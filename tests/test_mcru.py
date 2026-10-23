"""mc-ru.org accounts against a local fake Yggdrasil server: authenticate / validate / refresh / invalidate, the
authlib-injector download with a sha256 check, CustomSkinLoader config, and the launch command (javaagent, token,
user_type). No Qt. Run: `python -m tests.test_mcru` from eta/, or via `run.py --selftest`."""
import hashlib
import http.server
import json
import tempfile
import threading
from pathlib import Path


class FakeYggdrasil(http.server.BaseHTTPRequestHandler):
    tokens = {}          # access → client
    password = "hunter2"
    jar = b"PK\x03\x04 fake authlib-injector"
    calls = []

    def _json(self, code, data=None):
        body = json.dumps(data).encode() if data is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.calls.append(("GET", self.path))
        if self.path == "/api/yggdrasil":
            return self._json(200, {"meta": {"serverName": "mc-ru.org"}, "skinDomains": ["mc-ru.org"],
                                    "signaturePublickey": "-----BEGIN PUBLIC KEY-----\nx\n-----END PUBLIC KEY-----"})
        if self.path == "/artifact/latest.json":
            return self._json(200, {"version": "9.9", "download_url": f"http://{self.headers['Host']}/inj.jar",
                                    "checksums": {"sha256": hashlib.sha256(self.jar).hexdigest()}})
        if self.path == "/inj.jar":
            self.send_response(200)
            self.send_header("Content-Length", str(len(self.jar)))
            self.end_headers()
            self.wfile.write(self.jar)
            return
        if self.path.startswith("/api/users/"):
            return self._json(200, {"username": "Hoka_Neko", "uuid": "1" * 32, "model": "slim",
                                    "skin": {"hd": True, "animated": True}, "cape": None})
        self._json(404, {"error": "Not Found"})

    def do_POST(self):
        self.calls.append(("POST", self.path))
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if self.path.endswith("/authserver/authenticate"):
            if body.get("password") != self.password:
                return self._json(403, {"error": "ForbiddenOperationException",
                                        "errorMessage": "Неверный ник или пароль"})
            access = "acc-" + hashlib.md5(body["username"].encode()).hexdigest()[:8]
            self.tokens[access] = body["clientToken"]
            return self._json(200, {"accessToken": access, "clientToken": body["clientToken"],
                                    "selectedProfile": {"id": "a" * 32, "name": "Hoka_Neko"},
                                    "availableProfiles": [{"id": "a" * 32, "name": "Hoka_Neko"}]})
        ok = self.tokens.get(body.get("accessToken")) == body.get("clientToken")
        if self.path.endswith("/authserver/validate"):
            return self._json(204) if ok else self._json(403, {"error": "ForbiddenOperationException",
                                                                 "errorMessage": "Invalid token."})
        if self.path.endswith("/authserver/refresh"):
            if not ok:
                return self._json(403, {"error": "ForbiddenOperationException", "errorMessage": "Invalid token."})
            self.tokens.pop(body["accessToken"])
            new = "acc-refreshed"
            self.tokens[new] = body["clientToken"]
            return self._json(200, {"accessToken": new, "clientToken": body["clientToken"],
                                    "selectedProfile": {"id": "a" * 32, "name": "Hoka_Neko"}})
        if self.path.endswith("/authserver/invalidate"):
            self.tokens.pop(body.get("accessToken"), None)
            return self._json(204)
        self._json(404, {"error": "Not Found"})

    def log_message(self, *a):
        pass


