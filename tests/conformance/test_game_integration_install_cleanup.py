"""Journal-bound cleanup preflight must never delete staged data."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_executor import stage_installation_bytes
from game_integration_install_cleanup import inspect_staging_cleanup
from game_integration_install_staging import validate_staging_manifest


class CleanupPreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.repo = self.base / "repo"
        self.root = self.base / "staging"
        self.repo.mkdir()
        self.root.mkdir()
        self.data = b"safe payload"
        self.entries = [{"path": "assets/data.bin", "size": len(self.data),
                         "sha256": hashlib.sha256(self.data).hexdigest()}]
        self.digest = validate_staging_manifest(self.entries)["plan_sha256"]
        self.operation = self.root / "op1"

    def stage(self):
        self.assertEqual(stage_installation_bytes(
            self.root, "op1", self.repo, self.entries,
            lambda _: self.data)["state"], "staged")

    def inspect(self, **overrides):
        args = {"journal_operation_id": "op1", "journal_plan_sha256": self.digest,
                "journal_state": "cancelled", "owner_authorized": True}
        args.update(overrides)
        return inspect_staging_cleanup(self.root, "op1", self.entries, **args)

    def test_complete_snapshot_is_not_deletion(self):
        self.stage()
        result = self.inspect()
        self.assertEqual(result["state"], "eligible_snapshot")
        self.assertEqual(result["staging_state"], "complete_snapshot")
        self.assertFalse(result["cleanup_allowed"])
        self.assertFalse(result["deletion_performed"])
        self.assertTrue((self.operation / "blob-000000").exists())

    def test_interrupted_operation_is_eligible_but_preserved(self):
        self.stage()
        (self.operation / "manifest.json").unlink()
        result = self.inspect()
        self.assertEqual(result["state"], "eligible_snapshot")
        self.assertEqual(result["staging_state"], "incomplete")
        self.assertTrue((self.operation / "blob-000000").exists())

    def test_corrupt_payload_is_eligible_but_preserved(self):
        self.stage()
        (self.operation / "blob-000000").write_bytes(b"corrupt")
        result = self.inspect()
        self.assertEqual(result["staging_state"], "damaged")
        self.assertTrue((self.operation / "blob-000000").exists())

    def test_owner_is_required(self):
        self.stage()
        self.assertEqual(self.inspect(owner_authorized=False)["reason"],
                         "owner_authorization_required")

    def test_journal_binding_and_terminal_state_required(self):
        self.stage()
        for overrides in ({"journal_operation_id": "other"},
                          {"journal_plan_sha256": "0" * 64},
                          {"journal_state": "applying"},
                          {"journal_state": "prepared"},
                          {"journal_state": "committed"}):
            with self.subTest(overrides=overrides):
                self.assertEqual(self.inspect(**overrides)["reason"],
                                 "journal_cleanup_not_authorized")

    def test_unknown_files_block_cleanup_preflight(self):
        self.stage()
        extra = self.operation / "foreign.txt"
        extra.write_bytes(b"preserve")
        self.assertEqual(self.inspect()["reason"],
                         "unexpected_or_unsafe_staging_entry")
        self.assertEqual(extra.read_bytes(), b"preserve")

    def test_absent_operation_is_not_created(self):
        self.assertEqual(self.inspect()["state"], "absent")
        self.assertFalse(self.operation.exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction-specific test")
    def test_junction_operation_is_blocked(self):
        outside = self.base / "outside"
        outside.mkdir()
        command = subprocess.run(["cmd", "/c", "mklink", "/J",
                                  str(self.operation), str(outside)],
                                 capture_output=True)
        if command.returncode:
            self.skipTest("junction creation unavailable")
        self.assertEqual(self.inspect()["reason"], "unsafe_operation_path")
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
