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
        for _ in range(2):
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
                line = received.get(timeout=25)
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
            def http(method, endpoint, data=None, token=None):
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
            invalid, _ = http("POST", "/api/login", {
                "user_id": "mingleadmin", "password": DB_KEY})
            self.assertEqual(invalid, 401)
            ok, login = http("POST", "/api/login", {
                "user_id": "mingleadmin", "password": LOGIN_KEY})
            self.assertEqual(ok, 200)
            status, hosts = http("GET", "/api/hosts", token=login["session_token"])
            self.assertEqual(status, 200)
            self.assertEqual([h["host_id"] for h in hosts["hosts"]], ["host.local"])
            blocked, _ = http("POST", "/api/host/claim",
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
