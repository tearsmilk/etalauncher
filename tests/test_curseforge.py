"""CurseForge against a local fake Core API + edge CDN: search normalisation, files, and installing a modpack zip
(manifest.json, batch file resolve, class-id folders, sha1, blocked optional / required files, overrides).
No Qt. Run: `python -m tests.test_curseforge` from eta/, or via `run.py --selftest`."""
import hashlib
import http.server
import io
import json
import os
import tempfile
import threading
import zipfile
from pathlib import Path

MOD_A = b"PK\x03\x04 mod-a"
MOD_B = b"PK\x03\x04 mod-b"
PACK_RP = b"PK\x03\x04 resourcepack"


def _sha1(b):
    return hashlib.sha1(b).hexdigest()


class FakeCurseForge(http.server.BaseHTTPRequestHandler):
    calls = []
    key = "test-key"

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _raw(self, code, data=b""):
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def base(self):
        return f"http://{self.headers['Host']}"

    def files(self):
        b = self.base()
        return {
            101: {"id": 101, "modId": 11, "displayName": "Mod A 1.0", "fileName": "mod-a.jar", "releaseType": 1,
                  "fileDate": "2024-02-01T00:00:00Z", "downloadUrl": f"{b}/cdn/mod-a.jar",
                  "gameVersions": ["1.20.1", "Forge"], "hashes": [{"value": _sha1(MOD_A), "algo": 1}],
                  "fileLength": len(MOD_A), "downloadCount": 5},
            102: {"id": 102, "modId": 12, "displayName": "Mod B 2.0", "fileName": "mod-b.jar", "releaseType": 2,
                  "fileDate": "2024-03-01T00:00:00Z", "downloadUrl": None,   # author disallows API downloads
                  "gameVersions": ["1.20.1", "Forge"], "hashes": [], "fileLength": 3},
            103: {"id": 103, "modId": 13, "displayName": "Pretty Pack", "fileName": "pretty.zip", "releaseType": 1,
                  "fileDate": "2024-01-01T00:00:00Z", "downloadUrl": f"{b}/cdn/pretty.zip",
                  "gameVersions": ["1.20.1"], "hashes": [{"value": _sha1(PACK_RP), "algo": 1}],
                  "fileLength": len(PACK_RP)},
            201: {"id": 201, "modId": 77, "displayName": "Cozy Pack 1.2.0", "fileName": "cozy-1.2.0.zip",
                  "releaseType": 1, "fileDate": "2024-04-01T00:00:00Z", "downloadUrl": f"{b}/cdn/cozy.zip",
                  "gameVersions": ["1.20.1", "Forge"], "hashes": [], "fileLength": 0, "downloadCount": 9},
        }

    def mods(self):
        return {11: {"id": 11, "name": "Mod A", "classId": 6, "links": {"websiteUrl": "https://cf/mod-a"}},
                12: {"id": 12, "name": "Mod B", "classId": 6, "links": {"websiteUrl": "https://cf/mod-b"}},
                13: {"id": 13, "name": "Pretty", "classId": 12, "links": {"websiteUrl": "https://cf/pretty"}}}

    def do_GET(self):
        self.calls.append(("GET", self.path))
        if self.path.startswith("/cdn/"):
            name = self.path.rsplit("/", 1)[-1]
            data = {"mod-a.jar": MOD_A, "pretty.zip": PACK_RP, "cozy.zip": self.server.pack_zip}.get(name)
            return self._raw(200, data) if data else self._raw(404)
        if self.path.startswith("/files/"):   # edge cdn: mod-b is blocked
            return self._raw(403)
        if self.headers.get("x-api-key") != self.key:
            return self._json(403, {"error": "no key"})
        if self.path.startswith("/v1/mods/search"):
            hit = {"id": 77, "name": "Cozy Pack", "slug": "cozy-pack", "summary": "Уютная сборка",
                   "links": {"websiteUrl": "https://www.curseforge.com/minecraft/modpacks/cozy-pack"},
                   "categories": [{"name": "Adventure and RPG", "slug": "adventure-rpg"}],
                   "authors": [{"name": "mira"}], "downloadCount": 1234, "thumbsUpCount": 7,
                   "logo": {"thumbnailUrl": "https://cf/logo.png"},
                   "latestFilesIndexes": [{"gameVersion": "1.20.1", "modLoader": 1},
                                          {"gameVersion": "1.19.2", "modLoader": 1}, {"gameVersion": "1.20.1", "modLoader": 4}],
                   "dateCreated": "2023-01-01T00:00:00Z", "dateModified": "2024-04-01T00:00:00Z", "classId": 4471}
            return self._json(200, {"data": [hit], "pagination": {"index": 0, "pageSize": 20, "totalCount": 1}})
        if self.path.startswith("/v1/mods/77/files"):
            return self._json(200, {"data": [self.files()[201]]})
        if self.path.startswith("/v1/mods/77/description"):
            return self._json(200, {"data": "<p><b>Cozy</b> pack</p>"})
        if self.path.startswith("/v1/mods/77"):
            return self._json(200, {"data": {"id": 77, "name": "Cozy Pack", "slug": "cozy-pack", "summary": "x",
                                             "latestFilesIndexes": [], "classId": 4471}})
        if self.path.startswith("/v1/categories"):
            return self._json(200, {"data": [{"id": 4475, "name": "Adventure and RPG", "slug": "adventure-rpg"},
                                             {"id": 4476, "name": "Magic", "slug": "magic"}]})
        return self._json(404, {"error": "?"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        self.calls.append(("POST", self.path, body))
        if self.headers.get("x-api-key") != self.key:
            return self._json(403, {"error": "no key"})
        if self.path == "/v1/mods/files":
            return self._json(200, {"data": [self.files()[i] for i in body["fileIds"] if i in self.files()]})
        if self.path == "/v1/mods":
            return self._json(200, {"data": [self.mods()[i] for i in body["modIds"] if i in self.mods()]})
        return self._json(404, {})


def make_pack(required_b=False):
    buf = io.BytesIO()
    manifest = {"minecraft": {"version": "1.20.1", "modLoaders": [{"id": "forge-47.2.0", "primary": True}]},
                "manifestType": "minecraftModpack", "name": "Cozy Pack", "version": "1.2.0", "overrides": "overrides",
                "files": [{"projectID": 11, "fileID": 101, "required": True},
                          {"projectID": 12, "fileID": 102, "required": required_b},
                          {"projectID": 13, "fileID": 103, "required": True}]}
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        z.writestr("overrides/config/cozy.toml", "x = 1")
        z.writestr("overrides/mods/local.jar", "PK local")
    return buf.getvalue()


def serve(pack_zip):
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeCurseForge)
    httpd.pack_zip = pack_zip
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_port}"


