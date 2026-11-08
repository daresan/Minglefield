"""The installed Alpha must actually reopen its SQLCipher DB over loopback.

These tests reuse the existing store, local Host policy and HTTP handler.
They do not grant first-run consent or implement a native installer command.
"""
import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

from alpha_sqlcipher_runtime import (
    AlphaDatabaseOpenError, SQLITE_HEADER, sqlcipher_driver
)
from private_alpha_gateway import create_installed_local_alpha_server
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy

CIPHER_KEY = "M2InstalledCipherKey123!"
SIGNIN_KEY = "M2IndependentLoginKey456!"


def driver_ready():
    try:
        sqlcipher_driver()
        return True
    except AlphaDatabaseOpenError:
        return False


class InstalledGatewayFailClosedTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="minglefield-installed-runtime-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "operational.sqlite3"

    def test_absent_and_plaintext_targets_cannot_start(self):
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "installed_database_path_invalid"):
            create_installed_local_alpha_server(
                self.path, key_provider=lambda: CIPHER_KEY, port=0)
        self.assertFalse(self.path.exists())
        plain = sqlite3.connect(self.path)
        plain.execute("CREATE TABLE example(value TEXT)")
        plain.commit()
        plain.close()
        before = self.path.read_bytes()
        self.assertEqual(before[:16], SQLITE_HEADER)
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "encrypted_database_required"):
            create_installed_local_alpha_server(
                self.path, key_provider=lambda: CIPHER_KEY, port=0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_no_implicit_key_and_no_bypass_via_bad_port_or_relative_path(self):
        self.path.write_bytes(bytes(range(64)))
        for candidate in (None, "not-a-provider"):
            with self.assertRaisesRegex(AlphaDatabaseOpenError, "installed_database_key_required"):
                create_installed_local_alpha_server(
                    self.path, key_provider=candidate, port=0)
        for candidate in (-1, 65536, True, "8767"):
            with self.assertRaisesRegex(AlphaDatabaseOpenError, "installed_database_path_invalid"):
                create_installed_local_alpha_server(
                    self.path, key_provider=lambda: CIPHER_KEY, port=candidate)
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "installed_database_path_invalid"):
            create_installed_local_alpha_server(
                Path("relative.sqlite3"), key_provider=lambda: CIPHER_KEY, port=0)

    def test_missing_key_does_not_leak_exception_message(self):
        self.path.write_bytes(bytes(range(64)))
        def unavailable():
            raise RuntimeError("must-not-appear-in-diagnostics")
        with self.assertRaises(AlphaDatabaseOpenError) as captured:
            create_installed_local_alpha_server(self.path, key_provider=unavailable, port=0)
        self.assertEqual(str(captured.exception), "database_key_unavailable")


