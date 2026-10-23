"""Microsoft (licensed) accounts: OAuth device-code flow → Xbox Live → XSTS → Minecraft services. The result is
the same thing the official launcher gets: a Minecraft access token (`user_type` msa), the profile UUID and name.

CLIENT_ID is the Application (client) ID of an Azure / Entra app registration: «Mobile and desktop applications»
platform with redirect https://login.microsoftonline.com/common/oauth2/nativeclient, «Allow public client flows» = Yes,
supported account types «Personal Microsoft accounts». Mojang additionally has to approve the ID for
api.minecraftservices.com — the form is https://aka.ms/mce-reviewappid; until then login_with_xbox answers 403.
Set it via the ETA_MSA_CLIENT_ID environment variable or paste it below (see eta/README.md).

No Qt in here — called from worker threads and from launch.py."""
import os
import time

from . import net

CLIENT_ID = os.environ.get("ETA_MSA_CLIENT_ID") or ""
SCOPE = "XboxLive.signin offline_access"
DEVICE_CODE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
XBL_URL = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
MC_LOGIN_URL = "https://api.minecraftservices.com/authentication/login_with_xbox"
MC_STORE_URL = "https://api.minecraftservices.com/entitlements/mcstore"
MC_PROFILE_URL = "https://api.minecraftservices.com/minecraft/profile"
HEAD_URL = "https://crafatar.com/avatars/{uuid}?size=64&overlay"

XERR = {
    2148916233: "У этого аккаунта Microsoft нет профиля Xbox — создайте его на xbox.com и войдите снова",
    2148916235: "Xbox Live недоступен в стране этого аккаунта",
    2148916236: "Аккаунту нужна проверка возраста на xbox.com",
    2148916237: "Аккаунту нужна проверка возраста на xbox.com",
    2148916238: "Детский аккаунт: взрослый должен добавить его в семью Microsoft на account.microsoft.com/family",
}

REFRESH_MARGIN = 300   # seconds before mc_expires when we refresh


class MsaError(net.NetError):
    pass


class Cancelled(MsaError):
    pass


def available():
    return bool(CLIENT_ID)


def head_url(uuid_):
    return HEAD_URL.format(uuid=(uuid_ or "").replace("-", ""))


def _dashed(uid):
    uid = (uid or "").replace("-", "")
    return f"{uid[:8]}-{uid[8:12]}-{uid[12:16]}-{uid[16:20]}-{uid[20:]}" if len(uid) == 32 else uid


def _need(status, data, what):
    if status >= 400 or not isinstance(data, dict):
        desc = (data or {}).get("error_description") or (data or {}).get("error") if isinstance(data, dict) else ""
        raise MsaError(f"{what}: {desc or f'HTTP {status}'}")
    return data


# -- 1. Microsoft identity platform: device code

def request_device_code():
    """→ {"user_code", "device_code", "verification_uri", "interval", "expires_in", "message"}."""
    if not CLIENT_ID:
        raise MsaError("Вход через Microsoft не настроен: нет Client ID приложения (см. README)")
    st, d = net.post_form(DEVICE_CODE_URL, {"client_id": CLIENT_ID, "scope": SCOPE})
    d = _need(st, d, "Microsoft не выдал код устройства")
    if not d.get("device_code") or not d.get("user_code"):
        raise MsaError("Microsoft вернул неполный ответ на запрос кода")
    d.setdefault("verification_uri", "https://www.microsoft.com/link")
    d.setdefault("interval", 5)
    d.setdefault("expires_in", 900)
    return d


