"""System mods: jars the launcher itself keeps inside instances. Today that is rurukaSuka — the community's cosmetics
mod (wardrobe, rurs) — plus its Fabric API dependency. Release metadata comes from mc-ru.org (`/api/launcher/mod`)
with GitHub Releases (`rurukasuka-v*`) as the fallback; what we placed is tracked in `<.minecraft>/eta-system-mods.json`
so a toggle removes exactly our files and never a user's."""
import hashlib
import json
import shutil
import time
from pathlib import Path

from . import mcru, net
from .modrinth import content_versions
from .paths import data_dir, load_json, save_json

GITHUB_RELEASES = "https://api.github.com/repos/tearsmilk/amkawa-lang/releases"
TAG_PREFIX = "rurukasuka-v"
TRACKER = "eta-system-mods.json"
LAUNCHER_JSON = "config/rurukasuka_launcher.json"
CACHE_TTL = 6 * 3600


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize(d):
    if not d or not d.get("version"):
        return None
    jar = d.get("jar") or {}
    return {"version": str(d["version"]), "mc_versions": list(d.get("mc_versions") or []),
            "loaders": list(d.get("loaders") or ["fabric", "quilt"]), "requires": list(d.get("requires") or []),
            "jar": {"url": jar.get("url", ""), "name": jar.get("name") or f"rurukasuka-{d['version']}.jar",
                    "size": int(jar.get("size") or 0), "sha256": (jar.get("sha256") or None)}}


def _from_github():
    for r in net.get_json(GITHUB_RELEASES, timeout=10, params={"per_page": 30}) or []:
        if r.get("draft") or not str(r.get("tag_name", "")).startswith(TAG_PREFIX):
            continue
        assets = r.get("assets") or []
        meta = next((a for a in assets if a.get("name") == "rurukasuka-mod.json"), None)
        jar = next((a for a in assets if str(a.get("name", "")).endswith(".jar")), None)
        if not jar:
            continue
        info = net.get_json(meta["browser_download_url"], timeout=10) if meta else {}
        info = dict(info or {})
        info.setdefault("version", r["tag_name"][len(TAG_PREFIX):])
        digest = str(jar.get("digest") or "")
        info["jar"] = {"url": jar["browser_download_url"], "name": jar["name"], "size": jar.get("size", 0),
                       "sha256": digest.split(":", 1)[1] if digest.startswith("sha256:") else None}
        return _normalize(info)
    return None


def info(force=False):
    """Latest mod release: site first, GitHub second, the cached answer (even stale) last. None when unknown."""
    cache_file = data_dir() / "sysmods.json"
    cache = load_json(cache_file, {})
    if not force and cache.get("info") and cache.get("fetched", 0) + CACHE_TTL > time.time():
        return cache["info"]
    found = None
    try:
        found = _normalize(net.get_json(f"{mcru.SITE}/api/launcher/mod", timeout=10))
    except Exception:  # noqa: BLE001 — the site may be down; GitHub is next
        found = None
    if not found:
        try:
            found = _from_github()
        except Exception:  # noqa: BLE001
            found = None
    if found:
        save_json(cache_file, {"fetched": time.time(), "info": found})
        return found
    return cache.get("info")


def supports(inf, inst):
    loader = inst.get("loader") or "vanilla"
    return bool(inf and loader in inf.get("loaders", []) and inst.get("mc_version") in inf.get("mc_versions", []))


def wanted(settings, inst):
    return bool(settings.get("rurukasuka", True)) and bool(inst.get("rurukasuka", True))


def managed_files(mc_dir):
    """Jar names in mods/ that the launcher put there (for the content page: «системный», no delete)."""
    have = load_json(Path(mc_dir) / TRACKER, {})
    return {v.get("file") for v in have.values() if isinstance(v, dict) and v.get("file")}


def _write_launcher_json(mc_dir, acc):
    acc = acc or {}
    token = acc.get("access_token", "") if acc.get("type") == "mcru" else ""
    f = Path(mc_dir) / LAUNCHER_JSON
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"token": token or "", "site": mcru.SITE, "nick": acc.get("name", "")},
                            ensure_ascii=False), "utf-8")


