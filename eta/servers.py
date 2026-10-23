"""Community servers from mc-ru.org (GET /api/servers, cached on disk so the page works offline) and the
Minecraft Server List Ping (modern protocol: handshake → status request → JSON) to show who is online."""
import base64
import html
import json
import socket
import struct
import time

from . import mcru, net
from .paths import data_dir, load_json, save_json

SERVERS_URL = mcru.SITE + "/api/servers"
PROTOCOL = 767   # 1.21; any value works for a status request

COLORS = {"0": "#000000", "1": "#0000AA", "2": "#00AA00", "3": "#00AAAA", "4": "#AA0000", "5": "#AA00AA",
          "6": "#FFAA00", "7": "#AAAAAA", "8": "#555555", "9": "#5555FF", "a": "#55FF55", "b": "#55FFFF",
          "c": "#FF5555", "d": "#FF55FF", "e": "#FFFF55", "f": "#FFFFFF"}
NAMED = {n: c for c, n in zip("0123456789abcdef", (
    "black", "dark_blue", "dark_green", "dark_aqua", "dark_red", "dark_purple", "gold", "gray", "dark_gray", "blue",
    "green", "aqua", "red", "light_purple", "yellow", "white"))}
NAMED.update({v.upper(): k for k, v in COLORS.items()})


def _cache_file():
    return data_dir() / "servers.json"


def cached():
    data = load_json(_cache_file(), {})
    return list(data.get("servers") or [])


def fetch(url=None):
    """Servers from the site; saved to the cache on success."""
    data = net.get_json(url or SERVERS_URL)
    servers = [normalize(s) for s in data.get("servers") or []]
    servers.sort(key=lambda s: (s.get("sort") or 0, s["name"].lower()))
    try:
        save_json(_cache_file(), {"servers": servers, "fetched": time.time()})
    except OSError:
        pass
    return servers


def normalize(s):
    ip = str(s.get("ip") or "").strip()
    port = int(s.get("port") or 25565)
    if ":" in ip and not ip.startswith("["):
        host, _, p = ip.rpartition(":")
        if p.isdigit():
            ip, port = host, int(p)
    return {"id": s.get("id"), "name": str(s.get("name") or ip), "ip": ip, "port": port,
            "version": str(s.get("version") or ""), "motd": str(s.get("motd") or ""),
            "icon_url": s.get("icon_url") or None, "sort": int(s.get("sort") or 0)}


def address(s):
    return s["ip"] if s.get("port", 25565) == 25565 else f"{s['ip']}:{s['port']}"


# ---- server list ping

def _varint(n):
    out = bytearray()
    n &= 0xFFFFFFFF
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _read_varint(sock):
    n = shift = 0
    while True:
        b = sock.recv(1)
        if not b:
            raise OSError("Сервер оборвал соединение")
        n |= (b[0] & 0x7F) << shift
        if not b[0] & 0x80:
            return n
        shift += 7
        if shift > 35:
            raise OSError("Неверный ответ сервера")


def _packet(pid, payload):
    body = _varint(pid) + payload
    return _varint(len(body)) + body


def _recv(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(65536, n - len(buf)))
        if not chunk:
            raise OSError("Сервер оборвал соединение")
        buf += chunk
    return bytes(buf)


def description_text(d):
    """Plain text of a chat component (string, {"text","extra"} tree or list)."""
    if d is None:
        return ""
    if isinstance(d, str):
        return d
    if isinstance(d, list):
        return "".join(description_text(x) for x in d)
    if isinstance(d, dict):
        out = ""
        color = str(d.get("color") or "")
        code = NAMED.get(color) or NAMED.get(color.upper(), "")
        if code:
            out += "§" + code
        for key, c in (("bold", "l"), ("italic", "o"), ("underlined", "n"), ("strikethrough", "m")):
            if d.get(key):
                out += "§" + c
        out += str(d.get("text") or "")
        out += "".join(description_text(x) for x in d.get("extra") or [])
        return out
    return str(d)


