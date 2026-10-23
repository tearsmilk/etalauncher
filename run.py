"""Entry point (PyInstaller / `python run.py`). `--selftest` runs headless checks for CI."""
import sys


def selftest():
    import json
    import os
    import tempfile
    import time

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # CI has no display
    tmp = tempfile.mkdtemp()
    os.environ["ETA_DATA"] = tmp
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from eta.accounts import AccountStore, offline_uuid, validate
    from eta.catalog import DemoProvider
    from eta.instances import InstanceStore
    from eta.paths import Settings

    report = {}
    # offline UUID like the vanilla server (UUID.nameUUIDFromBytes("OfflinePlayer:" + name))
    assert offline_uuid("Notch") == "b50ad385-829d-3141-a216-7e7d7539ba7f"
    assert validate("ab") and validate("имя") and validate("a" * 17) and validate("Steve_09") is None
    accounts = AccountStore()
    acc = accounts.add_offline("Steve_09")
    assert validate("steve_09", accounts.names())
    assert AccountStore().get(acc["uuid"])["name"] == "Steve_09"
    # catalog
    prov = DemoProvider()
    hits, total = prov.search(loaders=["fabric"], sort="downloads")
    assert total and all("fabric" in p["loaders"] for p in hits)
    assert all(hits[i]["downloads"] >= hits[i + 1]["downloads"] for i in range(len(hits) - 1))
    assert prov.search(query="магия")[1] >= 1 and prov.versions(hits[0]["slug"])
    report["catalog"] = len(prov.items)
    # Modrinth: hit normalisation + offline .mrpack install from a local http server (sha1, overrides, traversal)
    report["mrpack"] = _mrpack_test(tmp)
    # game files + Java + Fabric-style loader from a local server, then the launch command run with a fake java
    report["launch"] = _launch_test(tmp)
    # mc-ru.org accounts: fake Yggdrasil (login, refresh, validate), authlib-injector, CustomSkinLoader, command
    from tests.test_mcru import run as mcru_test

    report["mcru"] = mcru_test(tmp)["calls"]
    # Microsoft accounts: fake device-code / Xbox / XSTS / Minecraft services chain, refresh, command
    from tests.test_msa import run as msa_test

    report["msa"] = msa_test(tmp)["calls"]
    # CurseForge: fake Core API + CDN — search, files, modpack zip install (blocked files, class folders)
    from tests.test_curseforge import run as cf_test

    report["curseforge"] = cf_test(tmp)["calls"]
    # community servers: server list ping on a fake server, MOTD, quick play / --server, list cache, update check
    from tests.test_servers import run as servers_test

    report["servers"] = servers_test(tmp)["calls"]
    # system mod rurukaSuka: fake mc-ru.org release + fake Modrinth (Fabric API), tracker, toggles, GitHub fallback
    from tests.test_sysmods import run as sysmods_test

    report["sysmods"] = sysmods_test(tmp)["calls"]
    from eta import theme
    from eta.modrinth import normalize

    n = normalize({"slug": "x", "title": "X", "categories": ["fabric", "magic"], "versions": ["1.20.1", "1.21",
                   "24w10a"], "downloads": 5, "date_modified": "2024-01-02T00:00:00Z"})
    assert n["loaders"] == ["fabric"] and n["categories"] == ["magic"] and n["game_versions"] == ["1.21", "1.20.1"]
    glass = theme.compose(theme.LIGHT, {"accent": "#5B8CC4", "backdrop": "scene:aurora", "glass": True,
                                        "glass_opacity": 0.5})
    assert glass["bg"] == "transparent" and glass["card"].startswith("rgba(") and glass["dialog"] != "transparent"
    assert theme.compose(theme.DARK, {})["accent"] == "#D97757"

    from eta.ui import AddAccountDialog, CreateInstanceDialog, InstallDialog, MainWindow, ProjectDialog

    settings = Settings()
    settings.update(check_updates=False)   # no network from the UI test
    instances = InstanceStore()
    win = MainWindow(app, settings, accounts, instances, prov)
    win.resize(1240, 800)
    win.show()
    # servers page renders the cached list (written by tests.test_servers) and the update banner shows/hides
    win.go("servers")
    app.processEvents()
    assert win.servers_page.list.count() >= 2 and win.nav["servers"].isChecked()
    # the home page shows the same cached servers in «Серверы сообщества» (max 4) and hides the block when empty
    win.go("home")
    app.processEvents()
    assert len(win.home.server_cards) >= 2 and not win.home.servers_head.isHidden()
    win.home.render_servers([])
    assert win.home.servers_head.isHidden() and win.home.servers_box.isHidden() and not win.home.server_cards
    win.home.render_servers(win.servers.items)
    win.home.show_update({"version": "9.9.9", "url": "", "newer": True})
    assert win.home.update_bar.isVisible() or not win.home.isVisible()
    win.home._skip_update()
    assert settings["update_skip"] == "9.9.9" and win.home.update_bar.isHidden()
    win.start(fast=True)
    t0 = time.monotonic()
    while win.root.currentIndex() == 0 and time.monotonic() - t0 < 5:
        app.processEvents()
        time.sleep(0.005)
    assert win.root.currentIndex() == 1, "loading page did not finish"
    for key in ("home", "modpacks", "accounts", "settings", "home"):
        win.go(key)
        app.processEvents()
        win.grab()
    # catalog filters and «more»
    mp = win.modpacks
    win.go("modpacks")
    mp.f_loaders["neoforge"].setChecked(True)
    app.processEvents()
    q = mp.query()
    assert q["loaders"] == ["neoforge"]
    mp.reset_filters()

    def rows():
        return [mp.results.itemAt(i).widget() for i in range(mp.results.count()) if mp.results.itemAt(i).widget()]

    wait(app, lambda: any(type(r).__name__ == "ProjectRow" for r in rows()), "catalog results")
    n0 = sum(type(r).__name__ == "ProjectRow" for r in rows())
    if any(r.objectName() == "MoreBtn" for r in rows()):
        mp.more()
        wait(app, lambda: sum(type(r).__name__ == "ProjectRow" for r in rows()) > n0, "more results")
    mp.toggle_filters(False)
    assert settings["filters_hidden"]
    mp.toggle_filters(True)
    # project page + install (fast) → instance
    slug = prov.items[1]["slug"]
    ProjectDialog(win, prov, slug).grab()
    dlg = InstallDialog(win, prov, prov.project(slug))
    wait(app, lambda: dlg.version.count() and dlg.version.currentData(), "versions")
    dlg.start(fast=True)
    t0 = time.monotonic()
    while dlg.result_inst is None and time.monotonic() - t0 < 5:
        app.processEvents()
        time.sleep(0.002)
    assert dlg.result_inst and instances.get(dlg.result_inst["id"])["mods"] > 0
    # own instance
    ci = CreateInstanceDialog(win)
    ci.name.setText("Выживание")
    ci.loader = "quilt"
    inst = instances.add(ci.name.text(), "t1", "fabric")
    win.select_instance(inst["id"], go_home=False)
    mp.show_tab("mine")
    app.processEvents()
    assert win.instance()["id"] == inst["id"]
    # account dialog: live validation
    ad = AddAccountDialog(win)
    ad.name.setText("x")
    assert not ad.ok.isEnabled()
    ad.name.setText("Alex_2")
    assert ad.ok.isEnabled() and "UUID" in ad.uuid.text()
    ad.site.setChecked(True)   # mc-ru.org mode: «Войти» only with both fields, link in the hint
    assert ad.mode == "mcru" and ad.ok.text() == "Войти" and not ad.ok.isEnabled() and "mc-ru.org" in ad.hint.text()
    ad.login.setText("hoka@example.com")
    ad.password.setText("x")
    assert ad.ok.isEnabled()
    ad.off.setChecked(True)
    assert ad.mode == "offline" and ad.ok.text() == "Создать" and ad.ok.isEnabled()
    # Microsoft tab: disabled without a Client ID, enabled (device-code UI) with one
    from eta import msa as _msa
    assert ad.ms.isEnabled() == _msa.available()
    old_cid, _msa.CLIENT_ID = _msa.CLIENT_ID, "test-client"
    ad2 = AddAccountDialog(win)
    assert ad2.ms.isEnabled()
    ad2.ms.setChecked(True)
    assert ad2.mode == "msa" and ad2.ok.text() == "Войти через Microsoft" and ad2.ok.isEnabled()
    ad2._ms_show_code("ABCD-1234", "https://www.microsoft.com/link", "")
    assert ad2.ms_code.text() == "ABCD-1234" and not ad2.ms_code.isHidden() and "Ожидаем" in ad2.ms_msg.text()
    _msa.CLIENT_ID = old_cid
    acc_ms = accounts.add_msa("Notch", "069a79f4-44e9-4726-a5be-fca90e38aaf5", "mc", time.time() + 3600, "rt", "1")
    assert AccountStore().get(acc_ms["uuid"])["type"] == "msa"
    win.select_account(acc_ms["uuid"])
    win.go("accounts")
    app.processEvents()
    accounts.remove(acc_ms["uuid"])
    acc_site = accounts.add_mcru("Hoka_Neko", "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa", "tok", "ct", "hoka@example.com")
    assert AccountStore().get(acc_site["uuid"])["type"] == "mcru" and accounts.update(acc_site["uuid"], access_token="t2")
    win.select_account(acc_site["uuid"])
    win.go("accounts")
    app.processEvents()
    win.grab()
    accounts.remove(acc_site["uuid"])
    acc2 = accounts.add_offline("Alex_2")
    win.select_account(acc2["uuid"])
    assert win.account()["name"] == "Alex_2"
    # launch dialog: real pipeline against the local server (patched in _launch_test), fake java exits at once
    if sys.platform != "win32":   # the fake java is a shell script (see _launch_test)
        settings.update(show_console=True)
        ld = win.launch(inst)
        wait(app, lambda: ld.phase == "done", "launch dialog", timeout=20)
        assert "--username Alex_2" in ld.console.toPlainText() and inst["id"] not in win.games
        assert ld.stage.text() == "Игра закрыта" and instances.get(inst["id"])["loader_version"] == "0.1"
        settings.update(show_console=False)
    # look: glass over a scene, sidebar on the right, hidden sidebar (rail)
    settings.update(accent="#7BA05B", backdrop="scene:aurora", glass=True, sidebar_side="right")
    win.apply_theme()
    win.go("settings")
    app.processEvents()
    win.grab()
    assert win.side.objectName() == "SideR"
    win.toggle_sidebar()
    app.processEvents()
    assert settings["sidebar_hidden"] and win.rail.isVisible() and not win.side.isVisible()
    win.toggle_sidebar()
    settings.update(backdrop="none", glass=False, sidebar_side="left")
    win.apply_theme()
    win.go("home")
    app.processEvents()
    assert "Alex_2" in win.home.greet.text()
    report["instances"] = len(instances.items)
    report["accounts"] = len(accounts.items)
    win.close()
    print("eta selftest ok", json.dumps(report, ensure_ascii=False))
    return 0