def remove(mc_dir, log=lambda s: None):
    """Take our jars out of mods/. Fabric API stays while other (user) mods could still need it."""
    mc_dir = Path(mc_dir)
    tracker = mc_dir / TRACKER
    have = load_json(tracker, {})
    mods = mc_dir / "mods"
    ours = {v.get("file") for v in have.values() if isinstance(v, dict)}
    others = [p for p in mods.glob("*.jar") if p.name not in ours] if mods.is_dir() else []
    for key in list(have):
        f = (have.get(key) or {}).get("file")
        if not f:
            continue
        if key == "fabric-api" and others:
            continue
        (mods / f).unlink(missing_ok=True)
        have.pop(key, None)
        log(f"[eta] rurukaSuka: убрали mods/{f}")
    if have:
        save_json(tracker, have)
    else:
        tracker.unlink(missing_ok=True)
    (mc_dir / LAUNCHER_JSON).unlink(missing_ok=True)


def ensure_rurukasuka(game, inst, mc_dir, settings, acc):
    """Install / refresh / remove the rurukaSuka system mod for this instance. Never raises."""
    log = getattr(game, "log", None) or (lambda s: None)
    mc_dir = Path(mc_dir)
    try:
        if not wanted(settings, inst):
            remove(mc_dir, log)
            return False
        inf = info()
        if not supports(inf, inst):
            if inf:
                log(f"[eta] rurukaSuka {inf['version']}: нет сборки для {inst.get('loader')} "
                    f"{inst.get('mc_version')} — пропускаем")
            remove(mc_dir, log)
            return False
        mods = mc_dir / "mods"
        mods.mkdir(parents=True, exist_ok=True)
        tracker = mc_dir / TRACKER
        have = load_json(tracker, {})
        jar = inf["jar"]
        cache_dir = data_dir() / "sysmods"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / (jar["name"] or f"rurukasuka-{inf['version']}.jar")
        if not cached.exists() or (jar.get("sha256") and _sha256(cached) != jar["sha256"]):
            net.download(jar["url"], cached)
            if jar.get("sha256") and _sha256(cached) != jar["sha256"]:
                cached.unlink(missing_ok=True)
                raise net.NetError("rurukaSuka: контрольная сумма jar не совпала")
        prev = (have.get("rurukasuka") or {}).get("file")
        if prev and prev != cached.name:
            (mods / prev).unlink(missing_ok=True)
        dest = mods / cached.name
        if not dest.exists() or _sha256(dest) != _sha256(cached):
            shutil.copy2(cached, dest)
            log(f"[eta] rurukaSuka {inf['version']} → mods/{dest.name}")
        have["rurukasuka"] = {"version": inf["version"], "file": dest.name}
        if any((r or {}).get("modrinth") == "fabric-api" for r in inf.get("requires", [])):
            present = [p for p in mods.glob("*.jar") if p.name.lower().startswith("fabric-api")]
            if not present:
                vs = [v for v in content_versions("fabric-api", inst.get("loader", ""), inst["mc_version"])
                      if v["file"].get("filename")]
                if vs:
                    pick = next((v for v in vs if v.get("type") == "release"), vs[0])
                    fdest = mods / pick["file"]["filename"]
                    net.download(pick["file"]["url"], fdest)
                    if pick["file"].get("sha1") and _sha1(fdest) != pick["file"]["sha1"]:
                        fdest.unlink(missing_ok=True)
                        raise net.NetError("Fabric API: контрольная сумма не совпала")
                    have["fabric-api"] = {"version": pick["name"], "file": fdest.name}
                    log(f"[eta] Fabric API {pick['name']} → mods/{fdest.name}")
                else:
                    log(f"[eta] Fabric API: нет сборки для {inst.get('loader')} {inst['mc_version']}")
        save_json(tracker, have)
        _write_launcher_json(mc_dir, acc)
        return True
    except Exception as e:  # noqa: BLE001 — cosmetics must never block a launch
        log(f"[eta] rurukaSuka пропущен: {e}")
        return False
