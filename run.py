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
    from eta import theme
    from eta.modrinth import normalize

    n = normalize({"slug": "x", "title": "X", "categories": ["fabric", "magic"], "versions": ["1.20.1", "1.21",
                   "24w10a"], "downloads": 5, "date_modified": "2024-01-02T00:00:00Z"})
    assert n["loaders"] == ["fabric"] and n["categories"] == ["magic"] and n["game_versions"] == ["1.21", "1.20.1"]
    glass = theme.compose(theme.LIGHT, {"accent": "#5B8CC4", "backdrop": "scene:aurora", "glass": True,
                                        "glass_opacity": 0.5})
    assert glass["bg"] == "transparent" and glass["card"].startswith("rgba(") and glass["dialog"] != "transparent"
    assert theme.compose(theme.DARK, {})["accent"] == "#D97757"

    from eta.ui import (AddAccountDialog, CreateInstanceDialog, InstallDialog, LaunchDialog, MainWindow,
                        ProjectDialog)

    settings = Settings()
    instances = InstanceStore()
    win = MainWindow(app, settings, accounts, instances, prov)
    win.resize(1240, 800)
    win.show()
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
    inst = instances.add(ci.name.text(), ci.version.currentData(), ci.loader)
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
    acc2 = accounts.add_offline("Alex_2")
    win.select_account(acc2["uuid"])
    assert win.account()["name"] == "Alex_2"
    # launch dialog (demo flow)
    ld = LaunchDialog(win, inst, acc2)
    t0 = time.monotonic()
    while ld.bar.value() < 100 and time.monotonic() - t0 < 6:
        app.processEvents()
        time.sleep(0.002)
    assert ld.bar.value() == 100
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
