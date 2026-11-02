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
                         'id="gameProjectCreate"', 'id="gameProjectSelect"',
                         '"/api/game/projects"', '["game","Game"]'):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, html)

    def test_invalid_requests_are_rejected(self):
        self.assertEqual(self.request("GET", "/api/game/projects", self.owner)[0], 400)
        self.assertEqual(self.request("GET", "/api/game/projects?host_id=a&host_id=b",
                                      self.owner)[0], 400)
        self.assertEqual(self.request("POST", "/api/game/projects", self.owner,
                                      {"host_id": "host.one"})[0], 400)


if __name__ == "__main__":
    unittest.main()