def poll_token(code, cancel=None):
    """Wait until the user confirms the code in the browser. → {"access_token", "refresh_token", "expires_in"}."""
    interval = int(code.get("interval") or 5)
    deadline = time.monotonic() + int(code.get("expires_in") or 900)
    cancel = cancel or (lambda: False)
    while True:
        if cancel():
            raise Cancelled("Вход отменён")
        if time.monotonic() > deadline:
            raise MsaError("Код устарел — попробуйте войти ещё раз")
        st, d = net.post_form(TOKEN_URL, {"client_id": CLIENT_ID, "device_code": code["device_code"],
                                          "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        d = d if isinstance(d, dict) else {}
        if st < 400 and d.get("access_token"):
            return d
        err = d.get("error", "")
        if err == "authorization_pending":
            pass
        elif err == "slow_down":
            interval += 5
        elif err == "expired_token":
            raise MsaError("Код устарел — попробуйте войти ещё раз")
        elif err == "authorization_declined":
            raise MsaError("Вход отклонён в окне Microsoft")
        else:
            raise MsaError(f"Microsoft: {d.get('error_description') or err or f'HTTP {st}'}")
        # short sleeps so cancel() is noticed quickly
        end = time.monotonic() + interval
        while time.monotonic() < end:
            if cancel():
                raise Cancelled("Вход отменён")
            time.sleep(0.25)


def refresh_ms_token(refresh_token):
    st, d = net.post_form(TOKEN_URL, {"client_id": CLIENT_ID, "refresh_token": refresh_token,
                                      "grant_type": "refresh_token", "scope": SCOPE})
    d = _need(st, d, "Не удалось продлить вход Microsoft")
    if not d.get("access_token"):
        raise MsaError("Microsoft не вернул новый токен — войдите заново")
    return d


# -- 2. Xbox Live → XSTS → Minecraft

def xbox_live(ms_access_token):
    st, d = net.call_json("POST", XBL_URL, {
        "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com",
                       "RpsTicket": f"d={ms_access_token}"},
        "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"})
    d = _need(st, d, "Xbox Live не принял вход")
    try:
        return d["Token"], d["DisplayClaims"]["xui"][0]["uhs"]
    except (KeyError, IndexError, TypeError) as e:
        raise MsaError("Xbox Live вернул неполный ответ") from e


def xsts(xbl_token):
    st, d = net.call_json("POST", XSTS_URL, {
        "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
        "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"})
    if st == 401 and isinstance(d, dict):
        xerr = int(d.get("XErr") or 0)
        raise MsaError(XERR.get(xerr, f"Xbox отказал во входе (XErr {xerr})"))
    d = _need(st, d, "XSTS не выдал токен")
    try:
        xui = d["DisplayClaims"]["xui"][0]
        return d["Token"], xui["uhs"], xui.get("xid", "")
    except (KeyError, IndexError, TypeError) as e:
        raise MsaError("XSTS вернул неполный ответ") from e


def minecraft_login(uhs, xsts_token):
    st, d = net.call_json("POST", MC_LOGIN_URL, {"identityToken": f"XBL3.0 x={uhs};{xsts_token}"})
    if st == 403:
        raise MsaError("Приложение ещё не одобрено Mojang для входа в Minecraft (см. README, форма "
                       "aka.ms/mce-reviewappid)")
    d = _need(st, d, "Minecraft не принял вход через Xbox")
    if not d.get("access_token"):
        raise MsaError("Minecraft не вернул токен")
    return d["access_token"], int(d.get("expires_in") or 86400)


def minecraft_profile(mc_token):
    hdr = {"Authorization": f"Bearer {mc_token}"}
    st, d = net.call_json("GET", MC_STORE_URL, headers=hdr)
    if st < 400 and isinstance(d, dict) and not d.get("items"):
        raise MsaError("На этом аккаунте нет Minecraft: Java Edition")
    st, d = net.call_json("GET", MC_PROFILE_URL, headers=hdr)
    if st == 404:
        raise MsaError("У аккаунта нет профиля Minecraft — запустите официальный лаунчер и придумайте ник")
    d = _need(st, d, "Не удалось получить профиль Minecraft")
    if not d.get("id") or not d.get("name"):
        raise MsaError("Профиль Minecraft без ника или UUID")
    return d


def _chain(ms_tokens):
    """MS access token → the account fields the launcher stores."""
    xbl, _uhs = xbox_live(ms_tokens["access_token"])
    xs, uhs, xuid = xsts(xbl)
    mc_token, ttl = minecraft_login(uhs, xs)
    prof = minecraft_profile(mc_token)
    return {"name": prof["name"], "uuid": _dashed(prof["id"]), "mc_token": mc_token,
            "mc_expires": time.time() + ttl, "refresh_token": ms_tokens.get("refresh_token", ""), "xuid": xuid}


def login_device_code(on_code=None, cancel=None):
    """Whole sign-in. on_code(user_code, verification_uri, message) fires once the code is ready; cancel() → True
    aborts the wait. Returns {name, uuid, mc_token, mc_expires, refresh_token, xuid}."""
    code = request_device_code()
    if on_code:
        on_code(code["user_code"], code["verification_uri"], code.get("message", ""))
    tokens = poll_token(code, cancel)
    return _chain(tokens)


def refresh(refresh_token):
    """New Minecraft session from a stored MS refresh token."""
    if not refresh_token:
        raise MsaError("Сессия Microsoft истекла — войдите в аккаунт заново")
    tokens = refresh_ms_token(refresh_token)
    out = _chain(tokens)
    out["refresh_token"] = tokens.get("refresh_token") or refresh_token
    return out


def ensure_session(acc):
    """Refresh when the Minecraft token is (nearly) expired; mutates and returns acc for saving."""
    if acc.get("mc_token") and float(acc.get("mc_expires") or 0) - time.time() > REFRESH_MARGIN:
        return acc
    try:
        acc.update(refresh(acc.get("refresh_token", "")))
    except net.NetError as e:
        raise net.NetError(f"Сессия Microsoft истекла — войдите в аккаунт заново ({e})") from e
    return acc
