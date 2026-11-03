"""SQLite crash-boundary tests for the internal cleanup progress journal."""
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_progress_journal import (
    ensure_cleanup_progress_schema, begin_cleanup_file,
    finish_cleanup_file, inspect_cleanup_progress)

DIGEST = "a" * 64


class CleanupProgressJournalTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        ensure_cleanup_progress_schema(self.db)
        self.db.commit()

    def test_intent_survives_restart_boundary_without_replay(self):
        result = begin_cleanup_file(self.db, "op.one", DIGEST, "blob-000000")
        self.assertEqual(result["state"], "intent")
        self.db.commit()
        status = inspect_cleanup_progress(self.db, "op.one", DIGEST)
        self.assertEqual(status["state"], "manual_recovery_required")
        self.assertFalse(status["auto_retry_allowed"])
        self.assertEqual(begin_cleanup_file(
            self.db, "op.one", DIGEST, "blob-000000")["state"], "blocked")

    def test_success_and_partial_failure(self):
        begin_cleanup_file(self.db, "op.one", DIGEST, "blob-000000")
        self.db.commit()
        self.assertEqual(finish_cleanup_file(
            self.db, "op.one", DIGEST, "blob-000000",
            observed_deleted=True)["state"], "removed")
        self.db.commit()
        begin_cleanup_file(self.db, "op.one", DIGEST, "manifest.json")
        self.db.commit()
        self.assertEqual(finish_cleanup_file(
            self.db, "op.one", DIGEST, "manifest.json")["state"], "uncertain")
        status = inspect_cleanup_progress(self.db, "op.one", DIGEST)
        self.assertEqual(status["removed_files"], ["blob-000000"])
        self.assertEqual(status["unresolved_files"], ["manifest.json"])
        self.assertEqual(status["state"], "manual_recovery_required")

    def test_digest_conflict_and_duplicate_intent_fail_closed(self):
        begin_cleanup_file(self.db, "op.one", DIGEST, "blob-000000")
        self.assertEqual(begin_cleanup_file(
            self.db, "op.one", "b" * 64, "blob-000000")["reason"],
            "cleanup_progress_plan_changed")
        self.assertEqual(inspect_cleanup_progress(
            self.db, "op.one", "b" * 64)["state"], "blocked")

    def test_no_unrecorded_confirmation(self):
        self.assertEqual(finish_cleanup_file(
            self.db, "op.one", DIGEST, "blob-000000",
            observed_deleted=True)["state"], "blocked")

    def test_transaction_rollback_removes_uncommitted_intent(self):
        begin_cleanup_file(self.db, "op.one", DIGEST, "blob-000000")
        self.db.rollback()
        self.assertEqual(inspect_cleanup_progress(
            self.db, "op.one", DIGEST)["removed_files"], [])

    def test_invalid_names_rejected(self):
        for name in ("../manifest.json", "blob-000001/other", "unknown"):
            self.assertEqual(begin_cleanup_file(
                self.db, "op.one", DIGEST, name)["state"], "blocked")
