"""CurseForge: modpack / content search (Core API v1), project pages, files, and installing a CurseForge modpack
zip (manifest.json + overrides) into an instance folder.

The API needs a key: https://console.curseforge.com → API keys (free). Put it in the launcher settings
(«Настройки → Загрузки → API-ключ CurseForge») or in the ETA_CURSEFORGE_KEY environment variable.
Docs: https://docs.curseforge.com — all requests send the key in the `x-api-key` header."""
import json
import os
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from . import net
from .modrinth import InstallError, _safe_join, _sha1
from .paths import data_dir

API = "https://api.curseforge.com/v1"
EDGE = "https://edge.forgecdn.net/files"
GAME_ID = 432
CLASS_IDS = {"modpack": 4471, "mod": 6, "shader": 6552, "resourcepack": 12, "datapack": 6945, "world": 17}
CLASS_FOLDERS = {6: "mods", 6552: "shaderpacks", 12: "resourcepacks", 6945: "datapacks"}
LOADER_TYPES = {"forge": 1, "fabric": 4, "quilt": 5, "neoforge": 6}
LOADER_NAMES = {v: k for k, v in LOADER_TYPES.items()}
SORT_FIELDS = {"relevance": 2, "follows": 2, "downloads": 6, "updated": 3, "newest": 3}
RELEASE_TYPES = {1: "release", 2: "beta", 3: "alpha"}
_SETTINGS = {}


def api_key(settings=None):
    s = settings if settings is not None else _SETTINGS
    return (os.environ.get("ETA_CURSEFORGE_KEY") or (s.get("curseforge_key") if hasattr(s, "get") else "") or "").strip()


def available(settings=None):
    return bool(api_key(settings))


def _headers(settings=None):
    key = api_key(settings)
    if not key:
        raise net.NetError("Нужен API-ключ CurseForge — Настройки → Загрузки → API-ключ CurseForge")
    return {"x-api-key": key}


def _get(path, params=None, settings=None):
    return net.get_json(f"{API}{path}", params=params, headers=_headers(settings))


def _post(path, payload, settings=None):
    return net.post_json(f"{API}{path}", payload, headers=_headers(settings))


