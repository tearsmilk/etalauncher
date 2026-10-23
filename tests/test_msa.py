"""Microsoft accounts against a local fake of the whole chain: device code (pending twice, then a token), Xbox Live,
XSTS (incl. one XErr), login_with_xbox, entitlements, profile, refresh — and the launch command for an msa account.
No Qt. Run: `python -m tests.test_msa` from eta/, or via `run.py --selftest`."""
import http.server
import json
import tempfile
import threading
import time
from pathlib import Path


class FakeMicrosoft(http.server.BaseHTTPRequestHandler):
    polls = 0
    calls = []
    xerr_for = "xbl-bad"     # the XBL token that makes XSTS answer with an XErr
    no_profile = False

    def _json(self, code, data=None):
        body = json.dumps(data).encode() if data is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if "json" in (self.headers.get("Content-Type") or ""):
            return json.loads(raw or b"{}")
        from urllib.parse import parse_qs
        return {k: v[0] for k, v in parse_qs(raw.decode()).items()}

    def do_POST(self):
        self.calls.append(("POST", self.path))
        b = self._body()
        if self.path == "/devicecode":
            assert b["client_id"] == "test-client" and "XboxLive.signin" in b["scope"], b
            return self._json(200, {"user_code": "ABCD-1234", "device_code": "dev-1", "interval": 0,
                                    "expires_in": 60, "verification_uri": "https://www.microsoft.com/link",
                                    "message": "go"})
        if self.path == "/token":
            if b.get("grant_type") == "refresh_token":
                assert b["refresh_token"] == "rt-1"
                return self._json(200, {"access_token": "ms-2", "refresh_token": "rt-2", "expires_in": 3600})
            FakeMicrosoft.polls += 1
            if self.polls == 1:
                return self._json(400, {"error": "authorization_pending"})
            if self.polls == 2:
                return self._json(400, {"error": "slow_down"})
            return self._json(200, {"access_token": "ms-1", "refresh_token": "rt-1", "expires_in": 3600})
        if self.path == "/xbl":
            tok = b["Properties"]["RpsTicket"]
            return self._json(200, {"Token": "xbl-bad" if tok == "d=ms-bad" else "xbl-1",
                                    "DisplayClaims": {"xui": [{"uhs": "uhs-1"}]}})
        if self.path == "/xsts":
            if b["Properties"]["UserTokens"] == [self.xerr_for]:
                return self._json(401, {"XErr": 2148916233, "Message": ""})
            return self._json(200, {"Token": "xsts-1", "DisplayClaims": {"xui": [{"uhs": "uhs-1",
                                                                                  "xid": "2535400000000000"}]}})
        if self.path == "/mc/login":
            assert b["identityToken"] == "XBL3.0 x=uhs-1;xsts-1", b
            return self._json(200, {"access_token": "mc-" + str(len(self.calls)), "expires_in": 86400})
        self._json(404, {"error": "nope"})

    def do_GET(self):
        self.calls.append(("GET", self.path))
        assert self.headers.get("Authorization", "").startswith("Bearer mc-"), self.headers.get("Authorization")
        if self.path == "/mc/store":
            return self._json(200, {"items": [{"name": "game_minecraft"}]})
        if self.path == "/mc/profile":
            if self.no_profile:
                return self._json(404, {"error": "NOT_FOUND"})
            return self._json(200, {"id": "069a79f444e94726a5befca90e38aaf5", "name": "Notch", "skins": []})
        self._json(404, {})

    def log_message(self, *a):
        pass


