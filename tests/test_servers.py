"""Community servers: the Server List Ping against a fake Minecraft server on a socket, MOTD § codes, the launch
command with a server (--quickPlayMultiplayer for 1.20+, --server/--port before), the server list fetch + cache and
the update check against a local fake of mc-ru.org. No Qt. Run: `python -m tests.test_servers` from eta/."""
import base64
import http.server
import json
import socket
import struct
import tempfile
import threading
from pathlib import Path

STATUS = {"version": {"name": "Paper 1.20.1", "protocol": 763},
          "players": {"online": 12, "max": 100, "sample": []},
          "description": {"text": "", "extra": [{"text": "Ферма", "color": "green", "bold": True},
                                                 {"text": " — выживание", "color": "gray"}]},
          "favicon": "data:image/png;base64," + base64.b64encode(b"\x89PNG fake").decode()}


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


def _read_varint(sock):
    n = shift = 0
    while True:
        b = sock.recv(1)[0]
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n
        shift += 7


def fake_minecraft():
    """A socket server answering one status request per connection. Returns (host, port, seen)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    seen = []

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            with conn:
                conn.settimeout(3)
                try:
                    ln = _read_varint(conn)
                    pkt = conn.recv(ln)
                    # packet id 0, protocol varint, host string, port, next state
                    assert pkt[0] == 0
                    pos = 1
                    while pkt[pos] & 0x80:
                        pos += 1
                    pos += 1
                    hl = pkt[pos]
                    host = pkt[pos + 1:pos + 1 + hl].decode()
                    port = struct.unpack(">H", pkt[pos + 1 + hl:pos + 3 + hl])[0]
                    seen.append((host, port))
                    _read_varint(conn)          # status request length
                    conn.recv(1)
                    body = json.dumps(STATUS).encode()
                    payload = b"\x00" + _varint(len(body)) + body
                    conn.sendall(_varint(len(payload)) + payload)
                except (OSError, AssertionError, IndexError):
                    pass

    threading.Thread(target=serve, daemon=True).start()
    return "127.0.0.1", srv.getsockname()[1], seen, srv


class FakeSite(http.server.BaseHTTPRequestHandler):
    servers = [{"id": 2, "name": "Ферма", "ip": "play.example.org:25566", "port": 25565, "version": "1.20.1",
                "motd": "§aФерма §7— выживание", "icon_url": None, "sort": 2},
               {"id": 1, "name": "Лобби", "ip": "lobby.example.org", "port": 25565, "version": "1.21",
                "motd": "Lobby", "icon_url": "http://x/icon.png", "sort": 1}]
    version = {"version": "1.2.0", "windows": "http://x/Eta.exe", "macos": "http://x/Eta.dmg"}

    def do_GET(self):
        data = {"servers": self.servers} if self.path == "/api/servers" else self.version
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def run(tmp=None):
    import os

    tmp = Path(tmp or tempfile.mkdtemp())
    os.environ.setdefault("ETA_DATA", str(tmp))
    from eta import launch, servers, updates

    calls = 0
    # ping
    host, port, seen, sock = fake_minecraft()
    st = servers.ping(host, port, timeout=3)
    sock.close()
    assert seen == [(host, port)], seen
    assert st["online"] == 12 and st["max"] == 100 and st["version"] == "Paper 1.20.1" and st["protocol"] == 763
    assert st["motd"] == "§a§lФерма§7 — выживание" and st["favicon"] == b"\x89PNG fake" and st["latency_ms"] >= 0
    calls += 1
    free = socket.socket()
    free.bind(("127.0.0.1", 0))
    closed_port = free.getsockname()[1]
    free.close()
    try:
        servers.ping("127.0.0.1", closed_port, timeout=0.5)
        raise AssertionError("ping to a closed port must fail")
    except OSError:
        calls += 1
    # motd
    rich = servers.motd_to_rich("§aФерма §l— §rвыживание <1>")
    assert 'color:#55FF55' in rich and "font-weight:600" in rich and "&lt;1&gt;" in rich and "§" not in rich
    assert servers.motd_plain("§a§lX§r y") == "X y"
    assert servers.version_matches("1.20.1", "1.20") and servers.version_matches("1.20", "1.20.1")
    assert servers.version_matches("1.21", "") and not servers.version_matches("1.19.2", "1.20.1")
    calls += 1
    # list + cache
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeSite)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    items = servers.fetch(base + "/api/servers")
    assert [s["name"] for s in items] == ["Лобби", "Ферма"]
    assert items[1]["ip"] == "play.example.org" and items[1]["port"] == 25566
    assert servers.address(items[1]) == "play.example.org:25566" and servers.address(items[0]) == "lobby.example.org"
    assert [s["name"] for s in servers.cached()] == ["Лобби", "Ферма"]
    calls += 1
    # update check
    assert updates.parse_version("1.2.0") == (1, 2, 0) and updates.is_newer("1.2.0", "1.1.9")
    assert not updates.is_newer("1.0.0", "1.0.0") and not updates.is_newer("", "1.0.0")
    st_ = {}
    class S(dict):
        def save(self):
            st_["saved"] = True
    s = S()
    res = updates.check(s, url=base + "/api/launcher/version")
    assert res["version"] == "1.2.0" and res["newer"] and res["url"].endswith((".exe", ".dmg")) and st_["saved"]
    assert updates.check(s, url="http://127.0.0.1:1/nope")["version"] == "1.2.0"   # cached, no request
    assert updates.check(s, force=True, url="http://127.0.0.1:1/nope") is None
    httpd.shutdown()
    calls += 1
    # launch command with a server
    assert launch.supports_quick_play("1.20") and launch.supports_quick_play("1.21.1") and \
        launch.supports_quick_play("24w10a") and not launch.supports_quick_play("1.19.4") and \
        not launch.supports_quick_play("1.8.9")
    g = launch.Game(tmp / "mc", tmp / "java")
    acc = {"name": "Steve", "uuid": "b50ad385-829d-3141-a216-7e7d7539ba7f", "type": "offline"}
    settings = {"memory_mb": 1024}
    modern = {"id": "1.20.1", "mainClass": "net.minecraft.client.main.Main", "assetIndex": {"id": "5"},
              "arguments": {"jvm": ["-cp", "${classpath}"],
                            "game": ["--username", "${auth_player_name}",
                                     {"rules": [{"action": "allow", "features": {"is_quick_play_multiplayer": True}}],
                                      "value": ["--quickPlayMultiplayer", "${quickPlayMultiplayer}"]}]}}
    server = {"ip": "play.example.org", "port": 25566, "name": "Ферма"}
    cmd = g.command(modern, "java", tmp / "g", acc, settings, tmp / "n", [tmp / "a.jar"], None,
                    {"mc_version": "1.20.1"}, server=server)
    assert cmd[cmd.index("--quickPlayMultiplayer") + 1] == "play.example.org:25566" and "--server" not in cmd
    cmd = g.command(modern, "java", tmp / "g", acc, settings, tmp / "n", [tmp / "a.jar"], None,
                    {"mc_version": "1.20.1"})
    assert "--quickPlayMultiplayer" not in cmd
    legacy = {"id": "1.12.2", "mainClass": "net.minecraft.client.main.Main", "assets": "1.12",
              "minecraftArguments": "--username ${auth_player_name} --version ${version_name}"}
    cmd = g.command(legacy, "java", tmp / "g", acc, settings, tmp / "n", [tmp / "a.jar"], None,
                    {"mc_version": "1.12.2"}, server=server)
    assert cmd[cmd.index("--server") + 1] == "play.example.org" and cmd[cmd.index("--port") + 1] == "25566"
    assert "--quickPlayMultiplayer" not in cmd
    calls += 1
    return {"calls": calls}


if __name__ == "__main__":
    print("servers ok", run())