def _ts(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def _is_release(v):
    return bool(v) and all(part.isdigit() for part in v.split("."))


def _sorted_versions(vs):
    return sorted({v for v in vs if _is_release(v)}, key=lambda v: [int(x) for x in v.split(".")], reverse=True)


def edge_url(file_id, file_name):
    """CDN link for a file whose API `downloadUrl` is null."""
    from urllib.parse import quote

    return f"{EDGE}/{int(file_id) // 1000}/{int(file_id) % 1000}/{quote(file_name)}"


def normalize(hit):
    idx = hit.get("latestFilesIndexes") or []
    loaders = []
    for i in idx:
        name = LOADER_NAMES.get(i.get("modLoader"))
        if name and name not in loaders:
            loaders.append(name)
    cats = [c.get("slug") or c.get("name", "").lower() for c in hit.get("categories") or []]
    logo = hit.get("logo") or {}
    return {
        "project_id": str(hit.get("id")), "slug": str(hit.get("id")), "cf_slug": hit.get("slug", ""),
        "title": hit.get("name", ""), "author": ", ".join(a.get("name", "") for a in hit.get("authors") or [])[:60],
        "description": hit.get("summary", ""), "categories": cats, "loaders": loaders,
        "game_versions": _sorted_versions([i.get("gameVersion", "") for i in idx]),
        "downloads": int(hit.get("downloadCount") or 0), "follows": int(hit.get("thumbsUpCount") or 0),
        "date_created": _ts(hit.get("dateCreated") or ""), "date_modified": _ts(hit.get("dateModified") or ""),
        "icon_url": logo.get("thumbnailUrl") or logo.get("url") or "", "source": "curseforge", "mods": None,
        "body": "", "url": (hit.get("links") or {}).get("websiteUrl") or f"https://www.curseforge.com/minecraft/modpacks/{hit.get('slug', '')}",
        "gallery": [s.get("url") for s in hit.get("screenshots") or [] if s.get("url")], "class_id": hit.get("classId"),
    }


def normalize_file(f):
    gv = f.get("gameVersions") or []
    mcs = _sorted_versions(gv)
    loaders = [g.lower() for g in gv if g.lower() in LOADER_TYPES]
    sha1 = next((h["value"] for h in f.get("hashes") or [] if h.get("algo") == 1), None)
    url = f.get("downloadUrl") or edge_url(f["id"], f.get("fileName", ""))
    return {
        "id": f.get("id"), "name": f.get("displayName") or f.get("fileName"), "version": f.get("displayName") or "",
        "mc": mcs[0] if mcs else "", "game_versions": mcs, "loader": loaders[0] if loaders else "", "loaders": loaders,
        "type": RELEASE_TYPES.get(f.get("releaseType"), "release"), "date": _ts(f.get("fileDate", "")),
        "downloads": f.get("downloadCount", 0),
        "file": {"url": url, "filename": f.get("fileName", ""), "size": f.get("fileLength", 0), "sha1": sha1,
                 "direct": bool(f.get("downloadUrl"))},
    }


# ---- categories (launcher slugs → CurseForge ids)

_CAT_ALIASES = {"kitchen-sink": ["multiplayer", "combat / pvp"], "lightweight": ["small / light"], "challenging": ["hardcore"],
                "technology": ["tech"], "quests": ["quests"], "magic": ["magic"], "adventure": ["adventure and rpg"],
                "combat": ["combat / pvp"], "multiplayer": ["multiplayer"], "optimization": ["small / light"]}


def categories(settings=None):
    cache = data_dir() / "cf-categories.json"
    try:
        if cache.is_file() and time.time() - cache.stat().st_mtime < 86400:
            return json.loads(cache.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        pass
    data = _get("/categories", {"gameId": GAME_ID, "classId": CLASS_IDS["modpack"]}, settings).get("data") or []
    out = {str(c.get("slug") or c.get("name", "")).lower(): c["id"] for c in data if c.get("id")}
    out.update({str(c.get("name", "")).lower(): c["id"] for c in data if c.get("id")})
    try:
        cache.write_text(json.dumps(out), "utf-8")
    except OSError:
        pass
    return out


def category_ids(slugs, settings=None):
    if not slugs:
        return []
    try:
        table = categories(settings)
    except net.NetError:
        return []
    ids = []
    for s in slugs:
        for cand in [s, s.replace("-", " ")] + _CAT_ALIASES.get(s, []):
            cid = table.get(cand.lower())
            if cid and cid not in ids:
                ids.append(cid)
                break
    return ids


# ---- provider

class CurseForgeProvider:
    name = "curseforge"

    def __init__(self, settings=None):
        self.settings = settings
        self._projects = {}

    def available(self):
        return available(self.settings)

    def search(self, query="", sources=(), loaders=(), version="", categories=(), sort="relevance", offset=0,
               limit=20):
        params = {"gameId": GAME_ID, "classId": CLASS_IDS["modpack"], "searchFilter": query or "",
                  "sortField": SORT_FIELDS.get(sort, 2), "sortOrder": "desc", "index": int(offset),
                  "pageSize": int(limit)}
        if version:
            params["gameVersion"] = version
        types = [LOADER_TYPES[lo] for lo in loaders if lo in LOADER_TYPES]
        if len(types) == 1:
            params["modLoaderType"] = types[0]
        elif types:
            params["modLoaderTypes"] = json.dumps(types)
        ids = category_ids(categories, self.settings)
        if len(ids) == 1:
            params["categoryId"] = ids[0]
        elif ids:
            params["categoryIds"] = json.dumps(ids)
        data = _get("/mods/search", params, self.settings)
        hits = [normalize(h) for h in data.get("data") or []]
        for h in hits:
            self._projects.setdefault(h["slug"], h)
        total = int((data.get("pagination") or {}).get("totalCount") or len(hits))
        return hits, total

    def project(self, slug):
        """Full project with its HTML description (CurseForge serves HTML, not markdown)."""
        try:
            p = normalize(_get(f"/mods/{int(slug)}", settings=self.settings).get("data") or {})
            try:
                p["body"] = _get(f"/mods/{int(slug)}/description", settings=self.settings).get("data") or ""
            except net.NetError:
                p["body"] = ""
            p["body_html"] = True
            self._projects[slug] = p
            return p
        except (net.NetError, ValueError):
            return self._projects.get(slug)

    def cached(self, slug):
        return self._projects.get(slug)

    def versions(self, slug):
        data = _get(f"/mods/{int(slug)}/files", {"pageSize": 50}, self.settings).get("data") or []
        return [normalize_file(f) for f in data]


# ---- standalone content search (mods, shaders, resourcepacks, datapacks) for ModAddDialog

def search_content(query="", project_type="mod", loaders=(), version="", offset=0, limit=20, settings=None):
    params = {"gameId": GAME_ID, "classId": CLASS_IDS.get(project_type, 6), "searchFilter": query or "",
              "sortField": 2, "sortOrder": "desc", "index": int(offset), "pageSize": int(limit)}
    if version:
        params["gameVersion"] = version
    types = [LOADER_TYPES[lo] for lo in loaders if lo in LOADER_TYPES]
    if types and project_type == "mod":
        params["modLoaderType"] = types[0]
    data = _get("/mods/search", params, settings)
    return [normalize(h) for h in data.get("data") or []]


def content_versions(mod_id, loader="", version="", settings=None):
    params = {"pageSize": 50}
    if version:
        params["gameVersion"] = version
    if loader and loader in LOADER_TYPES:
        params["modLoaderType"] = LOADER_TYPES[loader]
    data = _get(f"/mods/{int(mod_id)}/files", params, settings).get("data") or []
    return [normalize_file(f) for f in data]


# ---- modpack zip installation

_LOADER_RE = re.compile(r"^(forge|fabric|neoforge|quilt)-(.+)$", re.I)


def read_manifest(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        try:
            return json.loads(z.read("manifest.json").decode("utf-8"))
        except KeyError as e:
            raise InstallError("Это не сборка CurseForge (нет manifest.json)") from e


def is_curseforge_pack(zip_path):
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = set(z.namelist())
        return "manifest.json" in names and "modrinth.index.json" not in names
    except zipfile.BadZipFile:
        return False


def pack_info(manifest):
    mc = manifest.get("minecraft") or {}
    loader, loader_version = "vanilla", ""
    loaders = mc.get("modLoaders") or []
    primary = next((m for m in loaders if m.get("primary")), loaders[0] if loaders else None)
    if primary:
        m = _LOADER_RE.match(primary.get("id", ""))
        if m:
            loader, loader_version = m.group(1).lower(), m.group(2)
    files = [f for f in manifest.get("files") or [] if f.get("fileID") and f.get("projectID")]
    return {"name": manifest.get("name", ""), "version": manifest.get("version", ""), "mc": mc.get("version", ""),
            "loader": loader, "loader_version": loader_version, "files": files, "mods": len(files), "size": 0}


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def install_pack(zip_path, target, progress=None, cancel=None, workers=6, settings=None):
    """Install a CurseForge modpack zip into `target` (the instance's .minecraft folder). progress(stage, done,
    total). Returns pack_info()-shaped dict. Raises InstallError / net.NetError."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(zip_path)
    info = pack_info(manifest)
    cancelled = cancel or (lambda: False)
    headers = _headers(settings)
    wanted = info["files"]
    total = len(wanted)
    if progress:
        progress("files", 0, total)
    # resolve files and the kind of project each one belongs to
    file_ids = [int(f["fileID"]) for f in wanted]
    required = {int(f["fileID"]): bool(f.get("required", True)) for f in wanted}
    resolved = {}
    for part in _chunks(file_ids, 100):
        for f in _post("/mods/files", {"fileIds": part}, settings).get("data") or []:
            resolved[int(f["id"])] = f
        if cancelled():
            raise net.NetError("Отменено")
    mod_ids = sorted({int(f.get("modId")) for f in resolved.values() if f.get("modId")})
    mods = {}
    for part in _chunks(mod_ids, 100):
        for m in _post("/mods", {"modIds": part}, settings).get("data") or []:
            mods[int(m["id"])] = m
    blocked, skipped = [], []
    lock = threading.Lock()
    done = [0]
    size = [0]

    def fetch(fid):
        f = resolved.get(fid)
        if not f:
            if required.get(fid, True):
                raise InstallError(f"CurseForge не знает файл {fid}")
            return None
        mod = mods.get(int(f.get("modId") or 0), {})
        folder = CLASS_FOLDERS.get(mod.get("classId"), "mods")
        dest = _safe_join(target, f"{folder}/{f.get('fileName', '')}")
        sha1 = next((h["value"] for h in f.get("hashes") or [] if h.get("algo") == 1), None)
        if dest.exists() and sha1 and _sha1(dest) == sha1:
            return dest
        url = f.get("downloadUrl") or edge_url(fid, f.get("fileName", ""))
        try:
            net.download(url, dest, cancel=cancelled, headers=headers if url.startswith(API) else None)
            if sha1 and _sha1(dest) != sha1:
                dest.unlink(missing_ok=True)
                raise InstallError(f"Контрольная сумма не совпала: {f.get('fileName')}")
            with lock:
                size[0] += int(f.get("fileLength") or 0)
            return dest
        except net.NetError as e:
            if cancelled():
                raise
            text = str(e)
            if "403" in text or "404" in text or "Не найдено" in text:
                link = (mod.get("links") or {}).get("websiteUrl") or f"https://www.curseforge.com/projects/{f.get('modId')}"
                item = f"{mod.get('name') or f.get('fileName')} — {link}"
                with lock:
                    (blocked if required.get(fid, True) else skipped).append(item)
                return None
            raise

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = [pool.submit(fetch, fid) for fid in file_ids]
        try:
            for fut in as_completed(futures):
                fut.result()
                with lock:
                    done[0] += 1
                if progress:
                    progress("files", done[0], total)
                if cancelled():
                    raise net.NetError("Отменено")
        except BaseException:
            for fu in futures:
                fu.cancel()
            raise
    with zipfile.ZipFile(zip_path) as z:
        prefix = (manifest.get("overrides") or "overrides").strip("/") + "/"
        items = [n for n in z.namelist() if n.startswith(prefix) and not n.endswith("/")]
        for k, n in enumerate(items):
            dest = _safe_join(target, n[len(prefix):])
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(n) as src, open(dest, "wb") as out:
                out.write(src.read())
            if progress and (k % 20 == 0 or k == len(items) - 1):
                progress("overrides", k + 1, len(items))
    info["size"] = size[0]
    info["mods"] = sum(1 for p in (target / "mods").glob("*.jar")) if (target / "mods").is_dir() else info["mods"]
    info["skipped"] = skipped
    (target.parent / "eta-pack.json").write_text(json.dumps(
        {k: v for k, v in info.items() if k != "files"} | {"source": "curseforge", "installed": time.time()},
        ensure_ascii=False, indent=1), "utf-8")
    if blocked:
        raise InstallError("Автор запретил скачивание через API — скачайте вручную в папку mods:\n" +
                           "\n".join(blocked))
    return info
