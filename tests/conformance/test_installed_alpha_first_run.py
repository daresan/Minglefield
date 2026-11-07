"""Real SQLCipher private first-run worker: atomic local-only Host onboarding."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SERVER = Path(__file__).resolve().parents[2] / "server"
sys.path.insert(0, str(SERVER))
from alpha_sqlcipher_runtime import AlphaDatabaseOpenError, sqlcipher_driver, SQLITE_HEADER
from private_alpha_auth import AlphaAuthStore

DB_KEY = "Private-First-Run-SQLCipher-Password123!"
LOGIN_KEY = "Independent-First-Run-Signin-Password123!"


def available():
    try:
        sqlcipher_driver()
        return True
    except AlphaDatabaseOpenError:
        return False


@unittest.skipUnless(available(), "real SQLCipher runtime required")
class InstalledAlphaFirstRunTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="minglefield-first-run-")
        self.addCleanup(folder.cleanup)
        self.db = Path(folder.name) / "encrypted.sqlite3"
        driver = sqlcipher_driver()
        with driver.connect(str(self.db)) as connection:
            connection.execute("PRAGMA key = '" + DB_KEY + "'")
            connection.execute("CREATE TABLE imported_data(value TEXT NOT NULL)")
            connection.execute("INSERT INTO imported_data VALUES('preserved')")
        self.assertNotEqual(self.db.read_bytes()[:16], SQLITE_HEADER)

    def invoke_worker(self, **changes):
        request = {
            "version": 1, "databasePath": str(self.db),
            "sqlcipherKey": DB_KEY, "loginUserId": "mingleadmin",
            "loginPassword": LOGIN_KEY, "localHostId": "host.local"
        }
        request.update(changes)
        args = [sys.executable, "-I", "-B", str(SERVER / "installed_alpha_first_run.py")]
        self.assertNotIn(DB_KEY, " ".join(args))
        return subprocess.run(args, input=json.dumps(request).encode(),
                              capture_output=True, timeout=75, check=False)

    def test_first_run_is_atomic_and_replay_denied_and_source_data_preserved(self):
        first = self.invoke_worker()
        self.assertEqual(first.returncode, 0, first.stderr)
        receipt = json.loads(first.stdout)
        self.assertEqual(receipt["status"], "local_host_admin_created")
        self.assertEqual(receipt["loginUserId"], "mingleadmin")
        self.assertEqual(receipt["localHostId"], "host.local")
        self.assertIs(receipt["remoteHostAuthorityGranted"], False)
        self.assertNotIn(DB_KEY.encode(), first.stdout + first.stderr)
        self.assertNotIn(LOGIN_KEY.encode(), first.stdout + first.stderr)
        second = self.invoke_worker()
        self.assertEqual(second.returncode, 3)
        self.assertIn(b'"status": "denied"', second.stdout)
        self.assertNotIn(DB_KEY.encode(), second.stdout + second.stderr)
        store = AlphaAuthStore(self.db, sqlcipher_key_provider=lambda: DB_KEY)
        with store._tx() as connection:
            self.assertEqual(connection.execute(
                "SELECT value FROM imported_data").fetchone(), ("preserved",))
            self.assertEqual(connection.execute(
                "SELECT owner_id FROM sec01_host_owners WHERE host_id=?",
                ("host.local",)).fetchone(), ("mingleadmin",))
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM sec01_host_owners").fetchone()[0], 1)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM alpha_users").fetchone()[0], 1)
            self.assertIsNone(connection.execute(
                "SELECT owner_id FROM sec01_host_owners WHERE host_id=?",
                ("host.remote",)).fetchone())
        self.assertIsNotNone(store.login("mingleadmin", LOGIN_KEY))
        self.assertIsNone(store.login("mingleadmin", DB_KEY))

    def test_rejects_bad_keys_and_equal_login_password_before_owner_write(self):
        before = self.db.read_bytes()
        wrong = self.invoke_worker(sqlcipherKey="Incorrect-Cipher-Key123!")
        self.assertEqual(wrong.returncode, 2)
        self.assertEqual(wrong.stdout, b"")
        self.assertNotIn(b"Incorrect-Cipher-Key123!", wrong.stderr)
        identical = self.invoke_worker(loginPassword=DB_KEY)
        self.assertEqual(identical.returncode, 3)
        self.assertEqual(json.loads(identical.stdout)["status"], "denied")
        self.assertEqual(self.db.read_bytes(), before)

    def test_rejects_existing_host_or_existing_identity_without_reassignment(self):
        created = self.invoke_worker(loginUserId="user.one", localHostId="host.one")
        self.assertEqual(created.returncode, 0)
        conflict = self.invoke_worker(loginUserId="user.two", localHostId="host.one")
        self.assertEqual(conflict.returncode, 3)
        duplicate_user = self.invoke_worker(loginUserId="user.one", localHostId="host.two")
        self.assertEqual(duplicate_user.returncode, 3)
        store = AlphaAuthStore(self.db, sqlcipher_key_provider=lambda: DB_KEY)
        with store._tx() as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM sec01_host_owners").fetchone()[0], 1)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM alpha_users").fetchone()[0], 1)

    def test_unknown_fields_are_never_promoted_to_native_authority(self):
        result = self.invoke_worker(grantRemoteAdmin=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertNotIn(DB_KEY.encode(), result.stderr)


if __name__ == "__main__":
    unittest.main()
