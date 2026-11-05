"""Runtime SQLCipher DB-API conformance for the existing Alpha store.

Real-driver cases intentionally run against disposable temporary databases.
The existing cross-platform installation-conformance CI installs a pinned
SQLCipher binary wheel; local environments without it skip only real-driver cases.
"""
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))

from alpha_sqlcipher_runtime import (
    AlphaDatabaseOpenError, SQLITE_HEADER, open_alpha_database, sqlcipher_driver,
)
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy


KEY = "Cipher-Strong12!Test"
OTHER = "Incorrect-Cipher12!"


def real_driver_available():
    try:
        return importlib.util.find_spec("sqlcipher3") is not None
    except (ImportError, ValueError):
        return False


class RuntimeBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="minglefield-cipher-runtime-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.db = self.root / "alpha-encrypted.sqlite3"

    def test_legacy_plaintext_dev_path_preserved(self):
        store = AlphaAuthStore(self.root / "alpha-legacy.sqlite3")
        token = store.invite("local.user")
        self.assertIsNotNone(store.redeem(token, agent_id="local.agent"))
        with open(self.root / "alpha-legacy.sqlite3", "rb") as file:
            self.assertEqual(file.read(16), SQLITE_HEADER)

    def test_encrypted_mode_must_not_create_missing_file(self):
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "encrypted_database_not_found"):
            open_alpha_database(self.db, key_provider=lambda: KEY)
        self.assertFalse(self.db.exists())

    def test_plaintext_file_refuses_encrypted_mode_and_preserves_source(self):
        db = sqlite3.connect(self.db)
        db.execute("CREATE TABLE basic(value TEXT)")
        db.execute("INSERT INTO basic VALUES('unchanged')")
        db.commit()
        db.close()
        before = self.db.read_bytes()
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "encrypted_database_required"):
            open_alpha_database(self.db, key_provider=lambda: KEY)
        self.assertEqual(self.db.read_bytes(), before)

    def test_non_sqlite_ciphertext_requires_explicit_key(self):
        self.db.write_bytes(bytes(range(64)))
        before = self.db.read_bytes()
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "encrypted_database_key_required"):
            open_alpha_database(self.db)
        self.assertEqual(self.db.read_bytes(), before)

    def test_key_provider_failure_does_not_include_exception_or_secret(self):
        self.db.write_bytes(bytes(range(64)))
        def broken_provider():
            raise ValueError("sensitive password text")
        with self.assertRaises(AlphaDatabaseOpenError) as caught:
            open_alpha_database(self.db, key_provider=broken_provider)
        self.assertEqual(str(caught.exception), "database_key_unavailable")
        self.assertNotIn("sensitive", str(caught.exception))

    def test_driver_missing_fails_closed(self):
        self.db.write_bytes(bytes(range(64)))
        with patch("alpha_sqlcipher_runtime.importlib.import_module",
                   side_effect=ModuleNotFoundError("sqlcipher3 missing")):
            with self.assertRaisesRegex(AlphaDatabaseOpenError, "sqlcipher_runtime_unavailable"):
                sqlcipher_driver()
        self.assertEqual(self.db.read_bytes(), bytes(range(64)))

    def test_symlink_source_is_not_followed(self):
        target = self.root / "target.db"
        target.write_bytes(bytes(range(64)))
        try:
            self.db.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this platform")
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "database_source_not_regular"):
            open_alpha_database(self.db, key_provider=lambda: KEY)
        self.assertEqual(target.read_bytes(), bytes(range(64)))


@unittest.skipUnless(real_driver_available(), "sqlcipher3 wheel not installed")
class RealSqlcipherRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="minglefield-cipher-runtime-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.db = self.root / "alpha-encrypted.sqlite3"
        self.driver = sqlcipher_driver()

    def make_encrypted(self, key=KEY):
        db = self.driver.connect(str(self.db))
        db.execute("PRAGMA key = '" + key.replace("'", "''") + "'")
        db.execute("CREATE TABLE fixture (id INTEGER PRIMARY KEY, note TEXT)")
        db.execute("INSERT INTO fixture(note) VALUES ('original')")
        db.commit()
        db.close()
        self.assertNotEqual(self.db.read_bytes()[:16], SQLITE_HEADER)

    def test_cipher_version_and_real_reopen(self):
        self.make_encrypted()
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "encrypted_database_key_required"):
            open_alpha_database(self.db)
        db = open_alpha_database(self.db, key_provider=lambda: KEY)
        self.assertEqual(db.execute("SELECT note FROM fixture").fetchone(), ("original",))
        self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        db.close()

    def test_wrong_key_and_plaintext_module_cannot_read(self):
        self.make_encrypted()
        original = self.db.read_bytes()
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "sqlcipher_unlock_or_open_failed"):
            open_alpha_database(self.db, key_provider=lambda: OTHER)
        self.assertEqual(self.db.read_bytes(), original)
        with self.assertRaises(sqlite3.DatabaseError):
            db = sqlite3.connect(f"{self.db.as_uri()}?mode=ro", uri=True)
            try:
                db.execute("SELECT count(*) FROM sqlite_schema").fetchone()
            finally:
                db.close()

    def test_password_with_apostrophes_is_never_evaluated_as_sql(self):
        literal = "A'post; -- New-Key12!"
        self.make_encrypted(literal)
        db = open_alpha_database(self.db, key_provider=lambda: literal)
        self.assertEqual(db.execute("SELECT note FROM fixture").fetchone()[0], "original")
        db.close()

    def test_local_auth_and_host_policy_use_same_encrypted_database(self):
        self.make_encrypted()
        store = AlphaAuthStore(self.db, sqlcipher_key_provider=lambda: KEY)
        invite = store.invite("user.alpha")
        session = store.redeem(invite, agent_id="agent.alpha", password="local-password-123")
        self.assertIsNotNone(session)
        self.assertEqual(store.principal("Bearer " + session).user_id, "user.alpha")
        admission = IntegratedAlphaAdmission(store)
        policy = HostCommitPolicy(admission)
        with store._tx() as db:
            db.execute("INSERT INTO sec01_host_owners VALUES(?,?)", ("host.alpha", "user.alpha"))
        directory = str(self.root / "project")
        result = policy.create_game_project(
            "host.alpha", "user.alpha", "project.one", "Demo",
            directory, directory, directory,
        )
        self.assertEqual(result.state, "created")
        duplicate = policy.create_game_project(
            "host.alpha", "user.alpha", "project.one", "Demo",
            directory, directory, directory,
        )
        self.assertEqual(duplicate.reason, "project_id_exists")
        reread = AlphaAuthStore(self.db, sqlcipher_key_provider=lambda: KEY)
        self.assertEqual(reread.principal("Bearer " + session).user_id, "user.alpha")
        self.assertNotEqual(self.db.read_bytes()[:16], SQLITE_HEADER)

    def test_encrypted_store_rejects_wrong_password_before_any_write(self):
        self.make_encrypted()
        before = self.db.read_bytes()
        with self.assertRaisesRegex(AlphaDatabaseOpenError, "sqlcipher_unlock_or_open_failed"):
            AlphaAuthStore(self.db, sqlcipher_key_provider=lambda: OTHER)
        self.assertEqual(self.db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