def run(tmp=None):
    from eta import curseforge as cf
    from eta import net
    from eta.modrinth import InstallError

    tmp = Path(tmp or tempfile.mkdtemp())
    httpd, base = serve(make_pack())
    saved = cf.API, cf.EDGE
    cf.API, cf.EDGE = base + "/v1", base + "/files"
    settings = {"curseforge_key": "test-key"}
    # CI bakes a real key via ETA_CURSEFORGE_KEY / eta/_keys.py — the "no key" checks must not see it
    env_key, baked = os.environ.pop("ETA_CURSEFORGE_KEY", None), cf._baked_key
    cf._baked_key = lambda: ""
    try:
        assert not cf.available({"curseforge_key": ""}) and cf.available(settings)
        try:
            cf.CurseForgeProvider({}).search("x")
            raise AssertionError("search without a key worked")
        except net.NetError as e:
            assert "API-ключ" in str(e)
        prov = cf.CurseForgeProvider(settings)
        hits, total = prov.search(query="cozy", loaders=["forge"], version="1.20.1", categories=["adventure"],
                                  sort="downloads")
        assert total == 1 and hits[0]["slug"] == "77" and hits[0]["source"] == "curseforge"
        assert hits[0]["loaders"] == ["forge", "fabric"] and hits[0]["game_versions"] == ["1.20.1", "1.19.2"]
        assert hits[0]["author"] == "mira" and hits[0]["icon_url"].endswith("logo.png")
        q = next(c for c in FakeCurseForge.calls if c[1].startswith("/v1/mods/search"))[1]
        assert "modLoaderType=1" in q and "gameVersion=1.20.1" in q and "sortField=6" in q and "categoryId=4475" in q
        p = prov.project("77")
        assert p["body_html"] and "<b>Cozy</b>" in p["body"] and prov.cached("77") is p
        vs = prov.versions("77")
        assert vs[0]["loader"] == "forge" and vs[0]["mc"] == "1.20.1" and vs[0]["file"]["url"].endswith("cozy.zip")
        assert vs[0]["type"] == "release" and vs[0]["version"] == "Cozy Pack 1.2.0"
        assert cf.edge_url(102, "mod b.jar") == base + "/files/0/102/mod%20b.jar"
        # content search for ModAddDialog
        cs = cf.search_content("cozy", "mod", loaders=["forge"], version="1.20.1", settings=settings)
        assert cs and cs[0]["slug"] == "77"
        cv = cf.content_versions("77", "forge", "1.20.1", settings=settings)
        assert cv[0]["file"]["filename"] == "cozy-1.2.0.zip"
        # install: optional blocked file skipped, resourcepack lands in resourcepacks/, overrides copied
        pack = tmp / "cozy.zip"
        net.download(vs[0]["file"]["url"], pack)
        assert cf.is_curseforge_pack(pack)
        seen = []
        target = tmp / "cf-inst" / ".minecraft"
        info = cf.install_pack(pack, target, lambda st, d, t: seen.append(st), None, 3, settings)
        assert info["loader"] == "forge" and info["loader_version"] == "47.2.0" and info["mc"] == "1.20.1"
        assert (target / "mods" / "mod-a.jar").read_bytes() == MOD_A
        assert (target / "resourcepacks" / "pretty.zip").read_bytes() == PACK_RP
        assert not (target / "mods" / "mod-b.jar").exists() and len(info["skipped"]) == 1
        assert (target / "config" / "cozy.toml").read_text() == "x = 1" and (target / "mods" / "local.jar").exists()
        assert info["mods"] == 2 and "files" in seen and "overrides" in seen
        meta = json.loads((tmp / "cf-inst" / "eta-pack.json").read_text("utf-8"))
        assert meta["source"] == "curseforge" and meta["name"] == "Cozy Pack"
        # required blocked file → clear error with the project link
        httpd.pack_zip = make_pack(required_b=True)
        pack2 = tmp / "cozy2.zip"
        net.download(vs[0]["file"]["url"], pack2)
        try:
            cf.install_pack(pack2, tmp / "cf-inst2" / ".minecraft", None, None, 3, settings)
            raise AssertionError("blocked required file did not fail")
        except InstallError as e:
            assert "https://cf/mod-b" in str(e) and "вручную" in str(e), str(e)
        assert (tmp / "cf-inst2" / ".minecraft" / "mods" / "mod-a.jar").exists()
        # pack info parsing
        assert cf.pack_info({"minecraft": {"version": "1.21", "modLoaders": [{"id": "neoforge-21.1.0"}]},
                             "files": []})["loader"] == "neoforge"
        assert cf.pack_info({"minecraft": {"version": "1.21"}})["loader"] == "vanilla"
        return {"calls": len(FakeCurseForge.calls)}
    finally:
        cf.API, cf.EDGE = saved
        cf._baked_key = baked
        if env_key is not None:
            os.environ["ETA_CURSEFORGE_KEY"] = env_key
        httpd.shutdown()


if __name__ == "__main__":
    print("curseforge ok", run())