@unittest.skipUnless(driver_ready(), "real SQLCipher runtime required")
class InstalledGatewayRealCipherTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="minglefield-installed-runtime-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "operational.sqlite3"
        driver = sqlcipher_driver()
        with driver.connect(str(self.path)) as db:
            db.execute("PRAGMA key = '" + CIPHER_KEY + "'")
            db.execute("CREATE TABLE original_fixture(note TEXT NOT NULL)")
            db.execute("INSERT INTO original_fixture VALUES('unchanged')")
        self.assertNotEqual(self.path.read_bytes()[:16], SQLITE_HEADER)
        store = AlphaAuthStore(self.path, sqlcipher_key_provider=lambda: CIPHER_KEY)
        policy = HostCommitPolicy(IntegratedAlphaAdmission(store))
        result = policy.provision_first_run_local_host_admin_trusted(
            "host.local", SIGNIN_KEY)
        self.assertEqual(result.state, "created")

    def request(self, server, method, path, payload=None, session=None):
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        headers = {"Host": f"127.0.0.1:{server.server_port}"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if session is not None:
            headers["Authorization"] = "Bearer " + session
        try:
            connection.request(method, path,
                               body=json.dumps(payload) if payload is not None else None,
                               headers=headers)
            response = connection.getresponse()
            status = response.status
            body = response.read(128 * 1024)
            return status, json.loads(body) if body else None
        finally:
            connection.close()

    def open_and_serve(self):
        calls = []
        def provide_key():
            calls.append(1)
            return CIPHER_KEY
        server = create_installed_local_alpha_server(
            self.path, key_provider=provide_key, port=0)
        self.assertEqual(calls, [1])
        self.assertEqual(server.server_address[0], "127.0.0.1")
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        return server, worker

    def test_local_login_persists_across_server_restart_with_real_host_scope(self):
        prior_session = None
        for _ in range(2):
            server, worker = self.open_and_serve()
            try:
                # A previously issued bearer remains usable after restart,
                # provided its client still has it and it is not expired/revoked.
                # Host ownership is not an ephemeral installer token.
                if prior_session is not None:
                    prior_status, prior_hosts = self.request(
                        server, "GET", "/api/hosts", session=prior_session)
                    self.assertEqual(prior_status, 200)
                    self.assertEqual(
                        [host["host_id"] for host in prior_hosts["hosts"]],
                        ["host.local"])
                wrong, _ = self.request(server, "POST", "/api/login", {
                    "user_id": "mingleadmin", "password": CIPHER_KEY})
                self.assertEqual(wrong, 401)
                ok, session_reply = self.request(server, "POST", "/api/login", {
                    "user_id": "mingleadmin", "password": SIGNIN_KEY})
                self.assertEqual(ok, 200)
                self.assertIn("session_token", session_reply)
                token = session_reply["session_token"]
                if prior_session is None:
                    prior_session = token
                status, listing = self.request(server, "GET", "/api/hosts", session=token)
                self.assertEqual(status, 200)
                self.assertEqual(
                    [host["host_id"] for host in listing["hosts"]], ["host.local"])
                # The installed runtime never accepts the old console code
                # as an unattended replacement for local first-run consent.
                denied, _ = self.request(server, "POST", "/api/host/claim",
                    {"host_id": "host.remote", "bootstrap_secret": "guess"},
                    session=token)
                self.assertEqual(denied, 403)
                status, again = self.request(server, "GET", "/api/hosts", session=token)
                self.assertEqual(status, 200)
                self.assertEqual(len(again["hosts"]), 1)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())

        store = AlphaAuthStore(self.path, sqlcipher_key_provider=lambda: CIPHER_KEY)
        with store._tx() as db:
            self.assertEqual(
                db.execute("SELECT note FROM original_fixture").fetchone(),
                ("unchanged",))
            self.assertEqual(
                db.execute("SELECT owner_id FROM sec01_host_owners WHERE host_id=?",
                           ("host.local",)).fetchone(), ("mingleadmin",))
            self.assertIsNone(db.execute(
                "SELECT owner_id FROM sec01_host_owners WHERE host_id=?",
                ("host.remote",)).fetchone())

    def test_host_admin_grants_require_session_scope_and_db_key(self):
        # An installer-created mingleadmin grants only existing-user Host roles,
        # not SQLCipher/database privileges or ownership.
        store = AlphaAuthStore(self.path, sqlcipher_key_provider=lambda: CIPHER_KEY)
        store.redeem(store.invite("user.friend"), password="FriendLoginPassword123!")
        store.redeem(store.invite("user.other"), password="OtherLoginPassword123!")
        server, worker = self.open_and_serve()
        try:
            admin_session = self.request(server, "POST", "/api/login", {
                "user_id": "mingleadmin", "password": SIGNIN_KEY})[1]["session_token"]
            friend_session = self.request(server, "POST", "/api/login", {
                "user_id": "user.friend", "password": "FriendLoginPassword123!"
            })[1]["session_token"]
            uri = "/api/host/admin-users?host_id=host.local"
            self.assertEqual(self.request(server, "GET", uri)[0], 401)
            self.assertEqual(self.request(server, "GET", uri, session=friend_session)[0], 403)
            status, listing = self.request(server, "GET", uri, session=admin_session)
            self.assertEqual(status, 200)
            users = {row["user_id"]: row for row in listing["users"]}
            self.assertTrue(users["mingleadmin"]["is_host_owner"])
            self.assertFalse(users["user.friend"]["is_host_admin"])
            payload = {"host_id": "host.local", "user_ids": ["user.friend"],
                       "database_password": CIPHER_KEY}
            self.assertEqual(self.request(
                server, "POST", "/api/host/admin-users", payload,
                session=friend_session)[0], 403)
            wrong = dict(payload, database_password="WrongDatabasePassword123!")
            self.assertEqual(self.request(
                server, "POST", "/api/host/admin-users", wrong,
                session=admin_session)[0], 403)
            self.assertEqual(self.request(
                server, "GET", uri, session=admin_session)[1]["users"][1]["is_host_admin"],
                False)
            self.assertEqual(self.request(
                server, "POST", "/api/host/admin-users", payload,
                session=admin_session)[0], 200)
            # An existing Host admin may grant another existing user for this
            # Host using one DB-key confirmation; the original owner is intact.
            other_payload = {"host_id": "host.local", "user_ids": ["user.other"],
                             "database_password": CIPHER_KEY}
            self.assertEqual(self.request(
                server, "POST", "/api/host/admin-users", other_payload,
                session=friend_session)[0], 200)
            self.assertEqual(self.request(
                server, "POST", "/api/host/admin-users", payload,
                session=admin_session)[0], 200)
            self.assertEqual(self.request(
                server, "GET", uri, session=friend_session)[0], 200)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
        with store._tx() as db:
            self.assertEqual(db.execute(
                "SELECT owner_id FROM sec01_host_owners WHERE host_id='host.local'"
            ).fetchone(), ("mingleadmin",))
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM sec01_host_owners").fetchone(), (1,))
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM sec01_host_admins WHERE host_id='host.local'"
            ).fetchone(), (2,))
            self.assertEqual(db.execute(
                "SELECT count(*) FROM alpha_users").fetchone(), (3,))
            self.assertEqual(db.execute(
                "SELECT note FROM original_fixture").fetchone(), ("unchanged",))

    def test_wrong_key_rejects_launch_without_writing_database(self):
        before = self.path.read_bytes()
        with self.assertRaisesRegex(
                AlphaDatabaseOpenError, "sqlcipher_unlock_or_open_failed"):
            create_installed_local_alpha_server(
                self.path, key_provider=lambda: "WrongCipherKey0123!", port=0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_encrypted_file_never_reverts_to_legacy_sqlite(self):
        with self.assertRaises(sqlite3.DatabaseError):
            connection = sqlite3.connect(
                self.path.as_uri() + "?mode=ro", uri=True)
            try:
                connection.execute("SELECT count(*) FROM alpha_users").fetchone()
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