def serve():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeMicrosoft)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def run(tmp=None):
    from eta import launch, msa, net

    tmp = Path(tmp or tempfile.mkdtemp())
    httpd, base = serve()
    names = ("CLIENT_ID", "DEVICE_CODE_URL", "TOKEN_URL", "XBL_URL", "XSTS_URL", "MC_LOGIN_URL", "MC_STORE_URL",
             "MC_PROFILE_URL")
    saved = {n: getattr(msa, n) for n in names}
    msa.CLIENT_ID, msa.DEVICE_CODE_URL, msa.TOKEN_URL = "test-client", base + "/devicecode", base + "/token"
    msa.XBL_URL, msa.XSTS_URL = base + "/xbl", base + "/xsts"
    msa.MC_LOGIN_URL, msa.MC_STORE_URL, msa.MC_PROFILE_URL = base + "/mc/login", base + "/mc/store", base + "/mc/profile"
    try:
        assert msa.available()
        shown = []
        acc = msa.login_device_code(on_code=lambda c, u, m: shown.append((c, u)))
        assert shown == [("ABCD-1234", "https://www.microsoft.com/link")] and FakeMicrosoft.polls == 3
        assert acc["name"] == "Notch" and acc["uuid"] == "069a79f4-44e9-4726-a5be-fca90e38aaf5"
        assert acc["mc_token"].startswith("mc-") and acc["refresh_token"] == "rt-1" and acc["xuid"] == "2535400000000000"
        assert acc["mc_expires"] > time.time() + 80000
        # cancel is honoured while waiting
        FakeMicrosoft.polls = -100
        try:
            msa.login_device_code(cancel=lambda: True)
            raise AssertionError("cancel ignored")
        except msa.Cancelled:
            pass
        FakeMicrosoft.polls = 0
        # XErr → a Russian explanation, not a code
        try:
            msa._chain({"access_token": "ms-bad"})
            raise AssertionError("XErr accepted")
        except net.NetError as e:
            assert "xbox.com" in str(e), str(e)
        # missing profile
        FakeMicrosoft.no_profile = True
        try:
            msa._chain({"access_token": "ms-1"})
            raise AssertionError("no-profile accepted")
        except net.NetError as e:
            assert "официальный лаунчер" in str(e), str(e)
        FakeMicrosoft.no_profile = False
        # refresh: new MS tokens, chain again, new refresh token kept
        r = msa.refresh("rt-1")
        assert r["refresh_token"] == "rt-2" and r["name"] == "Notch" and r["mc_token"] != acc["mc_token"]
        # ensure_session: fresh → untouched; expired → refreshed in place; no refresh token → clear error
        fresh = dict(acc, type="msa")
        assert msa.ensure_session(fresh) is fresh and fresh["mc_token"] == acc["mc_token"]
        stale = dict(acc, type="msa", mc_expires=time.time() - 1)
        msa.ensure_session(stale)
        assert stale["mc_token"] != acc["mc_token"] and stale["refresh_token"] == "rt-2"
        try:
            msa.ensure_session({"type": "msa", "mc_expires": 0, "refresh_token": ""})
            raise AssertionError("session without refresh token accepted")
        except net.NetError as e:
            assert "войдите" in str(e)
        # the command line: real token, user_type msa, xuid + clientid, no javaagent
        g = launch.Game(tmp / "mc", tmp / "java", workers=2)
        v = {"id": "t", "mainClass": "m.Main", "assetIndex": {"id": "t"},
             "arguments": {"jvm": ["-cp", "${classpath}"],
                           "game": ["--username", "${auth_player_name}", "--uuid", "${auth_uuid}",
                                    "--accessToken", "${auth_access_token}", "--userType", "${user_type}",
                                    "--xuid", "${auth_xuid}", "--clientId", "${clientid}"]}}
        gd = tmp / "inst" / ".minecraft"
        cmd = g.command(v, "java", gd, dict(acc, type="msa"), {"memory_mb": 512}, tmp / "nat", [tmp / "a.jar"],
                        inst={"name": "X"}, injector=tmp / "never.jar")
        assert cmd[cmd.index("--userType") + 1] == "msa" and cmd[cmd.index("--accessToken") + 1] == acc["mc_token"]
        assert cmd[cmd.index("--uuid") + 1] == "069a79f444e94726a5befca90e38aaf5"
        assert cmd[cmd.index("--xuid") + 1] == "2535400000000000" and cmd[cmd.index("--clientId") + 1] == "test-client"
        assert not any(a.startswith("-javaagent") for a in cmd)
        assert msa.head_url(acc["uuid"]) == "https://crafatar.com/avatars/069a79f444e94726a5befca90e38aaf5?size=64&overlay"
        return {"calls": len(FakeMicrosoft.calls), "cmd": len(cmd)}
    finally:
        for n, val in saved.items():
            setattr(msa, n, val)
        httpd.shutdown()


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.environ.setdefault("ETA_DATA", tempfile.mkdtemp())
    print("msa ok", run())
