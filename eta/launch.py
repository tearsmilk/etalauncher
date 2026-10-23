"""Getting the game on disk and starting it: Mojang's version manifest → version JSON, client jar, libraries,
natives, assets and the log config; Mojang's own Java runtimes (the same ones the official launcher uses);
mod loaders — Fabric and Quilt from their meta servers, Forge and NeoForge through their installers; then the
command line with every ${placeholder} filled in.

Layout (everything shared between instances lives under the game folder):
  <game>/versions/<id>/<id>.json|jar   <game>/libraries/<maven path>   <game>/assets/{indexes,objects,log_configs}
  <game>/natives/<id>/                 <game>/instances/<iid>/.minecraft (the instance's own world / mods / configs)
  <data>/java/<component>/             Mojang runtime (jre.bundle/Contents/Home/bin/java on macOS)

This module has no Qt in it, so it can be driven from a worker thread and tested from the command line."""
import hashlib
import json
import lzma
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import __version__, mcru, net
from .modrinth import InstallError, content_versions
from .paths import data_dir

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
JAVA_RUNTIME_URL = ("https://launchermeta.mojang.com/v1/products/java-runtime/"
                    "2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json")
RESOURCES_URL = "https://resources.download.minecraft.net/"
LIBRARIES_URL = "https://libraries.minecraft.net/"
FABRIC_META = "https://meta.fabricmc.net/v2"
QUILT_META = "https://meta.quiltmc.org/v3"
FORGE_MAVEN = "https://maven.minecraftforge.net/"
FORGE_PROMOS = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
NEOFORGE_MAVEN = "https://maven.neoforged.net/releases/"
# old Forge JSONs point at this; the files moved
OLD_FORGE_MAVEN = ("http://files.minecraftforge.net/maven/", "https://files.minecraftforge.net/maven/")
# when Mojang has no build of a runtime for this platform, the next one with the same major works
JAVA_FALLBACK = {"java-runtime-alpha": "java-runtime-beta", "java-runtime-beta": "java-runtime-gamma",
                 "java-runtime-gamma-snapshot": "java-runtime-gamma"}


def host_os():
    return {"darwin": "osx", "win32": "windows"}.get(sys.platform, "linux")


def host_arch():
    m = platform.machine().lower()
    if m in ("arm64", "aarch64"):
        return "arm64"
    if m in ("i386", "i686", "x86"):
        return "x86"
    return "x86_64"


OS_NAME = host_os()
ARCH = host_arch()
JAVA_PLATFORM = {("osx", "x86_64"): "mac-os", ("osx", "arm64"): "mac-os-arm64", ("linux", "x86_64"): "linux",
                 ("linux", "x86"): "linux-i386", ("windows", "x86_64"): "windows-x64",
                 ("windows", "x86"): "windows-x86", ("windows", "arm64"): "windows-arm64"}.get((OS_NAME, ARCH), "linux")


def allowed(rules, features=None):
    """Mojang's rule lists: the last matching rule wins; no rules = allowed."""
    if not rules:
        return True
    ok = False
    for r in rules:
        match = True
        o = r.get("os") or {}
        if "name" in o and o["name"] != OS_NAME:
            match = False
        if "arch" in o and o["arch"] != ARCH:
            match = False
        if match and "version" in o:
            try:
                match = re.search(o["version"], platform.release()) is not None
            except re.error:
                match = False
        for k, want in (r.get("features") or {}).items():
            if bool((features or {}).get(k)) != bool(want):
                match = False
        if match:
            ok = r.get("action", "allow") == "allow"
    return ok


def maven_path(name):
    """group:artifact:version[:classifier][@ext] → group/dir/artifact/version/artifact-version[-classifier].ext"""
    ext = "jar"
    if "@" in name:
        name, ext = name.rsplit("@", 1)
    parts = name.split(":")
    group, artifact, version = parts[0], parts[1], parts[2]
    classifier = parts[3] if len(parts) > 3 else ""
    fn = f"{artifact}-{version}" + (f"-{classifier}" if classifier else "") + f".{ext}"
    return "/".join(group.split(".") + [artifact, version, fn])


