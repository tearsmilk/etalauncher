"""System mod rurukaSuka against a local fake of mc-ru.org (`/api/launcher/mod` + jar) and a fake Modrinth
(Fabric API): install into mods/, tracker, launcher session json per account type, removal on toggle (user jars
untouched), unsupported version, GitHub fallback. No Qt. Run: `python -m tests.test_sysmods` from eta/."""
import hashlib
import http.server
import json
import tempfile
import threading
from pathlib import Path

JAR = b"PK\x03\x04 rurukasuka fake jar"
JAR2 = b"PK\x03\x04 rurukasuka fake jar v2"
FAPI = b"PK\x03\x04 fabric api fake jar"


class Fake(http.server.BaseHTTPRequestHandler):
    calls = []
    site_down = False
    version = "0.1.0"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Fake.calls.append(self.path)
        base = f"http://127.0.0.1:{self.server.server_address[1]}"
        jar = JAR if Fake.version == "0.1.0" else JAR2
        meta = {"version": Fake.version, "mc_versions": ["1.21.11"], "loaders": ["fabric", "quilt"],
                "requires": [{"modrinth": "fabric-api"}]}
        if self.path == "/api/launcher/mod":
            if Fake.site_down:
                return self._send(503, {"error": "down"})
            return self._send(200, meta | {"jar": {"url": f"{base}/jar", "name": f"rurukasuka-{Fake.version}.jar",
                                                   "size": len(jar), "sha256": hashlib.sha256(jar).hexdigest()}})
        if self.path.startswith("/releases"):
            return self._send(200, [{"tag_name": "eta-v1.0.0", "draft": False, "assets": []},
                                    {"tag_name": f"rurukasuka-v{Fake.version}", "draft": False, "assets": [
                                        {"name": "rurukasuka-mod.json", "browser_download_url": f"{base}/meta.json"},
                                        {"name": f"rurukasuka-{Fake.version}.jar", "browser_download_url": f"{base}/jar",
                                         "size": len(jar), "digest": "sha256:" + hashlib.sha256(jar).hexdigest()}]}])
        if self.path == "/meta.json":
            return self._send(200, meta)
        if self.path == "/jar":
            return self._send(200, jar, "application/java-archive")
        if self.path.startswith("/v2/project/fabric-api/version"):
            return self._send(200, [{"version_number": "0.141.6+1.21.11", "version_type": "release",
                                     "game_versions": ["1.21.11"], "loaders": ["fabric"],
                                     "files": [{"primary": True, "url": f"{base}/fapi", "filename": "fabric-api-0.141.6+1.21.11.jar",
                                                "hashes": {"sha1": hashlib.sha1(FAPI).hexdigest()}}]}])
        if self.path == "/fapi":
            return self._send(200, FAPI, "application/java-archive")
        self._send(404, {"error": "nope"})


def serve():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


class _Game:
    def __init__(self):
        self.lines = []

    def log(self, s):
        self.lines.append(s)


