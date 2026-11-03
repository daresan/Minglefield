"""HTTP contract tests for owner-scoped game project registration."""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy
from private_alpha_gateway import handler_for


class GameProjectHttpTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = AlphaAuthStore(self.root / "alpha.sqlite3")
        self.owner = self.store.redeem(self.store.invite("user.owner"),
                                       password="local-test-password-123")
        self.other = self.store.redeem(self.store.invite("user.other"),
                                       password="local-test-password-123")
        self.store._host_policy = HostCommitPolicy(IntegratedAlphaAdmission(self.store))
        with self.store._tx() as db:
            db.execute("INSERT INTO sec01_host_owners(host_id,owner_id) VALUES(?,?)",
                       ("host.one", "user.owner"))
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.store))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def request(self, method, path, token=None, payload=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode()
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_host_integration_source_settings_owner_scoped(self):
        endpoint = "/api/host/settings"
        payload = {"host_id": "host.one", "settings": {
            "staging_root": "", "output_root": "",
            "trusted_integration_sources": ["daresan/minglefield-integration-test"]}}
        self.assertEqual(self.request("POST", endpoint, self.other, payload)[0], 400)
        status, data = self.request("POST", endpoint, self.owner, payload)
        self.assertEqual(status, 200, data)
        status, data = self.request("GET", endpoint + "?host_id=host.one", self.owner)
        self.assertEqual(status, 200)
        self.assertEqual(data["settings"]["trusted_integration_sources"],
                         ["daresan/minglefield-integration-test"])
        self.assertEqual(self.request("GET", endpoint + "?host_id=host.one", self.other)[0], 403)
        for bad in (["../evil"], ["daresan/repo", "daresan/repo"], ["https://example.com/x"]):
            invalid = {"host_id": "host.one", "settings": {
                "staging_root": "", "output_root": "",
                "trusted_integration_sources": bad}}
            self.assertNotEqual(self.request("POST", endpoint, self.owner, invalid)[0], 200)
        status, data = self.request("GET", endpoint + "?host_id=host.one", self.owner)
        self.assertEqual(data["settings"]["trusted_integration_sources"],
                         ["daresan/minglefield-integration-test"])

    def test_authenticated_project_lifecycle_and_isolation(self):
        path = "/api/game/projects?host_id=host.one"
        payload = dict(host_id="host.one", project_id="game.one", name="Game One",
                       repository_root=str(self.root / "repo"),
                       staging_root=str(self.root / "stage"),
                       output_root=str(self.root / "output"))
        self.assertEqual(self.request("GET", path)[0], 401)
        self.assertEqual(self.request("POST", "/api/game/projects", payload=payload)[0], 401)
        self.assertEqual(self.request("GET", path, self.other)[0], 403)
        self.assertEqual(self.request("POST", "/api/game/projects", self.other, payload)[0], 403)
        self.assertEqual(self.request("GET", path, self.owner), (200, {"projects": []}))
        status, data = self.request("POST", "/api/game/projects", self.owner, payload)
        self.assertEqual((status, data["state"]), (201, "created"))
        self.assertEqual(self.request("POST", "/api/game/projects", self.owner, payload)[0], 409)
        status, data = self.request("GET", path, self.owner)
        self.assertEqual(status, 200)
        self.assertEqual(len(data["projects"]), 1)
        self.assertEqual(data["projects"][0]["project_id"], "game.one")
        self.assertEqual(self.request("GET", path, self.other)[0], 403)

    def test_game_tab_markup_and_api_wiring(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        try:
            connection.request("GET", "/")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.getheader("Content-Type"))
            html = response.read().decode("utf-8")
        finally:
            connection.close()
        for fragment in ('id="gameProjectPanel"', 'id="gameHostSelect"',
                         'id="gameProjectCreate"', 'id="gameProjectUpdate"', 'id="gameProjectSelect"',
                         'id="gameProjectDelete"', 'id="gameCreatePanel"',
                         '"/api/game/projects"', '["game","Game"]'):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, html)

    def test_project_update_http_contract(self):
        payload = dict(host_id="host.one", project_id="game.one", name="Original",
                       repository_root=str(self.root / "repo"),
                       staging_root=str(self.root / "stage"),
                       output_root=str(self.root / "output"))
        self.assertEqual(self.request("POST", "/api/game/projects", self.owner, payload)[0], 201)
        update = dict(payload, name="Updated", settings_revision=1)
        path = "/api/game/projects/update"
        self.assertEqual(self.request("POST", path, payload=update)[0], 401)
        self.assertEqual(self.request("POST", path, self.other, update)[0], 403)
        self.assertEqual(self.request("POST", path, self.owner, update)[0], 200)
        self.assertEqual(self.request("POST", path, self.owner, update)[0], 409)
        status, data = self.request("GET", "/api/game/projects?host_id=host.one", self.owner)
        self.assertEqual(status, 200)
        self.assertEqual((data["projects"][0]["name"], data["projects"][0]["settings_revision"]),
                         ("Updated", 2))

    def test_git_profile_http_contract(self):
        profile=dict(profile_id="git.default",label="Default",auth_method="local",
                     git_executable="git",author_name="Tester",
                     author_email="tester@example.invalid")
        payload={"host_id":"host.one","profile":profile}
        self.assertEqual(self.request("POST", "/api/git/profiles", payload=payload)[0], 401)
        self.assertEqual(self.request("POST", "/api/git/profiles", self.other, payload)[0], 403)
        self.assertEqual(self.request("POST", "/api/git/profiles", self.owner, payload)[0], 200)
        status,data=self.request("GET", "/api/git/profiles?host_id=host.one", self.owner)
        self.assertEqual(status,200)
        self.assertEqual(data["profiles"][0]["profile_id"],"git.default")
        self.assertEqual(self.request("GET", "/api/git/profiles?host_id=host.one",
                                      self.other)[0],403)

    def test_unregister_is_owner_scoped_and_does_not_touch_files(self):
        existing = self.root / "repo"
        existing.mkdir()
        marker = existing / "keep.txt"
        marker.write_text("preserve")
        payload = dict(host_id="host.one", project_id="game.remove", name="Temporary",
                       repository_root=str(existing), staging_root=str(self.root / "stage"),
                       output_root=str(self.root / "output"))
        self.assertEqual(self.request("POST", "/api/game/projects", self.owner, payload)[0], 201)
        deletion = dict(host_id="host.one", project_id="game.remove", settings_revision=1)
        route = "/api/game/projects/delete"
        self.assertEqual(self.request("POST", route, payload=deletion)[0], 401)
        self.assertEqual(self.request("POST", route, self.other, deletion)[0], 403)
        self.assertEqual(self.request("POST", route, self.owner, deletion)[0], 200)
        self.assertEqual(self.request("POST", route, self.owner, deletion)[0], 409)
        self.assertEqual(marker.read_text(), "preserve")
        self.assertEqual(self.request("GET", "/api/game/projects?host_id=host.one",
                                      self.owner)[1]["projects"], [])

    def test_manifest_prepare_http_route(self):
        repo=self.root/"manifest_http_repo"
        repo.mkdir()
        payload=dict(host_id="host.one",project_id="game.manifest.http",
                     name="Manifest HTTP",repository_root=str(repo),
                     staging_root=str(repo/"staging"),output_root=str(repo/"output"))
        self.assertEqual(self.request("POST","/api/game/projects",
                                      self.owner,payload)[0],201)
        body=dict(host_id="host.one",project_id="game.manifest.http",
                  settings_revision=1)
        path="/api/game/projects/manifest/prepare"
        self.assertEqual(self.request("POST",path,payload=body)[0],401)
        self.assertEqual(self.request("POST",path,self.other,body)[0],403)
        status,data=self.request("POST",path,self.owner,body)
        self.assertEqual(status,200)
        self.assertEqual(data["state"],"created")
        self.assertTrue((repo/".minglefield"/"project.json").is_file())
        status,data=self.request("POST",path,self.owner,body)
        self.assertEqual(status,200)
        self.assertEqual(data["state"],"unchanged")

    def test_integration_registry_http_is_read_only_and_owner_scoped(self):
        repo=self.root/"integration_report_repo"
        repo.mkdir()
        payload=dict(host_id="host.one",project_id="game.report",
                     name="Integration Report",repository_root=str(repo),
                     staging_root=str(repo/"staging"),output_root=str(repo/"output"))
        self.assertEqual(self.request("POST","/api/game/projects",
                                      self.owner,payload)[0],201)
        route="/api/game/integrations?host_id=host.one&project_id=game.report"
        self.assertEqual(self.request("GET",route)[0],401)
        self.assertEqual(self.request("GET",route,self.other)[0],404)
        self.assertEqual(self.request("GET",route+"&extra=1",self.owner)[0],400)
        self.assertEqual(self.request("GET","/api/game/integrations?host_id=host.one",
                                      self.owner)[0],400)
        status,data=self.request("GET",route,self.owner)
        self.assertEqual(status,200)
        self.assertEqual(data["installation_state"],"setup_required")
        self.assertIsNone(data["installed_integrations"])
        self.assertEqual(data["registry"]["state"],"available")
        self.assertEqual(data["registry"]["integrations"],[])
        self.assertFalse((repo/".minglefield").exists())
        body=dict(host_id="host.one",project_id="game.report",settings_revision=1)
        self.assertEqual(self.request("POST","/api/game/projects/manifest/prepare",
                                      self.owner,body)[0],200)
        manifest=repo/".minglefield"/"project.json"
        before=manifest.read_bytes()
        status,data=self.request("GET",route,self.owner)
        self.assertEqual(status,200)
        self.assertEqual(data["installation_state"],"installation_unknown")
        self.assertIsNone(data["installed_integrations"])
        self.assertEqual(manifest.read_bytes(),before)

    def test_integration_update_status_is_read_only_and_owner_scoped(self):
        repo=self.root/"update_repo"
        repo.mkdir()
        payload=dict(host_id="host.one",project_id="game.update",
                     name="Update",repository_root=str(repo),
                     staging_root=str(repo/"staging"),output_root=str(repo/"output"))
        self.assertEqual(self.request("POST","/api/game/projects",
                                      self.owner,payload)[0],201)
        route="/api/game/integration/update-status?host_id=host.one&project_id=game.update"
        self.assertEqual(self.request("GET",route)[0],401)
        self.assertEqual(self.request("GET",route,self.other)[0],404)
        status,data=self.request("GET",route,self.owner)
        self.assertEqual(status,200)
        self.assertEqual(data["update_state"],"setup_required")
        self.assertIsNone(data["update_available"])
        self.assertFalse((repo/".minglefield").exists())
        body=dict(host_id="host.one",project_id="game.update",settings_revision=1)
        self.assertEqual(self.request("POST","/api/game/projects/manifest/prepare",
                                      self.owner,body)[0],200)
        status,data=self.request("GET",route,self.owner)
        self.assertEqual(status,200)
        self.assertEqual(data["update_state"],"availability_unknown")
        self.assertIsNone(data["update_available"])

    def test_integration_releases_endpoint_is_owner_scoped(self):
        repo=self.root/"release_report_repo"
        repo.mkdir()
        payload=dict(host_id="host.one",project_id="game.release.report",
                     name="Release Report",repository_root=str(repo),
                     staging_root=str(repo/"staging"),output_root=str(repo/"output"))
        self.assertEqual(self.request("POST","/api/game/projects",self.owner,payload)[0],201)
        route="/api/game/integration/releases?host_id=host.one&project_id=game.release.report"
        self.assertEqual(self.request("GET",route)[0],401)
        self.assertEqual(self.request("GET",route,self.other)[0],404)
        self.assertEqual(self.request("GET",route+"&release_repository=attacker/repo",self.owner)[0],400)
        status,data=self.request("GET",route,self.owner)
        self.assertEqual(status,200)
        self.assertEqual(data["state"],"unknown")
        self.assertEqual(data["updates"],[])
        self.assertFalse((repo/"minglefield.lock").exists())

    def test_multiple_release_discovery_is_isolated_and_preserves_files(self):
        from unittest.mock import patch
        repo=self.root/"multi"
        repo.mkdir()
        project="game.multi"
        payload=dict(host_id="host.one",project_id=project,name="Multi",repository_root=str(repo),
                     staging_root=str(repo/"staging"),output_root=str(repo/"output"))
        self.assertEqual(self.request("POST","/api/game/projects",self.owner,payload)[0],201)
        (repo/".minglefield").mkdir()
        (repo/".minglefield/project.json").write_text(json.dumps({"schema_version":1,"project_id":project}))
        entries=[{"integration_id":"community.alice."+name,"name":name,"publisher":"alice",
                  "trust_tier":"community","release_source":{"provider":"github","repository":"alice/"+name}}
                 for name in ("one","two")]
        packages=[{"package_id":e["integration_id"],"kind":"game_integration","version":"1.0",
                   "publisher":"alice","release_source":e["release_source"],
                   "artifact":{"reference":"asset","sha256":"a"*64}} for e in entries]
        (repo/"minglefield.lock").write_text(json.dumps({"lock_version":"0.1","project_id":project,"packages":packages}))
        (repo/"unrelated.txt").write_text("preserve")
        before={str(p.relative_to(repo)):p.read_bytes() for p in repo.rglob("*") if p.is_file()}
        route="/api/game/integration/releases?host_id=host.one&project_id="+project
        calls=[]
        def fetch(source):
            calls.append(source)
            if source=="alice/two":
                raise OSError("offline")
            return {"state":"available","releases":[{"tag_name":"1.0","release_notes":"<script>untrusted</script>"}]}
        self.assertEqual(self.request("POST", "/api/host/settings", self.owner, {
            "host_id": "host.one", "settings": {"staging_root": "", "output_root": "",
                "trusted_integration_sources": ["alice/one", "alice/two"]}})[0], 200)
        # Exercise the real inspector, validator and discovery engine with only external I/O mocked.
        import game_integration_updates as updates
        original=updates.discover_integration_update
        with patch("game_integration_registry.load_registry",return_value={"registry_version":"0.1","integrations":entries}), patch(
                "game_integration_updates.discover_integration_update",
                side_effect=lambda e,c: original(e,c,fetcher=fetch,compare_fetcher=lambda *_: {"state":"unknown"})):
            self.assertEqual(self.request("GET",route)[0],401)
            self.assertEqual(self.request("GET",route,self.other)[0],404)
            self.assertEqual(calls,[])
            status,data=self.request("GET",route,self.owner)
            self.assertEqual(status,200)
            self.assertEqual([u["comparison_state"] for u in data["updates"]],["up_to_date","error"])
            self.assertEqual(data["updates"][0]["release_notes"],"<script>untrusted</script>")
            self.assertEqual(calls,["alice/one","alice/two"])
        self.assertEqual(before,{str(p.relative_to(repo)):p.read_bytes() for p in repo.rglob("*") if p.is_file()})
        for endpoint in ("releases","update-status"):
            for extra in ("&release_repository=evil/repo","&release_repository=","&unknown=x"):
                url="/api/game/integration/"+endpoint+"?host_id=host.one&project_id="+project+extra
                self.assertEqual(self.request("GET",url,self.owner)[0],400)

    def test_http_assessment_approval_revocation_per_request(self):
        """Actual HTTP route reloads deployment approvals without client authority."""
        import hashlib
        from unittest.mock import patch

        repo = self.root / "approval_http_repo"
        repo.mkdir()
        project = "game.approval.http"
        payload = dict(host_id="host.one", project_id=project, name="Approval HTTP",
                       repository_root=str(repo), staging_root=str(repo / "staging"),
                       output_root=str(repo / "output"))
        self.assertEqual(self.request("POST", "/api/game/projects", self.owner, payload)[0], 201)
        (repo / ".minglefield").mkdir()
        (repo / ".minglefield" / "project.json").write_text(
            json.dumps({"schema_version": 1, "project_id": project}))
        source = {"provider": "github", "repository": "daresan/minglefield-integration-test"}
        integration = "community.daresan.test"
        (repo / "minglefield.lock").write_text(json.dumps({
            "lock_version": "0.1", "project_id": project,
            "packages": [{"package_id": integration, "kind": "game_integration",
                          "version": "v1.0.0", "publisher": "daresan",
                          "release_source": source,
                          "artifact": {"reference": "asset", "sha256": "a" * 64}}]}))
        document = {"contract_version": "0.1", "integration_id": integration,
                    "release_source": source, "from_version": "v1.0.0",
                    "to_version": "v1.1.0",
                    "requirements": [{"capability": "game.api", "constraint": ">=1.0"}]}
        raw = json.dumps(document).encode()
        row = {"kind": "compatibility", "integration_id": integration,
               "repository": source["repository"], "from_version": "v1.0.0",
               "to_version": "v1.1.0",
               "commit": "6df11272a9ca14dcfb8dc3bbe26b29c189d12253",
               "sha256": hashlib.sha256(raw).hexdigest()}
        self.assertEqual(self.request("POST", "/api/host/settings", self.owner, {
            "host_id": "host.one", "settings": {"staging_root": "", "output_root": "",
                "trusted_integration_sources": [source["repository"]]}})[0], 200)
        manifest = self.root / "operator_approvals.json"
        self.store._host_policy._assessment_manifest_path = manifest
        self.addCleanup(setattr, self.store._host_policy, "_assessment_manifest_path", None)
        route = "/api/game/integration/releases?host_id=host.one&project_id=" + project
        registry = {"registry_version": "0.1", "integrations": [
            {"integration_id": integration, "name": "Fixture", "publisher": "daresan",
             "trust_tier": "community", "release_source": source}]}
        calls = []
        def load(*args):
            calls.append(args)
            return raw
        def releases(*args):
            return {"state": "available", "complete": True, "releases": [
                {"tag_name": "v1.1.0", "draft": False, "prerelease": False}]}
        # Capture the original callable before patching its module attribute.
        # Otherwise importing it inside patch() returns the mock itself and recurses.
        from game_integration_assessment_approvals import discover_with_operator_approvals as real
        def injected_discovery(entry, catalog, **kwargs):
            return real(entry, catalog, **{**kwargs, "fetcher": releases,
                                         "compare_fetcher": lambda *args: {"state": "unknown"}})
        with patch("game_integration_registry.load_registry", return_value=registry), patch(
                "game_integration_assessment_loader.load_pinned_assessment_bytes",
                side_effect=load), patch(
                "game_integration_assessment_approvals.discover_with_operator_approvals",
                side_effect=injected_discovery):
            manifest.write_text(json.dumps({"format_version": "0.1", "approvals": [row]}))
            self.assertEqual(self.request("GET", route)[0], 401)
            self.assertEqual(self.request("GET", route, self.other)[0], 404)
            self.assertEqual(calls, [])
            status, approved = self.request("GET", route, self.owner)
            self.assertEqual(status, 200)
            compatibility = approved["updates"][0]["preview"]["compatibility"]
            self.assertEqual(compatibility["document_provenance"], "verified")
            self.assertEqual(compatibility["state"], "unknown")
            self.assertFalse(approved["updates"][0]["installation_allowed"])
            self.assertEqual(len(calls), 1)
            manifest.write_text(json.dumps({"format_version": "0.1", "approvals": []}))
            status, revoked = self.request("GET", route, self.owner)
            self.assertEqual(status, 200)
            self.assertNotIn("document_provenance",
                             revoked["updates"][0]["preview"]["compatibility"])
            self.assertEqual(len(calls), 1)
            self.assertFalse(revoked["updates"][0]["installation_allowed"])
            manifest.unlink()
            status, missing = self.request("GET", route, self.owner)
            self.assertEqual(status, 200)
            self.assertNotIn("document_provenance",
                             missing["updates"][0]["preview"]["compatibility"])

    def test_invalid_requests_are_rejected(self):
        self.assertEqual(self.request("GET", "/api/game/projects", self.owner)[0], 400)
        self.assertEqual(self.request("GET", "/api/game/projects?host_id=a&host_id=b",
                                      self.owner)[0], 400)
        self.assertEqual(self.request("POST", "/api/game/projects", self.owner,
                                      {"host_id": "host.one"})[0], 400)


if __name__ == "__main__":
    unittest.main()
