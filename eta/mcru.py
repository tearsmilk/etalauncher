"""mc-ru.org accounts: the community site runs a Yggdrasil-compatible auth server (authlib-injector spec), so the
game signs in with the site account and gets the player's skin and cape. HD and animated textures come through
CustomSkinLoader's CustomSkinAPI (`CSL_ROOT`); vanilla without mods gets the standard 64×64 first frame.

No Qt in here — called from worker threads and from launch.py."""
import hashlib
import uuid as _uuid
from pathlib import Path

from . import net

SITE = "https://mc-ru.org"
YGGDRASIL = SITE + "/api/yggdrasil"
CSL_ROOT = SITE + "/api/csl/"
INJECTOR_LATEST = "https://authlib-injector.yushi.moe/artifact/latest.json"
AGENT = {"name": "Minecraft", "version": 1}


def new_client_token():
    return _uuid.uuid4().hex


def _dashed(uid):
    uid = (uid or "").replace("-", "")
    return str(_uuid.UUID(uid)) if len(uid) == 32 else uid


def authenticate(login, password, client_token=None):
    """→ {"name", "uuid" (dashed), "access_token", "client_token"}; NetError with the server's message on failure."""
    client_token = client_token or new_client_token()
    r = net.post_json(f"{YGGDRASIL}/authserver/authenticate",
                      {"username": login, "password": password, "clientToken": client_token, "agent": AGENT,
                       "requestUser": False}) or {}
    prof = r.get("selectedProfile") or (r.get("availableProfiles") or [{}])[0]
    if not r.get("accessToken") or not prof.get("id"):
        raise net.NetError("Сервер mc-ru.org вернул неполный ответ")
    return {"name": prof.get("name", login), "uuid": _dashed(prof["id"]), "access_token": r["accessToken"],
            "client_token": r.get("clientToken") or client_token}


def refresh(access_token, client_token):
    r = net.post_json(f"{YGGDRASIL}/authserver/refresh",
                      {"accessToken": access_token, "clientToken": client_token, "requestUser": False}) or {}
    if not r.get("accessToken"):
        raise net.NetError("Не удалось продлить сессию mc-ru.org")
    prof = r.get("selectedProfile") or {}
    out = {"access_token": r["accessToken"], "client_token": r.get("clientToken") or client_token}
    if prof.get("id"):
        out["uuid"] = _dashed(prof["id"])
    if prof.get("name"):
        out["name"] = prof["name"]
    return out


def validate(access_token, client_token):
    """True when the token is still good (204), False on 403; other errors propagate."""
    try:
        net.post_json(f"{YGGDRASIL}/authserver/validate",
                      {"accessToken": access_token, "clientToken": client_token})
        return True
    except net.NetError as e:
        if getattr(e, "status", 0) in (401, 403):
            return False
        raise


def invalidate(access_token, client_token):
    try:
        net.post_json(f"{YGGDRASIL}/authserver/invalidate",
                      {"accessToken": access_token, "clientToken": client_token})
    except net.NetError:
        pass


def profile(name):
    return net.get_json(f"{SITE}/api/users/{name}")


def head_url(name):
    return f"{SITE}/api/users/{name}/skin.png?frame=0&size=64"


def authlib_injector(cache_dir, progress=None):
    """Newest authlib-injector jar (sha256-checked, cached in cache_dir). progress(done, total) while downloading."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    info = net.get_json(INJECTOR_LATEST)
    version = str(info.get("version") or "latest")
    url = info.get("download_url")
    sha256 = ((info.get("checksums") or {}).get("sha256") or "").lower()
    if not url:
        raise net.NetError("authlib-injector: нет ссылки на загрузку")
    dest = cache_dir / f"authlib-injector-{version}.jar"
    if dest.exists() and (not sha256 or _sha256(dest) == sha256):
        return dest
    net.download(url, dest, progress=progress)
    if sha256 and _sha256(dest) != sha256:
        dest.unlink(missing_ok=True)
        raise net.NetError("authlib-injector: контрольная сумма не совпала")
    for old in cache_dir.glob("authlib-injector-*.jar"):
        if old != dest:
            old.unlink(missing_ok=True)
    return dest


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


CSL_ENTRY = {"name": "mc-ru.org", "type": "CustomSkinAPI", "root": CSL_ROOT}
CSL_CONFIG = {"version": "14.0", "enable": True, "loadlist": [CSL_ENTRY, {"name": "Mojang", "type": "MojangAPI"}],
              "enableDynamicSkull": True, "enableTransparentSkin": True, "forceIgnoreHttpsCertificate": False,
              "enableLocalProfileCache": False, "enableCacheAutoClean": True, "enableLogStdOut": False,
              "cacheExpiry": 30, "forceUpdateSkull": False, "enableSkull": True, "threadPoolSize": 8,
              "retryTime": 1, "forceDisableCache": False}
