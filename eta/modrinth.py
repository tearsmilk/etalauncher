"""Modrinth: search modpacks (API v2), project pages, versions, and installing a .mrpack into an instance folder
(downloading every mod listed in modrinth.index.json with sha1 checks, then the overrides).

Docs: https://docs.modrinth.com/api — search uses facets, e.g. [["project_type:modpack"],["categories:fabric"]]."""
import hashlib
import json
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from . import net

API = "https://api.modrinth.com/v2"
LOADER_KEYS = {"fabric", "forge", "neoforge", "quilt"}
SORT_INDEX = {"relevance": "relevance", "downloads": "downloads", "follows": "follows", "newest": "newest",
              "updated": "updated"}
# hosts the .mrpack format allows for file downloads (https only)
ALLOWED_HOSTS = {"cdn.modrinth.com", "github.com", "raw.githubusercontent.com", "gitlab.com"}
DEP_LOADERS = {"fabric-loader": "fabric", "forge": "forge", "neoforge": "neoforge", "quilt-loader": "quilt"}


def _ts(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _release_versions(vs):
    """Game versions newest first, only plain releases (1.20.1, 26.1 …)."""
    out = [v for v in vs or [] if all(part.isdigit() for part in v.split("."))]

    def key(v):
        return [int(x) for x in v.split(".")]

    return sorted(set(out), key=key, reverse=True)


def normalize(hit):
    cats = hit.get("categories") or []
    loaders = [c for c in cats if c in LOADER_KEYS] or [c for c in hit.get("loaders", []) if c in LOADER_KEYS]
    display = hit.get("display_categories") or [c for c in cats if c not in LOADER_KEYS]
    return {
        "project_id": hit.get("project_id") or hit.get("id"), "slug": hit.get("slug"), "title": hit.get("title"),
        "author": hit.get("author") or hit.get("organization") or "", "description": hit.get("description", ""),
        "categories": [c for c in display if c not in LOADER_KEYS], "loaders": loaders,
        "game_versions": _release_versions(hit.get("versions") or hit.get("game_versions")),
        "downloads": int(hit.get("downloads") or 0), "follows": int(hit.get("follows") or hit.get("followers") or 0),
        "date_created": _ts(hit.get("date_created") or hit.get("published") or ""),
        "date_modified": _ts(hit.get("date_modified") or hit.get("updated") or ""),
        "icon_url": hit.get("icon_url") or "", "source": "modrinth", "mods": None,
        "body": hit.get("body", ""), "url": f"https://modrinth.com/modpack/{hit.get('slug')}",
        "gallery": [g if isinstance(g, str) else g.get("url") for g in hit.get("gallery") or []],
    }


class ModrinthProvider:
    name = "modrinth"

    def __init__(self):
        self._projects = {}

    def search(self, query="", sources=(), loaders=(), version="", categories=(), sort="relevance", offset=0,
               limit=20):
        facets = [["project_type:modpack"]]
        if loaders:
            facets.append([f"categories:{lo}" for lo in loaders])
        if version:
            facets.append([f"versions:{version}"])
        for c in categories or ():
            facets.append([f"categories:{c}"])
        params = {"query": query or "", "facets": json.dumps(facets), "index": SORT_INDEX.get(sort, "relevance"),
                  "offset": int(offset), "limit": int(limit)}
        data = net.get_json(f"{API}/search", params=params)
        hits = [normalize(h) for h in data.get("hits", [])]
        for h in hits:
            self._projects.setdefault(h["slug"], h)
        return hits, int(data.get("total_hits", len(hits)))

    def project(self, slug):
        """Full project (with the description body); uses the search hit as a fallback."""
        try:
            p = normalize(net.get_json(f"{API}/project/{slug}"))
            prev = self._projects.get(slug) or {}
            p["author"] = p["author"] or prev.get("author", "")
            self._projects[slug] = p
            return p
        except net.NetError:
            return self._projects.get(slug)

    def cached(self, slug):
        return self._projects.get(slug)

    def versions(self, slug):
        data = net.get_json(f"{API}/project/{slug}/version")
        out = []
        for v in data:
            gv = _release_versions(v.get("game_versions"))
            files = v.get("files") or []
            primary = next((f for f in files if f.get("primary")), files[0] if files else None)
            out.append({
                "id": v.get("id"), "name": v.get("name") or v.get("version_number"),
                "version": v.get("version_number", ""), "mc": gv[0] if gv else "", "game_versions": gv,
                "loader": next((lo for lo in v.get("loaders", []) if lo in LOADER_KEYS), "vanilla"),
                "loaders": v.get("loaders", []), "type": v.get("version_type", "release"),
                "date": _ts(v.get("date_published", "")), "downloads": v.get("downloads", 0),
                "file": {"url": primary["url"], "filename": primary["filename"], "size": primary.get("size", 0),
                         "sha1": (primary.get("hashes") or {}).get("sha1")} if primary else None,
            })
        return out


# ---- standalone content search (mods, shaders, resourcepacks, datapacks)

def search_content(query="", project_type="mod", loaders=(), version="", offset=0, limit=20):
    """Search Modrinth for a single content type (not modpacks)."""
    facets = [[f"project_type:{project_type}"]]
    if loaders:
        facets.append([f"categories:{lo}" for lo in loaders])
    if version:
        facets.append([f"versions:{version}"])
    params = {"query": query or "", "facets": json.dumps(facets), "index": "relevance",
              "offset": int(offset), "limit": int(limit)}
    data = net.get_json(f"{API}/search", params=params)
    return [normalize(h) for h in data.get("hits", [])]


def content_versions(slug, loader="", version=""):
    """Return versions for a mod/shader/etc, filtered by loader and game version."""
    params = {}
    if loader and loader != "vanilla":
        params["loaders"] = json.dumps([loader])
    if version:
        params["game_versions"] = json.dumps([version])
    vs = net.get_json(f"{API}/project/{slug}/version", params=params) or []
    out = []
    for v in vs[:60]:
        files = v.get("files") or []
        primary = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not primary:
            continue
        gv = v.get("game_versions") or [""]
        lo = v.get("loaders") or [""]
        out.append({"name": v.get("version_number", ""),
                    "file": {"url": primary["url"],
                             "sha1": (primary.get("hashes") or {}).get("sha1", ""),
                             "filename": primary.get("filename", "")},
                    "mc": gv[0] if gv else "", "loader": lo[0] if lo else "",
                    "type": v.get("version_type", "release")})
    return out


# ---- .mrpack installation

class InstallError(Exception):
    pass


def _safe_join(root, rel):
    """root / rel, refusing absolute paths and '..' (an index or zip must not write outside the instance)."""
    rel = str(rel).replace("\\", "/")
    pp = PurePosixPath(rel)
    if pp.is_absolute() or ".." in pp.parts or not pp.parts:
        raise InstallError(f"Недопустимый путь в сборке: {rel}")
    out = (Path(root) / Path(*pp.parts)).resolve()
    if Path(root).resolve() not in out.parents and out != Path(root).resolve():
        raise InstallError(f"Недопустимый путь в сборке: {rel}")
    return out


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_index(mrpack):
    with zipfile.ZipFile(mrpack) as z:
        try:
            return json.loads(z.read("modrinth.index.json").decode("utf-8"))
        except KeyError as e:
            raise InstallError("Это не сборка Modrinth (нет modrinth.index.json)") from e


def pack_info(index):
    deps = index.get("dependencies", {})
    loader, loader_version = "vanilla", ""
    for key, name in DEP_LOADERS.items():
        if key in deps:
            loader, loader_version = name, deps[key]
            break
    files = [f for f in index.get("files", []) if (f.get("env") or {}).get("client", "required") != "unsupported"]
    mods = sum(1 for f in files if str(f.get("path", "")).startswith("mods/"))
    return {"name": index.get("name", ""), "version": index.get("versionId", ""), "mc": deps.get("minecraft", ""),
            "loader": loader, "loader_version": loader_version, "files": files, "mods": mods,
            "size": sum(int(f.get("fileSize") or 0) for f in files)}


def install_mrpack(mrpack, target, progress=None, cancel=None, workers=6, allow_hosts=None):
    """Install a .mrpack into `target` (the instance's .minecraft folder). progress(stage, done, total).
    Returns pack_info(). Raises InstallError / net.NetError."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    index = read_index(mrpack)
    info = pack_info(index)
    hosts = set(ALLOWED_HOSTS) | set(allow_hosts or ())
    files = info["files"]
    total = len(files)
    done = [0]
    lock = threading.Lock()
    cancelled = cancel or (lambda: False)

    def fetch(f):
        dest = _safe_join(target, f["path"])
        sha1 = (f.get("hashes") or {}).get("sha1")
        if dest.exists() and sha1 and _sha1(dest) == sha1:
            return dest
        last = None
        for url in f.get("downloads") or []:
            u = urlparse(url)
            local = u.hostname in (allow_hosts or ())
            if (u.scheme != "https" and not local) or u.hostname not in hosts:
                last = InstallError(f"Ссылка не из разрешённых источников: {u.hostname}")
                continue
            try:
                net.download(url, dest, cancel=cancelled)
                if sha1 and _sha1(dest) != sha1:
                    dest.unlink(missing_ok=True)
                    last = InstallError(f"Контрольная сумма не совпала: {f['path']}")
                    continue
                return dest
            except net.NetError as e:
                last = e
                if cancelled():
                    raise
        raise last or InstallError(f"Нет ссылки для {f['path']}")

    if progress:
        progress("files", 0, total)
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = [pool.submit(fetch, f) for f in files]
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
    # overrides: common first, client-specific on top
    with zipfile.ZipFile(mrpack) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        for prefix in ("overrides/", "client-overrides/"):
            items = [n for n in names if n.startswith(prefix)]
            for k, n in enumerate(items):
                dest = _safe_join(target, n[len(prefix):])
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, open(dest, "wb") as out:
                    out.write(src.read())
                if progress and (k % 20 == 0 or k == len(items) - 1):
                    progress("overrides", k + 1, len(items))
    (target.parent / "eta-pack.json").write_text(json.dumps(
        {k: v for k, v in info.items() if k != "files"} | {"installed": time.time()}, ensure_ascii=False, indent=1),
        "utf-8")
    return info