def ping(host, port=25565, timeout=3.0):
    """Status of a Minecraft server → {online, max, version, protocol, motd, favicon (bytes|None), latency_ms}.
    Raises OSError when unreachable."""
    t0 = time.monotonic()
    with socket.create_connection((host, int(port)), timeout=timeout) as sock:
        sock.settimeout(timeout)
        h = host.encode("utf-8")
        handshake = _varint(PROTOCOL) + _varint(len(h)) + h + struct.pack(">H", int(port)) + _varint(1)
        sock.sendall(_packet(0, handshake) + _packet(0, b""))
        length = _read_varint(sock)
        if length <= 0 or length > 1 << 22:
            raise OSError("Неверный ответ сервера")
        data = _recv(sock, length)
        latency = int((time.monotonic() - t0) * 1000)
    # packet id, then a string (VarInt length + utf-8)
    pos = 0
    pid, shift = 0, 0
    while True:
        b = data[pos]
        pos += 1
        pid |= (b & 0x7F) << shift
        if not b & 0x80:
            break
        shift += 7
    if pid != 0:
        raise OSError("Неверный ответ сервера")
    slen, shift = 0, 0
    while True:
        b = data[pos]
        pos += 1
        slen |= (b & 0x7F) << shift
        if not b & 0x80:
            break
        shift += 7
    try:
        status = json.loads(data[pos:pos + slen].decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise OSError("Сервер прислал не JSON") from e
    players = status.get("players") or {}
    version = status.get("version") or {}
    favicon = None
    fav = status.get("favicon")
    if isinstance(fav, str) and fav.startswith("data:image/png;base64,"):
        try:
            favicon = base64.b64decode(fav.split(",", 1)[1])
        except (ValueError, IndexError):
            favicon = None
    return {"online": int(players.get("online") or 0), "max": int(players.get("max") or 0),
            "version": str(version.get("name") or ""), "protocol": int(version.get("protocol") or 0),
            "motd": description_text(status.get("description")), "favicon": favicon, "latency_ms": latency}


# ---- MOTD (§ codes)

def motd_plain(text):
    out, i = [], 0
    text = text or ""
    while i < len(text):
        if text[i] == "§" and i + 1 < len(text):
            i += 2
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def motd_to_rich(text, default_color=None):
    """§-formatted text → Qt rich text (HTML). Unknown codes are dropped; newlines become <br>."""
    text = text or ""
    color, bold, italic, underline, strike = None, False, False, False, False
    parts, buf = [], []

    def flush():
        if not buf:
            return
        s = html.escape("".join(buf)).replace("\n", "<br>")
        buf.clear()
        styles = []
        if color:
            styles.append(f"color:{color}")
        if bold:
            styles.append("font-weight:600")
        if italic:
            styles.append("font-style:italic")
        deco = [d for d, on in (("underline", underline), ("line-through", strike)) if on]
        if deco:
            styles.append("text-decoration:" + " ".join(deco))
        parts.append(f'<span style="{";".join(styles)}">{s}</span>' if styles else s)

    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "§" and i + 1 < len(text):
            code = text[i + 1].lower()
            flush()
            if code in COLORS:
                color, bold, italic, underline, strike = COLORS[code], False, False, False, False
            elif code == "l":
                bold = True
            elif code == "o":
                italic = True
            elif code == "n":
                underline = True
            elif code == "m":
                strike = True
            elif code == "r":
                color, bold, italic, underline, strike = None, False, False, False, False
            i += 2
            continue
        buf.append(ch)
        i += 1
    flush()
    out = "".join(parts)
    return f'<span style="color:{default_color}">{out}</span>' if default_color else out


def version_matches(inst_version, server_version):
    """'1.20.1' vs '1.20' → True; empty server version → True."""
    sv = (server_version or "").strip()
    iv = (inst_version or "").strip()
    if not sv or not iv:
        return True
    a, b = iv.split("."), sv.split(".")
    n = min(len(a), len(b))
    return a[:n] == b[:n]