def _lib_key(lib):
    parts = (lib.get("name") or "").split(":")
    return ":".join(parts[:2] + parts[3:4])


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ok(path, sha1=None, size=None):
    p = Path(path)
    if not p.is_file():
        return False
    if sha1:
        return _sha1(p) == sha1
    if size:
        return p.stat().st_size == int(size)
    return True


def merge(parent, child):
    """A loader's version JSON (inheritsFrom) on top of the vanilla one, the way the official launcher does it."""
    v = dict(parent)
    v["id"] = child.get("id", parent["id"])
    v["mainClass"] = child.get("mainClass", parent.get("mainClass"))
    v["jar"] = child.get("jar") or parent.get("jar") or parent["id"]
    seen, libs = set(), []
    for lib in list(child.get("libraries", [])) + list(parent.get("libraries", [])):
        k = _lib_key(lib)
        if k in seen:
            continue
        seen.add(k)
        libs.append(lib)
    v["libraries"] = libs
    if "minecraftArguments" in child:
        v["minecraftArguments"] = child["minecraftArguments"]
        v.pop("arguments", None)
    elif "arguments" in child:
        pa, ca = parent.get("arguments", {}), child["arguments"]
        v["arguments"] = {"jvm": list(pa.get("jvm", [])) + list(ca.get("jvm", [])),
                          "game": list(pa.get("game", [])) + list(ca.get("game", []))}
    for key in ("assetIndex", "assets", "downloads", "javaVersion", "logging", "type"):
        if key in child:
            v[key] = child[key]
    return v


def find_java(folder):
    """The java executable inside a runtime folder (macOS bundle or plain layout), or None."""
    folder = Path(folder)
    for rel in ("jre.bundle/Contents/Home/bin/java", "Contents/Home/bin/java", "bin/java", "bin/java.exe",
                "jre.bundle/Contents/Home/bin/java.exe"):
        p = folder / rel
        if p.is_file():
            return str(p)
    return None


def clean_env():
    """The game's environment: drop loader paths PyInstaller sets for the frozen app."""
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("DYLD_") or key in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
            orig = env.pop(key + "_ORIG", None)
            env.pop(key, None)
            if orig:
                env[key] = orig
    return env