def run(tmp=None):
    import os

    from eta import mcru, modrinth, sysmods

    tmp = Path(tmp or tempfile.mkdtemp())
    prev_data = os.environ.get("ETA_DATA")
    os.environ["ETA_DATA"] = str(tmp / "data")
    httpd, base = serve()
    saved = mcru.SITE, modrinth.API, sysmods.GITHUB_RELEASES, sysmods.CACHE_TTL
    mcru.SITE, modrinth.API, sysmods.GITHUB_RELEASES = base, base + "/v2", base + "/releases"
    sysmods.CACHE_TTL = 0
    Fake.calls.clear()
    Fake.site_down = False
    Fake.version = "0.1.0"
    mc = tmp / "sysmods-inst" / ".minecraft"
    mods = mc / "mods"
    mods.mkdir(parents=True, exist_ok=True)
    (mods / "sodium.jar").write_bytes(b"user mod")
    inst = {"id": "i1", "mc_version": "1.21.11", "loader": "fabric"}
    settings = {"rurukasuka": True}
    acc = {"type": "mcru", "name": "Hoka", "access_token": "jwt-123"}
    try:
        g = _Game()
        assert sysmods.ensure_rurukasuka(g, inst, mc, settings, acc) is True, g.lines
        assert (mods / "rurukasuka-0.1.0.jar").read_bytes() == JAR
        assert (mods / "fabric-api-0.141.6+1.21.11.jar").read_bytes() == FAPI
        tracker = json.loads((mc / sysmods.TRACKER).read_text("utf-8"))
        assert tracker["rurukasuka"]["version"] == "0.1.0" and tracker["fabric-api"]["file"].startswith("fabric-api")
        sess = json.loads((mc / sysmods.LAUNCHER_JSON).read_text("utf-8"))
        assert sess == {"token": "jwt-123", "site": base, "nick": "Hoka"}
        assert sysmods.managed_files(mc) == {"rurukasuka-0.1.0.jar", "fabric-api-0.141.6+1.21.11.jar"}
        # second run: cached jar, no re-download, Fabric API already there
        n = len(Fake.calls)
        assert sysmods.ensure_rurukasuka(g, inst, mc, settings, acc) is True
        assert "/jar" not in Fake.calls[n:] and "/fapi" not in Fake.calls[n:]
        # offline account → empty token; still installed
        assert sysmods.ensure_rurukasuka(g, inst, mc, settings, {"type": "offline", "name": "Steve"})
        assert json.loads((mc / sysmods.LAUNCHER_JSON).read_text("utf-8"))["token"] == ""
        # a new release replaces the old jar
        Fake.version = "0.2.0"
        assert sysmods.ensure_rurukasuka(g, inst, mc, settings, acc)
        assert not (mods / "rurukasuka-0.1.0.jar").exists() and (mods / "rurukasuka-0.2.0.jar").read_bytes() == JAR2
        # site down → GitHub releases fallback
        Fake.site_down = True
        (tmp / "data" / "sysmods.json").unlink()
        inf = sysmods.info(force=True)
        assert inf and inf["version"] == "0.2.0" and inf["jar"]["sha256"] == hashlib.sha256(JAR2).hexdigest()
        Fake.site_down = False
        # per-instance toggle off → our jar gone, user jar and Fabric API (other mods may need it) stay
        assert sysmods.ensure_rurukasuka(g, inst | {"rurukasuka": False}, mc, settings, acc) is False
        assert not (mods / "rurukasuka-0.2.0.jar").exists() and (mods / "sodium.jar").exists()
        assert (mods / "fabric-api-0.141.6+1.21.11.jar").exists() and not (mc / sysmods.LAUNCHER_JSON).exists()
        assert json.loads((mc / sysmods.TRACKER).read_text("utf-8")).keys() == {"fabric-api"}
        # alone in mods/ → Fabric API is ours to remove too
        (mods / "sodium.jar").unlink()
        assert sysmods.ensure_rurukasuka(g, inst, mc, settings, acc)
        assert sysmods.ensure_rurukasuka(g, inst, mc, {"rurukasuka": False}, acc) is False
        assert not list(mods.glob("*.jar")) and not (mc / sysmods.TRACKER).exists()
        # unsupported version / loader → nothing is placed
        (mods / "sodium.jar").write_bytes(b"user mod")
        assert sysmods.ensure_rurukasuka(g, inst | {"mc_version": "1.20.1"}, mc, settings, acc) is False
        assert sysmods.ensure_rurukasuka(g, inst | {"loader": "forge"}, mc, settings, acc) is False
        assert [p.name for p in mods.glob("*.jar")] == ["sodium.jar"]
        # bad checksum → skipped, not fatal
        Fake.version = "0.1.0"
        (tmp / "data" / "sysmods" / "rurukasuka-0.1.0.jar").write_bytes(b"corrupt")
        assert sysmods.ensure_rurukasuka(g, inst, mc, settings, acc)   # re-downloaded over the corrupt cache
        assert (mods / "rurukasuka-0.1.0.jar").read_bytes() == JAR
        return {"calls": len(Fake.calls)}
    finally:
        mcru.SITE, modrinth.API, sysmods.GITHUB_RELEASES, sysmods.CACHE_TTL = saved
        if prev_data is None:
            os.environ.pop("ETA_DATA", None)
        else:
            os.environ["ETA_DATA"] = prev_data
        httpd.shutdown()


if __name__ == "__main__":
    print("sysmods ok", run())
