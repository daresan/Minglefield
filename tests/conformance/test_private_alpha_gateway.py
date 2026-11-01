"""Private Alpha loopback gateway tests. Never starts public listeners/effects."""
import http.client
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from private_alpha_gateway import (
    AlphaSimulation, TestPrincipal as PrincipalFixture, handler_for)


class PrivateAlphaGatewayTests(unittest.TestCase):
    def setUp(self):
        self.a = "a" * 48
        self.b = "b" * 48
        self.sim = AlphaSimulation({
            self.a: PrincipalFixture("user.alpha", "agent.alpha"),
            self.b: PrincipalFixture("user.beta", "agent.beta")})
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.sim))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def request(self, method, path, *, token=None, payload=None, raw=None, headers=None):
        con = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=3)
        h = dict(headers or {})
        if token is not None:
            h["Authorization"] = "Bearer " + token
        if payload is not None:
            raw = json.dumps(payload).encode()
            h["Content-Type"] = "application/json"
        try:
            con.request(method, path, body=raw, headers=h)
            response = con.getresponse()
            content = response.read()
            return response.status, response.getheader("Content-Type"), content
        finally:
            con.close()

    def test_health_and_client_are_local_simulation(self):
        status, _, body = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "simulation_only")
        status, kind, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", kind)
        self.assertIn(b"Local Alpha", html)
        self.assertEqual(self.http.server_address[0], "127.0.0.1")

    def test_unauthenticated_api_is_denied(self):
        for method, path in (("GET", "/api/agents"), ("GET", "/api/jobs"),
                             ("POST", "/api/jobs")):
            with self.subTest(method=method, path=path):
                status, _, _ = self.request(method, path)
                self.assertEqual(status, 401)

    def test_agent_and_job_isolation(self):
        a = json.loads(self.request("GET", "/api/agents", token=self.a)[2])
        b = json.loads(self.request("GET", "/api/agents", token=self.b)[2])
        self.assertEqual(a["agents"][0]["agent_id"], "agent.alpha")
        self.assertEqual(b["agents"][0]["agent_id"], "agent.beta")
        payload = {"action": "demo.echo", "idempotency_key": "request.1"}
        status, _, body = self.request("POST", "/api/jobs", token=self.a, payload=payload)
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)["state"], "simulated_no_effect")
        jobs_a = json.loads(self.request("GET", "/api/jobs", token=self.a)[2])["jobs"]
        jobs_b = json.loads(self.request("GET", "/api/jobs", token=self.b)[2])["jobs"]
        self.assertEqual(len(jobs_a), 1)
        self.assertEqual(jobs_b, [])
        self.assertEqual(jobs_a[0]["user_id"], "user.alpha")

    def test_idempotency_and_quota(self):
        for i in range(5):
            status, _, body = self.request(
                "POST", "/api/jobs", token=self.a,
                payload={"action": "demo.echo", "idempotency_key": str(i)})
            self.assertEqual(status, 201)
        duplicate = self.request(
            "POST", "/api/jobs", token=self.a,
            payload={"action": "demo.echo", "idempotency_key": "0"})
        self.assertEqual(duplicate[0], 200)
        self.assertEqual(self.request(
            "POST", "/api/jobs", token=self.a,
            payload={"action": "demo.echo", "idempotency_key": "more"})[0], 429)

    def test_invalid_actions_and_input_fail_closed(self):
        self.assertEqual(self.request("POST", "/api/jobs", token=self.a,
            payload={"action": "shell.exec", "idempotency_key": "x"})[0], 400)
        self.assertEqual(self.request("POST", "/api/jobs", token=self.a,
            payload={"action": "demo.echo", "idempotency_key": "x",
                     "target_id": "other"})[0], 400)
        self.assertEqual(self.request("POST", "/api/jobs", token=self.a,
            raw=b"broken", headers={"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("POST", "/api/jobs", token=self.a,
            raw=b"{}", headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.sim.jobs(PrincipalFixture("user.alpha", "agent.alpha")), [])

    def test_unknown_tokens_and_paths_are_not_authorized(self):
        self.assertEqual(self.request("GET", "/api/agents", token="wrong")[0], 401)
        self.assertEqual(self.request("GET", "/api/unknown", token=self.a)[0], 404)
        self.assertEqual(self.request("POST", "/api/unknown", token=self.a)[0], 404)


if __name__ == "__main__":
    unittest.main()
