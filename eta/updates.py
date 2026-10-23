"""Launcher update check against mc-ru.org (GET /api/launcher/version → {version, windows, macos})."""
import re
import sys
import time

from . import __version__, mcru, net

VERSION_URL = mcru.SITE + "/api/launcher/version"
CACHE_SECONDS = 6 * 3600


def parse_version(s):
    nums = re.findall(r"\d+", str(s or ""))
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(remote, local=__version__):
    return parse_version(remote) > parse_version(local)


def platform_url(info):
    key = "windows" if sys.platform == "win32" else "macos"
    return info.get(key) or info.get("macos") or info.get("windows") or ""


def check(settings=None, force=False, url=None):
    """→ {"version", "url", "newer"} (None when the site is unreachable). Cached in settings for 6 h."""
    now = time.time()
    if settings is not None and not force and now - float(settings.get("update_checked") or 0) < CACHE_SECONDS:
        v = settings.get("update_version") or ""
        return {"version": v, "url": settings.get("update_url") or "", "newer": is_newer(v)} if v else None
    try:
        info = net.get_json(url or VERSION_URL, timeout=10)
    except net.NetError:
        return None
    v = str(info.get("version") or "")
    res = {"version": v, "url": platform_url(info), "newer": bool(v) and is_newer(v)}
    if settings is not None:
        settings.update(update_checked=now, update_version=v, update_url=res["url"])
        settings.save()
    return res if v else None