def serve():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeYggdrasil)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def run(tmp=None):
    from eta import launch, mcru, net

    tmp = Path(tmp or tempfile.mkdtemp())
    httpd, base = serve()
    saved = mcru.SITE, mcru.YGGDRASIL, mcru.INJECTOR_LATEST
    mcru.SITE, mcru.YGGDRASIL, mcru.INJECTOR_LATEST = base, base + "/api/yggdrasil", base + "/artifact/latest.json"
    try:
        # bad password → the server's message, not an HTTP code
        try:
            mcru.authenticate("Hoka_Neko", "wrong", "ct1")
            raise AssertionError("bad password accepted")
        except net.NetError as e:
            assert "Неверный ник или пароль" in str(e), str(e)
        r = mcru.authenticate("hoka@example.com", "hunter2", "ct1")
        assert r["name"] == "Hoka_Neko" and r["uuid"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert r["client_token"] == "ct1" and r["access_token"].startswith("acc-")
        assert mcru.validate(r["access_token"], "ct1") and not mcru.validate("nope", "ct1")
        # expired token → refresh gives a new one that validates
        nr = mcru.refresh(r["access_token"], "ct1")
        assert nr["access_token"] == "acc-refreshed" and not mcru.validate(r["access_token"], "ct1")
        assert mcru.validate("acc-refreshed", "ct1")
        try:
            mcru.refresh("dead", "ct1")
            raise AssertionError("refresh of a dead token succeeded")
        except net.NetError:
            pass
        assert mcru.profile("Hoka_Neko")["skin"]["hd"] and mcru.head_url("X").endswith("/skin.png?frame=0&size=64")
        # injector: download, sha256, cached second time
        jar = mcru.authlib_injector(tmp / "inj")
        assert jar.name == "authlib-injector-9.9.jar" and jar.read_bytes() == FakeYggdrasil.jar
        n = len(FakeYggdrasil.calls)
        assert mcru.authlib_injector(tmp / "inj") == jar and len(FakeYggdrasil.calls) == n + 1  # only latest.json
        # session helper: validate ok → unchanged; dead → refreshed and acc mutated; dead+unrefreshable → error
        g = launch.Game(tmp / "mc", tmp / "java", workers=2)
        acc = {"type": "mcru", "name": "Hoka_Neko", "uuid": r["uuid"], "access_token": "acc-refreshed",
               "client_token": "ct1"}
        assert g.mcru_session(acc)["access_token"] == "acc-refreshed"
        FakeYggdrasil.tokens["old"] = "ct1"
        acc2 = dict(acc, access_token="stale")
        FakeYggdrasil.tokens.pop("stale", None)
        try:
            g.mcru_session(acc2)
            raise AssertionError("stale token without refresh accepted")
        except net.NetError as e:
            assert "войдите" in str(e)
        # CustomSkinLoader config: created, then an existing config gets the mc-ru.org entry prepended
        gd = tmp / "inst" / ".minecraft"
        cfg = launch.Game.csl_config(gd)
        data = json.loads(cfg.read_text("utf-8"))
        assert data["loadlist"][0]["root"] == mcru.CSL_ROOT and data["enableDynamicSkull"]
        cfg.write_text(json.dumps({"version": "14.0", "loadlist": [{"name": "Mojang", "type": "MojangAPI"}]}))
        data = json.loads(launch.Game.csl_config(gd).read_text("utf-8"))
        assert [e["name"] for e in data["loadlist"]] == ["mc-ru.org", "Mojang"]
        assert [e["name"] for e in json.loads(launch.Game.csl_config(gd).read_text("utf-8"))["loadlist"]] == \
            ["mc-ru.org", "Mojang"]
        # the command line: token, user_type mojang, javaagent right after -Xmx; offline unchanged
        v = {"id": "t", "mainClass": "m.Main", "assetIndex": {"id": "t"},
             "arguments": {"jvm": ["-cp", "${classpath}"],
                           "game": ["--username", "${auth_player_name}", "--uuid", "${auth_uuid}",
                                    "--accessToken", "${auth_access_token}", "--userType", "${user_type}"]}}
        settings = {"memory_mb": 512}
        cmd = g.command(v, "java", gd, acc, settings, tmp / "nat", [tmp / "a.jar"], inst={"name": "X"},
                        injector=jar)
        assert cmd[2] == f"-javaagent:{jar}={mcru.YGGDRASIL}" and cmd[3] == "-Dauthlibinjector.side=client"
        assert cmd[cmd.index("--accessToken") + 1] == "acc-refreshed" and cmd[cmd.index("--userType") + 1] == "mojang"
        assert cmd[cmd.index("--uuid") + 1] == "a" * 32
        off = g.command(v, "java", gd, {"name": "Steve", "uuid": "b50ad385-829d-3141-a216-7e7d7539ba7f"}, settings,
                        tmp / "nat", [tmp / "a.jar"], inst={"name": "X"}, injector=jar)
        assert not any(a.startswith("-javaagent") for a in off) and off[off.index("--userType") + 1] == "legacy"
        assert off[off.index("--accessToken") + 1] == "0"
        return {"calls": len(FakeYggdrasil.calls), "cmd": len(cmd)}
    finally:
        mcru.SITE, mcru.YGGDRASIL, mcru.INJECTOR_LATEST = saved
        httpd.shutdown()


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.setdefault("ETA_DATA", tempfile.mkdtemp())
    print("mcru ok", run())