class Game:
    """Everything below runs in a worker thread. progress(stage, done, total, text); cancel() → True aborts;
    log(line) gets installer / download chatter."""

    STAGES = ("version", "java", "loader", "libraries", "assets", "auth", "launch")
    MOD_LOADERS = ("fabric", "quilt", "forge", "neoforge")

    def __init__(self, root, java_root=None, progress=None, cancel=None, log=None, workers=8):
        self.root = Path(root)
        self.java_root = Path(java_root) if java_root else data_dir() / "java"
        self.progress = progress or (lambda *a: None)
        self.cancel = cancel or (lambda: False)
        self.log = log or (lambda s: None)
        self.workers = max(1, int(workers))
        for d in ("versions", "libraries", "assets", "natives", "instances"):
            (self.root / d).mkdir(parents=True, exist_ok=True)

    # -- helpers
    def _check(self):
        if self.cancel():
            raise net.NetError("Отменено")

    def _p(self, stage, done=0, total=0, text=""):
        self.progress(stage, done, total, text)

    def _cached_json(self, url, cache):
        """Network first, the last copy on disk when offline (manifests change, but a stale one still launches)."""
        cache = Path(cache)
        try:
            data = net.get_bytes(url)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
            return json.loads(data.decode("utf-8"))
        except net.NetError:
            if cache.is_file():
                self.log(f"[eta] офлайн: берём сохранённый {cache.name}")
                return json.loads(cache.read_text("utf-8"))
            raise

    def _fetch_many(self, items, stage, text):
        """items: (url, dest, sha1, size). Skips files already on disk and intact; parallel; progress by count."""
        todo = [it for it in items if not _ok(it[1], it[2], it[3])]
        total, done = len(items), len(items) - len(todo)
        self._p(stage, done, total, text)
        if not todo:
            return
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futs = {pool.submit(self._fetch_one, *it): it for it in todo}
            try:
                for fut in as_completed(futs):
                    fut.result()
                    done += 1
                    self._p(stage, done, total, text)
                    self._check()
            except BaseException:
                for f in futs:
                    f.cancel()
                raise

    def _fetch_one(self, url, dest, sha1=None, size=None):
        if not url:
            if Path(dest).is_file():
                return dest
            raise InstallError(f"Нет ссылки на файл {Path(dest).name}")
        for old, new in ((OLD_FORGE_MAVEN[0], FORGE_MAVEN), (OLD_FORGE_MAVEN[1], FORGE_MAVEN)):
            if url.startswith(old):
                url = FORGE_MAVEN + url[len(old):]
        last = None
        for attempt in range(3):     # a cut transfer or a bad proxy reply: try again before giving up
            try:
                net.download(url, dest, cancel=self.cancel)
                if sha1 and _sha1(dest) != sha1:
                    Path(dest).unlink(missing_ok=True)
                    raise InstallError(f"Контрольная сумма не совпала: {Path(dest).name}")
                if size and Path(dest).stat().st_size != int(size):
                    Path(dest).unlink(missing_ok=True)
                    raise InstallError(f"Размер файла не совпал: {Path(dest).name}")
                return dest
            except (net.NetError, InstallError) as e:
                last = e
                if self.cancel():
                    raise
                time.sleep(0.5 * (attempt + 1))
        raise last

    # -- vanilla
    def version_manifest(self):
        return self._cached_json(MANIFEST_URL, self.root / "versions" / "version_manifest_v2.json")

    def vanilla(self, mc):
        path = self.root / "versions" / mc / f"{mc}.json"
        try:
            entry = next((v for v in self.version_manifest()["versions"] if v["id"] == mc), None)
        except net.NetError:
            entry = None
            if not path.is_file():
                raise
        if entry is None and not path.is_file():
            raise InstallError(f"Версии Minecraft {mc} нет в списке Mojang")
        if entry and not _ok(path, entry.get("sha1")):
            self._fetch_one(entry["url"], path, entry.get("sha1"))
        return json.loads(path.read_text("utf-8"))

    # -- java
    def ensure_java(self, component, custom=None):
        if custom:
            p = Path(custom).expanduser()
            if p.is_file():
                return str(p)
            found = find_java(p)
            if found:
                return found
            raise InstallError(f"Java не найдена: {custom}")
        base = self.java_root / component
        marker = base / ".eta-runtime"
        all_ = self._cached_json(JAVA_RUNTIME_URL, self.java_root / "all.json")
        plat = all_.get(JAVA_PLATFORM) or {}
        comp = component
        while not plat.get(comp) and comp in JAVA_FALLBACK:
            comp = JAVA_FALLBACK[comp]
        entries = plat.get(comp) or []
        if not entries:
            raise InstallError(f"У Mojang нет Java «{component}» для этой системы ({JAVA_PLATFORM})")
        name = entries[0]["version"]["name"]
        exe = find_java(base)
        if exe and marker.is_file() and marker.read_text("utf-8").strip() == name:
            self._p("java", 1, 1, f"Java {name}")
            return exe
        self.log(f"[eta] ставим Java {comp} {name} → {base}")
        files = net.get_json(entries[0]["manifest"]["url"])["files"]
        for rel, info in files.items():
            if info["type"] == "directory":
                (base / rel).mkdir(parents=True, exist_ok=True)
        plain = [(rel, info) for rel, info in files.items() if info["type"] == "file"]
        total, done = len(plain), 0
        self._p("java", 0, total, f"Java {name}")
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futs = [pool.submit(self._java_file, base / rel, info) for rel, info in plain]
            try:
                for fut in as_completed(futs):
                    fut.result()
                    done += 1
                    self._p("java", done, total, f"Java {name}")
                    self._check()
            except BaseException:
                for f in futs:
                    f.cancel()
                raise
        for rel, info in files.items():
            if info["type"] == "link":
                dest = base / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.is_symlink() or dest.exists():
                    dest.unlink()
                try:
                    os.symlink(info["target"], dest)
                except OSError:
                    src = (dest.parent / info["target"]).resolve()
                    if src.is_file():
                        shutil.copy2(src, dest)
        exe = find_java(base)
        if not exe:
            raise InstallError("В скачанной Java нет исполняемого файла")
        marker.write_text(name, "utf-8")
        return exe

    def _java_file(self, dest, info):
        raw = info["downloads"]["raw"]
        if _ok(dest, raw.get("sha1")):
            if info.get("executable"):
                os.chmod(dest, 0o755)
            return
        lz = info["downloads"].get("lzma")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if lz:
            tmp = dest.with_name(dest.name + ".lzma")
            try:
                net.download(lz["url"], tmp, cancel=self.cancel)
                data = lzma.decompress(tmp.read_bytes())
                tmp.unlink(missing_ok=True)
                if not raw.get("sha1") or hashlib.sha1(data).hexdigest() == raw["sha1"]:
                    dest.write_bytes(data)
                    if info.get("executable"):
                        os.chmod(dest, 0o755)
                    return
            except (net.NetError, lzma.LZMAError):
                tmp.unlink(missing_ok=True)
                if self.cancel():
                    raise
        self._fetch_one(raw["url"], dest, raw.get("sha1"))
        if info.get("executable"):
            os.chmod(dest, 0o755)

    # -- loaders
    def loader_json(self, mc, loader, version, java):
        """(version JSON of the loader, its resolved version). version "" = newest stable / recommended."""
        if loader in ("fabric", "quilt"):
            meta = FABRIC_META if loader == "fabric" else QUILT_META
            if not version:
                lst = net.get_json(f"{meta}/versions/loader")
                pick = next((x for x in lst if x.get("stable", "-" not in x["version"])), lst[0] if lst else None)
                if not pick:
                    raise InstallError(f"{loader}: нет ни одной версии загрузчика")
                version = pick["version"]
            vid = f"{loader}-loader-{version}-{mc}"
            path = self.root / "versions" / vid / f"{vid}.json"
            if not path.is_file():
                self._p("loader", 0, 1, f"{loader} {version}")
                try:
                    data = net.get_json(f"{meta}/versions/loader/{mc}/{version}/profile/json")
                except net.NetError as e:
                    raise InstallError(f"{loader} {version} для Minecraft {mc} не найден ({e})") from e
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data), "utf-8")
            return json.loads(path.read_text("utf-8")), version
        if loader == "forge":
            if not version:
                promos = net.get_json(FORGE_PROMOS).get("promos", {})
                version = promos.get(f"{mc}-recommended") or promos.get(f"{mc}-latest")
                if not version:
                    raise InstallError(f"Forge для Minecraft {mc} не выпускался")
            full = f"{mc}-{version}"
            urls = [f"{FORGE_MAVEN}net/minecraftforge/forge/{full}/forge-{full}-installer.jar",
                    f"{FORGE_MAVEN}net/minecraftforge/forge/{full}-{mc}/forge-{full}-{mc}-installer.jar"]
            return self._installer("forge", f"forge-{full}", urls, java), version
        if loader == "neoforge":
            legacy = mc == "1.20.1"   # NeoForge for 1.20.1 is still published as net.neoforged:forge
            if not version:
                art = "forge" if legacy else "neoforge"
                xml = net.get_bytes(f"{NEOFORGE_MAVEN}net/neoforged/{art}/maven-metadata.xml").decode("utf-8")
                vs = re.findall(r"<version>([^<]+)</version>", xml)
                if legacy:
                    prefix = f"{mc}-"
                else:
                    a, b, *c = mc.split(".")
                    prefix = f"{b}.{c[0] if c else 0}." if a == "1" else f"{a}.{b}."
                vs = [v for v in vs if v.startswith(prefix)]
                stable = [v for v in vs if "beta" not in v]
                if not vs:
                    raise InstallError(f"NeoForge для Minecraft {mc} не выпускался")
                version = (stable or vs)[-1]
                if legacy:
                    version = version[len(prefix):]
            if legacy:
                full = f"{mc}-{version}"
                urls = [f"{NEOFORGE_MAVEN}net/neoforged/forge/{full}/forge-{full}-installer.jar"]
            else:
                urls = [f"{NEOFORGE_MAVEN}net/neoforged/neoforge/{version}/neoforge-{version}-installer.jar"]
            return self._installer("neoforge", f"neoforge-{version}", urls, java), version
        raise InstallError(f"Неизвестный загрузчик: {loader}")

    def _installer(self, kind, tag, urls, java):
        """Forge / NeoForge: download the installer, then either unpack it (old install_profile with versionInfo)
        or run it headless (--installClient) so it writes versions/<id>/<id>.json and the patched jars."""
        stamp = self.root / "versions" / f".{tag}.installed"
        if stamp.is_file():
            vid = stamp.read_text("utf-8").strip()
            path = self.root / "versions" / vid / f"{vid}.json"
            if path.is_file():
                return json.loads(path.read_text("utf-8"))
        jar = self.root / "versions" / f".{tag}-installer.jar"
        if not jar.is_file():
            self._p("loader", 0, 1, f"Установщик {tag}")
            last = None
            for url in urls:
                try:
                    self._fetch_one(url, jar)
                    break
                except (net.NetError, InstallError) as e:
                    last = e
            else:
                raise InstallError(f"Установщик {tag} не найден: {last}")
        with zipfile.ZipFile(jar) as z:
            prof = json.loads(z.read("install_profile.json").decode("utf-8"))
            if "versionInfo" in prof:      # old Forge (≤ 1.12): the version JSON and the universal jar are inside
                vi = prof["versionInfo"]
                vid = vi["id"]
                vdir = self.root / "versions" / vid
                vdir.mkdir(parents=True, exist_ok=True)
                (vdir / f"{vid}.json").write_text(json.dumps(vi), "utf-8")
                inst = prof.get("install", {})
                if inst.get("filePath") and inst.get("path"):
                    dest = self.root / "libraries" / maven_path(inst["path"])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(z.read(inst["filePath"]))
                stamp.write_text(vid, "utf-8")
                return vi
        vid = prof.get("version") or ""
        profiles = self.root / "launcher_profiles.json"
        if not profiles.is_file():
            profiles.write_text('{"profiles": {}}', "utf-8")
        self._p("loader", 0, 0, f"Устанавливаем {tag}…")
        self.log(f"[eta] {java} -jar {jar.name} --installClient {self.root}")
        before = {p.name for p in (self.root / "versions").iterdir() if p.is_dir()}
        proc = subprocess.Popen([java, "-jar", str(jar), "--installClient", str(self.root)], cwd=str(self.root),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                env=clean_env(), text=True, errors="replace")
        tail = []
        for line in proc.stdout:
            line = line.rstrip()
            self.log(line)
            tail = (tail + [line])[-12:]
            if self.cancel():
                proc.kill()
                raise net.NetError("Отменено")
        proc.wait()
        if proc.returncode:
            raise InstallError(f"Установщик {kind} завершился с ошибкой {proc.returncode}:\n" + "\n".join(tail))
        if not vid or not (self.root / "versions" / vid / f"{vid}.json").is_file():
            new = [p.name for p in (self.root / "versions").iterdir() if p.is_dir() and p.name not in before
                   and (p / f"{p.name}.json").is_file()]
            if not new:
                raise InstallError(f"Установщик {kind} не создал версию")
            vid = new[0]
        stamp.write_text(vid, "utf-8")
        return json.loads((self.root / "versions" / vid / f"{vid}.json").read_text("utf-8"))

    # -- files
    def ensure_files(self, v, natives_dir):
        """Client jar, libraries (+ natives extracted into natives_dir), assets, log config.
        Returns (classpath entries, log4j argument or None)."""
        jar_id = v.get("jar") or v["id"]
        client = self.root / "versions" / jar_id / f"{jar_id}.jar"
        items, cp, natives = [], [], []
        dl = (v.get("downloads") or {}).get("client")
        if dl:
            items.append((dl["url"], client, dl.get("sha1"), dl.get("size")))
        elif not client.is_file():
            raise InstallError(f"Нет файла игры для версии {jar_id}")
        for lib in v.get("libraries", []):
            if not allowed(lib.get("rules")) or lib.get("clientreq") is False:
                continue
            name = lib.get("name", "")
            dls = lib.get("downloads") or {}
            art = dls.get("artifact")
            if art:
                path = self.root / "libraries" / art["path"]
                items.append((art.get("url", ""), path, art.get("sha1"), art.get("size")))
                cp.append(path)
            elif name and not lib.get("natives"):
                path = self.root / "libraries" / maven_path(name)
                base = lib.get("url") or LIBRARIES_URL
                items.append((base.rstrip("/") + "/" + maven_path(name), path, lib.get("sha1"), lib.get("size")))
                cp.append(path)
            nat = (lib.get("natives") or {}).get(OS_NAME)
            if nat:
                nat = nat.replace("${arch}", "32" if ARCH == "x86" else "64")
                cls = (dls.get("classifiers") or {}).get(nat)
                if cls:
                    path = self.root / "libraries" / cls["path"]
                    items.append((cls.get("url", ""), path, cls.get("sha1"), cls.get("size")))
                elif name:
                    path = self.root / "libraries" / maven_path(f"{name}:{nat}")
                    base = lib.get("url") or LIBRARIES_URL
                    items.append((base.rstrip("/") + "/" + maven_path(f"{name}:{nat}"), path, None, None))
                natives.append((path, (lib.get("extract") or {}).get("exclude", [])))
        self._fetch_many(items, "libraries", "Библиотеки")
        cp.append(client)
        # natives (LWJGL 2 era and 1.13–1.18): fresh folder every launch
        natives_dir = Path(natives_dir)
        if natives:
            shutil.rmtree(natives_dir, ignore_errors=True)
            natives_dir.mkdir(parents=True, exist_ok=True)
            for jar, exclude in natives:
                with zipfile.ZipFile(jar) as z:
                    for n in z.namelist():
                        if n.endswith("/") or any(n.startswith(e) for e in exclude) or ".." in n:
                            continue
                        out = natives_dir / n
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(z.read(n))
        else:
            natives_dir.mkdir(parents=True, exist_ok=True)
        self._assets(v)
        log_arg = None
        lg = (v.get("logging") or {}).get("client")
        if lg and lg.get("file"):
            f = lg["file"]
            path = self.root / "assets" / "log_configs" / f["id"]
            self._fetch_many([(f["url"], path, f.get("sha1"), f.get("size"))], "assets", "Настройки журнала")
            log_arg = lg.get("argument", "-Dlog4j.configurationFile=${path}").replace("${path}", str(path))
        return cp, log_arg

    def _assets(self, v):
        ai = v.get("assetIndex")
        if not ai:
            return
        index = self.root / "assets" / "indexes" / f"{ai['id']}.json"
        self._fetch_many([(ai["url"], index, ai.get("sha1"), ai.get("size"))], "assets", "Список ресурсов")
        data = json.loads(index.read_text("utf-8"))
        objects = data.get("objects", {})
        items = []
        for name, o in objects.items():
            h = o["hash"]
            items.append((f"{RESOURCES_URL}{h[:2]}/{h}", self.root / "assets" / "objects" / h[:2] / h, None, o.get("size")))
        self._fetch_many(items, "assets", "Ресурсы игры")
        if data.get("virtual") or data.get("map_to_resources"):
            # 1.7.2 and older look for files by name, not by hash
            vdir = self.root / "assets" / "virtual" / ai["id"]
            for name, o in objects.items():
                h = o["hash"]
                dest = vdir / name
                if not dest.is_file():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(self.root / "assets" / "objects" / h[:2] / h, dest)

    # -- command line
    def command(self, v, java, game_dir, acc, settings, natives_dir, classpath, log_arg=None, inst=None,
                injector=None):
        inst = inst or {}
        mcru_acc = acc.get("type") == "mcru"
        token = (acc.get("access_token") or "0") if mcru_acc else "0"
        w, h = int(settings.get("width") or 0), int(settings.get("height") or 0)
        fullscreen = bool(settings.get("fullscreen"))
        features = {"is_demo_user": False, "has_custom_resolution": bool(w and h) and not fullscreen,
                    "has_quick_plays_support": False, "is_quick_play_singleplayer": False,
                    "is_quick_play_multiplayer": False, "is_quick_play_realms": False}
        ai = v.get("assetIndex") or {}
        assets_root = self.root / "assets"
        virtual = assets_root / "virtual" / ai.get("id", "legacy")
        cp_str = os.pathsep.join(str(p) for p in classpath)
        vars_ = {
            "auth_player_name": acc["name"], "version_name": v["id"], "game_directory": str(game_dir),
            "assets_root": str(assets_root), "assets_index_name": ai.get("id", v.get("assets", "legacy")),
            "auth_uuid": acc["uuid"].replace("-", ""),
            "auth_access_token": token, "auth_session": token,
            "user_type": "mojang" if mcru_acc else "legacy", "version_type": v.get("type", "release"),
            "user_properties": "{}",
            "natives_directory": str(natives_dir), "launcher_name": "eta", "launcher_version": __version__,
            "classpath": cp_str, "classpath_separator": os.pathsep, "library_directory": str(self.root / "libraries"),
            "clientid": "", "auth_xuid": "", "resolution_width": str(w or 854), "resolution_height": str(h or 480),
            "game_assets": str(virtual if virtual.is_dir() else assets_root), "quickPlayPath": "", "quickPlaySingleplayer": "",
            "quickPlayMultiplayer": "", "quickPlayRealms": "",
        }

        def sub(s):
            for k, val in vars_.items():
                s = s.replace("${" + k + "}", val)
            return s

        def expand(args):
            out = []
            for a in args:
                if isinstance(a, str):
                    out.append(sub(a))
                elif allowed(a.get("rules"), features):
                    val = a.get("value", [])
                    out += [sub(x) for x in ([val] if isinstance(val, str) else val)]
            return out

        if "arguments" in v:
            jvm = expand(v["arguments"].get("jvm", []))
            game = expand(v["arguments"].get("game", []))
        else:
            jvm = ["-Djava.library.path=" + str(natives_dir), "-cp", cp_str]
            game = [sub(x) for x in (v.get("minecraftArguments") or "").split()]
        if fullscreen:
            game.append("--fullscreen")
        mem = int(inst.get("memory_mb") or settings.get("memory_mb") or 4096)
        cmd = [java, f"-Xmx{mem}M"]
        if mcru_acc and injector:
            cmd += [f"-javaagent:{injector}={mcru.YGGDRASIL}", "-Dauthlibinjector.side=client"]
        cmd += ["-Dminecraft.launcher.brand=eta", f"-Dminecraft.launcher.version={__version__}"]
        if OS_NAME == "osx":
            cmd.append("-Xdock:name=" + (inst.get("name") or "Minecraft"))
        cmd += shlex.split(settings.get("jvm_args") or "")
        if log_arg:
            cmd.append(log_arg)
        cmd += jvm + [v["mainClass"]] + game
        return cmd

    def prepare(self, inst, acc, settings, inst_dir):
        """Everything needed to start this instance. Returns {cmd, cwd, env, version, java, loader_version}."""
        mc = inst["mc_version"]
        loader = inst.get("loader") or "vanilla"
        lv = inst.get("loader_version") or ""
        game_dir = Path(inst_dir) / ".minecraft"
        game_dir.mkdir(parents=True, exist_ok=True)
        self._p("version", 0, 1, f"Minecraft {mc}")
        van = self.vanilla(mc)
        self._check()
        comp = (van.get("javaVersion") or {}).get("component", "jre-legacy")
        self._p("java", 0, 0, "Проверяем Java…")
        java = self.ensure_java(comp, settings.get("java_path") or None)
        self._check()
        v = van
        if loader != "vanilla":
            self._p("loader", 0, 0, f"Загрузчик {loader}…")
            lj, lv = self.loader_json(mc, loader, lv, java)
            v = merge(van, lj)
        self._check()
        natives_dir = self.root / "natives" / v["id"]
        cp, log_arg = self.ensure_files(v, natives_dir)
        self._check()
        injector = None
        out = {}
        if acc.get("type") == "mcru":
            self._p("auth", 0, 0, "Проверяем сессию mc-ru.org…")
            out["account"] = self.mcru_session(acc)
            self._check()
            injector = mcru.authlib_injector(self.root / "authlib-injector",
                                             lambda d, t: self._p("auth", d, t, "authlib-injector"))
            if settings.get("csl_skins", True) and loader in self.MOD_LOADERS:
                self._p("auth", 0, 0, "CustomSkinLoader…")
                self.ensure_csl(game_dir, mc, loader)
            self._check()
        self._p("launch", 0, 1, "Собираем команду запуска…")
        cmd = self.command(v, java, game_dir, acc, settings, natives_dir, cp, log_arg, inst, injector)
        return {"cmd": cmd, "cwd": str(game_dir), "env": clean_env(), "version": v["id"], "java": java,
                "loader_version": lv, "started": time.time(), **out}

    # -- mc-ru.org
    def mcru_session(self, acc):
        """Make sure the Yggdrasil token is alive (validate → refresh); mutates and returns acc for saving."""
        if mcru.validate(acc.get("access_token", ""), acc.get("client_token", "")):
            return acc
        try:
            acc.update(mcru.refresh(acc.get("access_token", ""), acc.get("client_token", "")))
        except net.NetError as e:
            raise net.NetError("Сессия mc-ru.org истекла — войдите в аккаунт заново") from e
        return acc

    def ensure_csl(self, game_dir, mc, loader):
        """CustomSkinLoader mod + config pointing at mc-ru.org (HD and animated skins). Never fatal."""
        try:
            mods = Path(game_dir) / "mods"
            marker = Path(game_dir) / "eta-csl.json"
            have = json.loads(marker.read_text("utf-8")) if marker.exists() else {}
            if not (have.get("mc") == mc and have.get("loader") == loader
                    and (mods / have.get("file", "")).exists()):
                vs = content_versions("customskinloader", loader, mc)
                vs = [x for x in vs if x["file"].get("filename")]
                if vs:
                    pick = next((x for x in vs if x.get("type") == "release"), vs[0])
                    for old in mods.glob("CustomSkinLoader*.jar"):
                        old.unlink(missing_ok=True)
                    dest = mods / pick["file"]["filename"]
                    net.download(pick["file"]["url"], dest)
                    sha1 = pick["file"].get("sha1")
                    if sha1 and _sha1(dest) != sha1:
                        dest.unlink(missing_ok=True)
                        raise net.NetError("CustomSkinLoader: контрольная сумма не совпала")
                    marker.write_text(json.dumps({"mc": mc, "loader": loader, "version": pick["name"],
                                                  "file": dest.name}, ensure_ascii=False), "utf-8")
                    self.log(f"[eta] CustomSkinLoader {pick['name']} → mods/{dest.name}")
                else:
                    self.log(f"[eta] CustomSkinLoader: нет сборки для {loader} {mc}, HD-скины в игре не будет")
            self.csl_config(game_dir)
        except Exception as e:  # noqa: BLE001
            self.log(f"[eta] CustomSkinLoader пропущен: {e}")

    @staticmethod
    def csl_config(game_dir):
        cfg = Path(game_dir) / "CustomSkinLoader" / "CustomSkinLoader.json"
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text("utf-8"))
            except ValueError:
                data = dict(mcru.CSL_CONFIG)
            lst = data.get("loadlist") or []
            if any(e.get("root") == mcru.CSL_ROOT for e in lst):
                return cfg
            data["loadlist"] = [dict(mcru.CSL_ENTRY)] + lst
        else:
            data = json.loads(json.dumps(mcru.CSL_CONFIG))
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        return cfg
