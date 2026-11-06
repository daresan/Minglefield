"""Executable M2 Alpha gateway process: real DB, private key handoff, login.

Uses the application's existing HTTP/Host policy, not a second gateway,
and disposable fixtures only; no direct first-run provisioning endpoint.
"""
import http.client
import json
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2] / "server"
sys.path.insert(0, str(SERVER))
from alpha_sqlcipher_runtime import SQLITE_HEADER, sqlcipher_driver, AlphaDatabaseOpenError
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy

DB_KEY = "LauncherCipherKey123!"
LOGIN_KEY = "SeparateLauncherLogin123!"


def driver_available():
    try:
        sqlcipher_driver()
        return True
    except AlphaDatabaseOpenError:
        return False


class InstalledAlphaProcessTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="minglefield-alpha-launch-")
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "installed.sqlite3"

    def spawn(self, payload):
        # -I: do not inherit PYTHONPATH/user site; -B: no pycache writes.
        args = [sys.executable, "-I", "-B", str(SERVER / "installed_alpha_launch.py")]
        self.assertNotIn(DB_KEY, " ".join(args))
        self.assertNotIn(LOGIN_KEY, " ".join(args))
        child = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, bufsize=0)
        self.addCleanup(self.finish, child)
        child.stdin.write(payload)
        child.stdin.close()
        return child

    @staticmethod
    def finish(child):
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=8)
        for handle in (child.stdout, child.stderr):
            handle.close()

    def test_unknown_fields_and_invalid_frames_never_start(self):
        for payload in [
            b'',
            b'x' * 8193,
            b'{"version":1}',
            json.dumps({"version": 1, "databasePath": str(self.db),
                        "sqlcipherKey": DB_KEY, "port": 0,
                        "provisionHost": True}).encode(),
            json.dumps({"version": 1, "databasePath": str(self.db),
                        "sqlcipherKey": DB_KEY, "port": True}).encode(),
        ]:
            child = self.spawn(payload)
            out, err = child.communicate(timeout=8) if child.stdin is None else (
                child.stdout.read(), child.stderr.read())
            self.assertEqual(child.wait(timeout=8), 2)
            self.assertEqual(out, b"")
            self.assertIn(b"installed_alpha_start_rejected", err)
            self.assertNotIn(DB_KEY.encode(), err)
            self.assertNotIn(str(self.db).encode(), err)
        self.assertFalse(self.db.exists())

    @unittest.skipUnless(driver_available(), "real SQLCipher wheel unavailable")
    def test_installed_process_authenticates_and_restarts_without_an_invite(self):
        driver = sqlcipher_driver()
        with driver.connect(str(self.db)) as db:
            db.execute("PRAGMA key = '" + DB_KEY + "'")
            db.execute("CREATE TABLE preserved_fixture(value TEXT)")
            db.execute("INSERT INTO preserved_fixture VALUES('unchanged')")
        store = AlphaAuthStore(self.db, sqlcipher_key_provider=lambda: DB_KEY)
        policy = HostCommitPolicy(IntegratedAlphaAdmission(store))
        self.assertEqual(policy.provision_first_run_local_host_admin_trusted(
            "host.local", LOGIN_KEY).state, "created")
        self.assertNotEqual(self.db.read_bytes()[:16], SQLITE_HEADER)
        self.assertFalse(list(self.db.parent.glob("*.secret")))
        for cycle in range(2):
            request = {
                "version": 1, "databasePath": str(self.db),
                "sqlcipherKey": DB_KEY, "port": 0
            }
            child = self.spawn(json.dumps(request).encode())
            received = queue.Queue(maxsize=1)
            reader = threading.Thread(
                target=lambda: received.put(child.stdout.readline()), daemon=True)
            reader.start()
            try:
                # Cold macOS SQLCipher initialization may exceed 25 seconds
                # when setting up the full Host runtime on a CI worker.
                # This is a bounded readiness check, not a latency SLA.
                line = received.get(timeout=90)
            except queue.Empty:
                self.fail("installed Alpha did not report ready within test deadline")
            self.assertTrue(line, "installed Alpha exited before ready")
            self.assertNotIn(DB_KEY.encode(), line)
            ready = json.loads(line)
            self.assertEqual(ready["status"], "ready")
            self.assertEqual(ready["bind"], "127.0.0.1")
            self.assertTrue(ready["encryptedDatabase"])
            self.assertFalse(ready["hostClaimBootstrapEnabled"])
            port = ready["port"]
            def request_local(method, endpoint, data=None, token=None):
                c = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
                headers = {"Host": f"127.0.0.1:{port}"}
                if data is not None:
                    headers["Content-Type"] = "application/json"
                if token is not None:
                    headers["Authorization"] = "Bearer " + token
                try:
                    c.request(method, endpoint,
                              body=json.dumps(data) if data is not None else None,
                              headers=headers)
                    result = c.getresponse()
                    return result.status, json.loads(result.read(1024 * 100))
                finally:
                    c.close()
            invalid, _ = request_local("POST", "/api/login", {
                "user_id": "mingleadmin", "password": DB_KEY})
            self.assertEqual(invalid, 401)
            ok, login = request_local("POST", "/api/login", {
                "user_id": "mingleadmin", "password": LOGIN_KEY})
            self.assertEqual(ok, 200)
            status, hosts = request_local("GET", "/api/hosts", token=login["session_token"])
            self.assertEqual(status, 200)
            self.assertEqual([h["host_id"] for h in hosts["hosts"]], ["host.local"])

            # Exercise the actual installed HTTP API once, then query all
            # persisted Host/Effect/Job/Game rows after the process restarts.
            if cycle == 0:
                effect_status, effect = request_local(
                    "POST", "/api/host/effects",
                    {"host_id": "host.local", "effect_id": "effect.local",
                     "description": "local-only demo", "enabled": True},
                    token=login["session_token"])
                self.assertEqual(effect_status, 200)
                self.assertEqual(effect["state"], "saved")
                job_status, job = request_local(
                    "POST", "/api/host/effects/manual",
                    {"host_id": "host.local", "effect_id": "effect.local"},
                    token=login["session_token"])
                self.assertEqual(job_status, 200)
                self.assertEqual(job["state"], "queued_mock")
                root = str(self.db.parent / "project-root")
                game_status, game = request_local(
                    "POST", "/api/game/projects",
                    {"host_id": "host.local", "project_id": "game.local",
                     "name": "Local Alpha", "repository_root": root,
                     "job_attachments_root": root, "output_root": root},
                    token=login["session_token"])
                self.assertEqual(game_status, 201)
                self.assertEqual(game["state"], "created")
                settings_status, _ = request_local(
                    "POST", "/api/host/settings",
                    {"host_id": "host.local",
                     "settings": {"job_attachments_root": root,
                                  "output_root": root,
                                  "trusted_integration_sources": []}},
                    token=login["session_token"])
                self.assertEqual(settings_status, 200)

            status, jobs = request_local(
                "GET", "/api/host/jobs?host_id=host.local",
                token=login["session_token"])
            self.assertEqual(status, 200)
            self.assertEqual(len(jobs["jobs"]), 1)
            status, projects = request_local(
                "GET", "/api/game/projects?host_id=host.local",
                token=login["session_token"])
            self.assertEqual(status, 200)
            self.assertEqual(len(projects["projects"]), 1)
            self.assertEqual(projects["projects"][0]["project_id"], "game.local")
            status, settings = request_local(
                "GET", "/api/host/settings?host_id=host.local",
                token=login["session_token"])
            self.assertEqual(status, 200)
            self.assertEqual(settings["settings"]["trusted_integration_sources"], [])
            for endpoint in (
                "/api/host/jobs?host_id=host.remote",
                "/api/game/projects?host_id=host.remote"
            ):
                denied_status, _ = request_local(
                    "GET", endpoint, token=login["session_token"])
                self.assertEqual(denied_status, 403)

            blocked, _ = request_local("POST", "/api/host/claim",
                              {"host_id": "host.remote", "bootstrap_secret": "anything"},
                              token=login["session_token"])
            self.assertEqual(blocked, 403)
            self.finish(child)
            self.assertNotIn(DB_KEY.encode(), self.db.read_bytes())
            self.assertNotIn(LOGIN_KEY.encode(), self.db.read_bytes())
        with store._tx() as db:
            self.assertEqual(db.execute(
                "SELECT value FROM preserved_fixture").fetchone(), ("unchanged",))
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM sec01_host_owners").fetchone()[0], 1)
            for table in (
                "sec01_host_settings", "sec01_host_effect_definitions",
                "sec01_host_jobs", "alpha_game_projects"
            ):
                self.assertEqual(db.execute(
                    "SELECT COUNT(*) FROM " + table).fetchone()[0], 1)

    @unittest.skipUnless(driver_available(), "real SQLCipher wheel unavailable")
    def test_wrong_cipher_key_rejects_before_listening_without_leaking_it(self):
        driver = sqlcipher_driver()
        with driver.connect(str(self.db)) as db:
            db.execute("PRAGMA key = '" + DB_KEY + "'")
            db.execute("CREATE TABLE fixture(value TEXT)")
        before = self.db.read_bytes()
        bad_key = "IncorrectCipherKey456!"
        child = self.spawn(json.dumps({
            "version": 1, "databasePath": str(self.db),
            "sqlcipherKey": bad_key, "port": 0
        }).encode())
        out = child.stdout.read()
        err = child.stderr.read()
        self.assertEqual(child.wait(timeout=8), 2)
        self.assertEqual(out, b"")
        self.assertNotIn(bad_key.encode(), err)
        self.assertNotIn(str(self.db).encode(), err)
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
