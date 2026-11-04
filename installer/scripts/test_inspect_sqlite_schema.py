"""Tests for read-only SQLite schema inspection."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from inspect_sqlite_schema import inspect_sqlite


class SQLiteSchemaInspectionTests(unittest.TestCase):
    def test_valid_database_schema_and_version_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom.data"
            with closing(sqlite3.connect(path)) as db:
                db.execute("CREATE TABLE alpha_users (user_id TEXT PRIMARY KEY, disabled INTEGER)")
                db.execute("PRAGMA user_version=7")
                db.execute("PRAGMA application_id=123")
                db.commit()
            before = path.read_bytes()
            result = inspect_sqlite(path)
            self.assertEqual(result["status"], "sqlite_integrity_verified_schema_unclassified")
            self.assertTrue(result["integrityOk"])
            self.assertEqual(result["userVersion"], 7)
            self.assertEqual(result["applicationId"], 123)
            self.assertEqual(result["tables"][0]["name"], "alpha_users")
            self.assertIn("user_id", result["tables"][0]["columns"])
            self.assertEqual(path.read_bytes(), before)

    def test_rejects_fake_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fake.sqlite"
            path.write_bytes(b"SQLite format 3\\0" + bytes(256))
            result = inspect_sqlite(path)
            self.assertFalse(result["integrityOk"])
            self.assertNotEqual(result["status"], "sqlite_integrity_verified_schema_unclassified")

    def test_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect_sqlite(Path(tmp) / "missing.sqlite")
            self.assertEqual(result["error"], "not_a_regular_file")

    def test_reads_wal_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wal.sqlite"
            db = sqlite3.connect(path)
            try:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE alpha_jobs (job_id TEXT)")
                db.commit()
                db.execute("INSERT INTO alpha_jobs VALUES ('live')")
                db.commit()
                result = inspect_sqlite(path)
                self.assertTrue(result["integrityOk"])
                self.assertIn("alpha_jobs", [table["name"] for table in result["tables"]])
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