def wait(app, cond, what, timeout=5):
    import time

    t0 = time.monotonic()
    while not cond():
        if time.monotonic() - t0 > timeout:
            raise AssertionError(f"timeout: {what}")
        app.processEvents()
        time.sleep(0.005)


def _launch_test(tmp):
    """A local 'Mojang': version manifest, version JSON, client jar, a library, a natives jar, assets, a log config,
    a Java runtime whose bin/java is a shell script, and a Fabric-like meta. launch.* URLs are pointed at it."""
    import hashlib
    import http.server
    import json
    import os
    import subprocess
    import threading
    import zipfile
    from pathlib import Path

    from eta import launch

    import io

    files = {}   # url path → bytes (a dict, because /versions/loader is both a file and a folder in Fabric's meta)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            data = files.get(self.path.split("?")[0].lstrip("/"))
            self.send_response(200 if data is not None else 404)
            self.send_header("Content-Length", str(len(data or b"")))
            self.end_headers()
            self.wfile.write(data or b"")

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def put(rel, data):
        data = data if isinstance(data, bytes) else data.encode("utf-8")
        files[rel] = data
        return {"url": f"{base}/{rel}", "sha1": hashlib.sha1(data).hexdigest(), "size": len(data)}

    def jar(rel, members):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n, d in members.items():
                z.writestr(n, d)
        return put(rel, buf.getvalue())

    java = put("jre/bin/java", "#!/bin/sh\necho ETA-JAVA \"$@\"\n")
    jre = put("jre.json", json.dumps({"files": {
        "bin": {"type": "directory"}, "bin/java": {"type": "file", "executable": True, "downloads": {"raw": java}},
        "legal": {"type": "directory"}, "legal/java": {"type": "link", "target": "../bin/java"}}}))
    put("all.json", json.dumps({launch.JAVA_PLATFORM: {"jre-legacy": [{"version": {"name": "test-8"},
                                                                       "manifest": jre}]}}))
    client = jar("client.jar", {"test/Main.class": b"\xca\xfe"})
    lib = jar("libs/a/b/lib/1/lib-1.jar", {"lib.txt": "lib"})
    nat = jar("libs/a/b/nat/1/nat-1-natives.jar", {"libnat.so": b"nat", "META-INF/MANIFEST.MF": "x"})
    h1, h2 = hashlib.sha1(b"one").hexdigest(), hashlib.sha1(b"two").hexdigest()
    put(f"objects/{h1[:2]}/{h1}", "one")
    put(f"objects/{h2[:2]}/{h2}", "two")
    index = put("t.json", json.dumps({"virtual": True, "objects": {"a/one.txt": {"hash": h1, "size": 3},
                                                                   "two.txt": {"hash": h2, "size": 3}}}))
    log = put("log.xml", "<Configuration/>")
    natives_key = {"osx": "natives-osx", "linux": "natives-linux", "windows": "natives-windows"}
    classifiers = {k: dict(nat, path="a/b/nat/1/nat-1-natives.jar") for k in natives_key.values()}
    vj = {"id": "t1", "type": "release", "mainClass": "test.Main",
          "javaVersion": {"component": "jre-legacy", "majorVersion": 8},
          "assetIndex": dict(index, id="t", totalSize=6), "downloads": {"client": client},
          "logging": {"client": {"argument": "-Dlog4j.configurationFile=${path}", "file": dict(log, id="log.xml"),
                                 "type": "log4j2-xml"}},
          "libraries": [{"name": "a.b:lib:1", "downloads": {"artifact": dict(lib, path="a/b/lib/1/lib-1.jar")}},
                        {"name": "a.b:nat:1", "natives": natives_key, "extract": {"exclude": ["META-INF/"]},
                         "downloads": {"classifiers": classifiers}},
                        {"name": "a.b:skip:1", "rules": [{"action": "allow", "os": {"name": "nowhere"}}],
                         "downloads": {"artifact": {"url": f"{base}/missing.jar", "path": "a/b/skip/1/skip-1.jar",
                                                    "sha1": "0" * 40, "size": 1}}}],
          "arguments": {"game": ["--username", "${auth_player_name}", "--gameDir", "${game_directory}",
                                 "--assetIndex", "${assets_index_name}",
                                 {"rules": [{"action": "allow", "features": {"has_custom_resolution": True}}],
                                  "value": ["--width", "${resolution_width}"]}],
                        "jvm": [{"rules": [{"action": "allow", "os": {"name": launch.OS_NAME}}],
                                 "value": ["-XstartOnFirstThread"]},
                                "-Djava.library.path=${natives_directory}", "-cp", "${classpath}"]}}
    ver = put("t1.json", json.dumps(vj))
    put("version_manifest_v2.json", json.dumps({"latest": {"release": "t1"}, "versions": [dict(ver, id="t1")]}))
    fl = jar("maven/a/b/fl/1/fl-1.jar", {"fl.txt": "loader"})
    put("fabric/versions/loader", json.dumps([{"version": "0.2-beta", "stable": False}, {"version": "0.1", "stable": True}]))
    put("fabric/versions/loader/t1/0.1/profile/json", json.dumps({
        "id": "fabric-loader-0.1-t1", "inheritsFrom": "t1", "mainClass": "fabric.Main",
        "libraries": [{"name": "a.b:fl:1", "url": f"{base}/maven/", "sha1": fl["sha1"], "size": fl["size"]}],
        "arguments": {"jvm": ["-Dfabric=1"], "game": ["--fab"]}}))
    launch.MANIFEST_URL = f"{base}/version_manifest_v2.json"
    launch.JAVA_RUNTIME_URL = f"{base}/all.json"
    launch.RESOURCES_URL = f"{base}/objects/"
    launch.FABRIC_META = f"{base}/fabric"

    root = Path(tmp) / "minecraft"
    seen = []
    g = launch.Game(root, Path(tmp) / "java", lambda st, d, t, x: seen.append(st), workers=4)
    acc = {"name": "Steve_09", "uuid": "b50ad385-829d-3141-a216-7e7d7539ba7f"}
    settings = {"memory_mb": 1024, "width": 1280, "height": 720, "jvm_args": "-Dx=1"}
    inst = {"id": "i1", "name": "Тест", "mc_version": "t1", "loader": "fabric", "loader_version": ""}
    r = g.prepare(inst, acc, settings, root / "instances" / "i1")
    cmd = r["cmd"]
    assert r["version"] == "fabric-loader-0.1-t1" and r["loader_version"] == "0.1"
    assert Path(cmd[0]).name == "java" and "-Xmx1024M" in cmd and "-Dx=1" in cmd and "-Dfabric=1" in cmd
    assert "-XstartOnFirstThread" in cmd and cmd[cmd.index("-cp") + 1].split(os.pathsep)[0].endswith("fl-1.jar")
    assert cmd.index("--fab") > cmd.index("fabric.Main") > cmd.index("-cp") and "--width" in cmd
    assert any(a.startswith("-Dlog4j.configurationFile=") for a in cmd)
    natives = root / "natives" / "fabric-loader-0.1-t1"
    assert (natives / "libnat.so").read_bytes() == b"nat" and not (natives / "META-INF").exists()
    assert (root / "assets" / "objects" / h1[:2] / h1).read_bytes() == b"one"
    assert (root / "assets" / "virtual" / "t" / "a" / "one.txt").read_bytes() == b"one"
    assert not (root / "libraries" / "a/b/skip/1/skip-1.jar").exists()
    assert (Path(tmp) / "java" / "jre-legacy" / "legal" / "java").exists()
    assert "java" in seen and "assets" in seen and "libraries" in seen
    if os.name != "nt":   # the fake java is a shell script; Windows CI checks the command, not its run
        out = subprocess.run(cmd, cwd=r["cwd"], env=r["env"], capture_output=True, text=True, timeout=30).stdout
        assert "ETA-JAVA" in out and "--username Steve_09" in out and "--assetIndex t" in out, out
    else:
        assert "--username" in cmd and cmd[cmd.index("--username") + 1] == "Steve_09" and "--assetIndex" in cmd
    # second run: nothing to download, same command
    g2 = launch.Game(root, Path(tmp) / "java", workers=4)
    assert g2.prepare(inst, acc, settings, root / "instances" / "i1")["cmd"] == cmd
    # rules and maven paths
    assert launch.maven_path("net.fabricmc:fabric-loader:0.16.9") == \
        "net/fabricmc/fabric-loader/0.16.9/fabric-loader-0.16.9.jar"
    assert launch.maven_path("org.lwjgl:lwjgl:3.3.1:natives-macos@zip") == \
        "org/lwjgl/lwjgl/3.3.1/lwjgl-3.3.1-natives-macos.zip"
    assert launch.allowed([{"action": "allow"}, {"action": "disallow", "os": {"name": "nowhere"}}])
    assert not launch.allowed([{"action": "allow", "os": {"name": "nowhere"}}])
    assert launch.allowed([{"action": "allow", "features": {"is_demo_user": True}}], {"is_demo_user": True})
    return len(cmd)


