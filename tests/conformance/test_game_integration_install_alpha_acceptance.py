"""P1.4f.4 alpha acceptance: synthetic manifests, recovery, owner and cleanup evidence."""
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_staging import validate_staging_manifest
from game_integration_install_cleanup import inspect_staging_cleanup
from game_integration_install_recovery import inspect_staged_installation
from game_integration_install_cleanup_windows_progress import (
    inspect_windows_cleanup_recovery)
from game_integration_install_cleanup_progress_journal import (
    ensure_cleanup_progress_schema, begin_cleanup_file, finish_cleanup_file,
    inspect_cleanup_progress)

DIGEST = "a" * 64
EXPECTED = ["blob-000000", "blob-000001", "manifest.json"]


class GameInstallationAlphaAcceptanceTests(unittest.TestCase):
    def test_invalid_plan_is_rejected(self):
        self.assertEqual(validate_staging_manifest([
            {"path": "../escape", "sha256": DIGEST, "size": 1}
        ])["state"], "blocked")

    def test_wrong_owner_is_rejected_without_filesystem_mutation(self):
        entries = [{"path": "game/file.txt", "sha256": DIGEST, "size": 1}]
        plan = validate_staging_manifest(entries)
        with tempfile.TemporaryDirectory() as root:
            operation = Path(root) / "op.one"
            operation.mkdir()
            sentinel = operation / "sentinel"
            sentinel.write_bytes(b"untouched")
            result = inspect_staging_cleanup(
                root, "op.one", entries, journal_operation_id="op.one",
                journal_plan_sha256=plan["plan_sha256"],
                journal_state="cancelled", owner_authorized=False)
            self.assertEqual(result["reason"], "owner_authorization_required")
            self.assertEqual(sentinel.read_bytes(), b"untouched")

    def test_wrong_digest_is_rejected(self):
        entries = [{"path": "game/file.txt", "sha256": DIGEST, "size": 1}]
        with tempfile.TemporaryDirectory() as root:
            result = inspect_staging_cleanup(
                root, "op.one", entries, journal_operation_id="op.one",
                journal_plan_sha256="b" * 64,
                journal_state="cancelled", owner_authorized=True)
            self.assertEqual(result["reason"], "journal_cleanup_not_authorized")

    def test_corrupted_staging_is_not_eligible(self):
        entries = [{"path": "game/file.txt",
                    "sha256": hashlib.sha256(b"correct").hexdigest(),
                    "size": len(b"correct")}]
        plan = validate_staging_manifest(entries)
        with tempfile.TemporaryDirectory() as root:
            operation = Path(root) / "op.one"
            operation.mkdir()
            (operation / "blob-000000").write_bytes(b"tampered")
            (operation / "manifest.json").write_text(
                json.dumps({"plan_sha256": plan["plan_sha256"],
                            "files": [
                                {"path": item["path"], "blob": f"blob-{i:06d}",
                                 "size": item["size"], "sha256": item["sha256"]}
                                for i, item in enumerate(plan["files"])
                            ]}), encoding="utf-8")
            recovery = inspect_staged_installation(root, "op.one", entries)
            self.assertEqual(recovery["state"], "damaged", recovery)
            self.assertEqual(recovery["reason"], "blob_mismatch", recovery)
            self.assertFalse(recovery["installation_allowed"])
            result = inspect_staging_cleanup(
                root, "op.one", entries, journal_operation_id="op.one",
                journal_plan_sha256=plan["plan_sha256"],
                journal_state="cancelled", owner_authorized=True)
            # Cleanup preflight can inspect damaged staging, but cannot delete.
            self.assertEqual(result["state"], "eligible_snapshot", result)
            self.assertEqual(result["staging_state"], "damaged")
            self.assertFalse(result["cleanup_allowed"])
            self.assertFalse(result["deletion_performed"])
            self.assertTrue((operation / "blob-000000").exists())

    def test_missing_file_without_durable_record_is_blocked(self):
        progress = {"state": "recorded_snapshot",
                    "removed_files": [], "unresolved_files": []}
        result = inspect_windows_cleanup_recovery(
            EXPECTED, ["blob-000001", "manifest.json"], progress)
        self.assertEqual(result["reason"], "missing_files_without_cleanup_evidence")
        self.assertFalse(result["cleanup_allowed"])

    def test_recorded_removal_is_read_only(self):
        progress = {"state": "recorded_snapshot",
                    "removed_files": ["blob-000000"], "unresolved_files": []}
        result = inspect_windows_cleanup_recovery(
            EXPECTED, ["blob-000001", "manifest.json"], progress)
        self.assertEqual(result["state"], "consistent_snapshot")
        self.assertFalse(result["auto_retry_allowed"])

    def test_uncertain_intent_cannot_be_replayed(self):
        with sqlite3.connect(":memory:") as db:
            ensure_cleanup_progress_schema(db)
            begin_cleanup_file(db, "op.one", DIGEST, "blob-000000")
            db.commit()
            progress = inspect_cleanup_progress(db, "op.one", DIGEST)
            result = inspect_windows_cleanup_recovery(
                EXPECTED, ["blob-000001", "manifest.json"], progress)
            self.assertEqual(result["reason"], "unresolved_cleanup_intent")
            self.assertFalse(result["auto_retry_allowed"])

    def test_recorded_removed_but_still_present_is_blocked(self):
        progress = {"state": "recorded_snapshot",
                    "removed_files": ["blob-000000"], "unresolved_files": []}
        result = inspect_windows_cleanup_recovery(EXPECTED, EXPECTED, progress)
        self.assertEqual(result["reason"], "recorded_removed_file_still_present")


if __name__ == "__main__":
    unittest.main()