def _mrpack_test(tmp):
    """Build a tiny .mrpack whose files are served by a local http server, install it, check everything landed."""
    import hashlib
    import http.server
    import json
    import threading
    import zipfile
    from functools import partial
    from pathlib import Path

    from eta.modrinth import InstallError, install_mrpack

    srv_dir = Path(tmp) / "srv"
    srv_dir.mkdir()
    payload = {f"mod{i}.jar": f"jar {i}".encode() * 50 for i in range(5)}
    for name, data in payload.items():
        (srv_dir / name).write_bytes(data)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(srv_dir)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def pack(files, path):
        index = {"formatVersion": 1, "game": "minecraft", "versionId": "1.0", "name": "Тест",
                 "dependencies": {"minecraft": "1.20.1", "fabric-loader": "0.16.9"}, "files": files}
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("modrinth.index.json", json.dumps(index))
            z.writestr("overrides/config/a.txt", "common")
            z.writestr("client-overrides/config/a.txt", "client")
            z.writestr("overrides/options.txt", "lang:ru_ru")
        return path

    files = [{"path": f"mods/{n}", "hashes": {"sha1": hashlib.sha1(d).hexdigest()}, "downloads": [f"{base}/{n}"],
              "fileSize": len(d), "env": {"client": "required", "server": "required"}} for n, d in payload.items()]
    files.append({"path": "mods/server-only.jar", "hashes": {}, "downloads": [f"{base}/nope"],
                  "env": {"client": "unsupported", "server": "required"}})
    target = Path(tmp) / "inst" / ".minecraft"
    seen = []
    info = install_mrpack(pack(files, Path(tmp) / "t.mrpack"), target, lambda st, d, t: seen.append(st),
                          allow_hosts={"127.0.0.1"})
    assert info["mods"] == 5 and info["loader"] == "fabric" and info["mc"] == "1.20.1"
    assert all((target / "mods" / n).read_bytes() == d for n, d in payload.items())
    assert not (target / "mods" / "server-only.jar").exists()
    assert (target / "config" / "a.txt").read_text() == "client" and (target / "options.txt").exists()
    assert (target.parent / "eta-pack.json").exists() and "files" in seen
    # bad hash, foreign host, path traversal → refused
    for bad in ({"path": "mods/x.jar", "hashes": {"sha1": "0" * 40}, "downloads": [f"{base}/mod0.jar"]},
                {"path": "mods/x.jar", "downloads": ["https://evil.example/x.jar"]},
                {"path": "../../escape.jar", "downloads": [f"{base}/mod0.jar"]}):
        try:
            install_mrpack(pack([bad], Path(tmp) / "bad.mrpack"), Path(tmp) / "bad" / ".minecraft",
                           allow_hosts={"127.0.0.1"})
            raise AssertionError(f"accepted a bad pack entry: {bad}")
        except InstallError:
            pass
    assert not (Path(tmp) / "escape.jar").exists()
    httpd.shutdown()
    return info["mods"]


try:
    import http.server as _hs

    class _QuietHandler(_hs.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
except ImportError:  # pragma: no cover
    _QuietHandler = None


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        code = selftest()
        sys.stdout.flush()
        sys.stderr.flush()
        import os

        os._exit(code)  # every check ran; skip interpreter teardown of Qt objects
    from eta.ui import main

    sys.exit(main())
