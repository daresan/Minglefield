"""Read-only staging recovery inspection tests."""
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
from game_integration_install_recovery import inspect_staged_installation


class InstallationRecoveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve(strict=True)
        self.repo = self.base / "repo"
        self.root = self.base / "staging"
        self.repo.mkdir()
        self.root.mkdir()
        self.payload = {"assets/a.bin": b"first", "scripts/b.bin": b"second"}
        self.entries = [
            {"path": path, "size": len(data),
             "sha256": hashlib.sha256(data).hexdigest()}
            for path, data in self.payload.items()
        ]
        self.operation = self.root / "op1"

    def inspect(self, entries=None):
        return inspect_staged_installation(
            self.root, "op1", self.entries if entries is None else entries)

    def stage(self):
        return stage_installation_bytes(
            self.root, "op1", self.repo, self.entries, self.payload.__getitem__)

    def test_absent_is_not_complete(self):
        self.assertEqual(self.inspect()["state"], "absent")
        self.assertFalse(self.operation.exists())

    def test_complete_snapshot_is_not_installation_authorization(self):
        self.assertEqual(self.stage()["state"], "staged")
        before = sorted(p.name for p in self.operation.iterdir())
        result = self.inspect()
        self.assertEqual(result["state"], "complete_snapshot")
        self.assertFalse(result["installation_allowed"])
        self.assertFalse(result["mutation_performed"])
        self.assertEqual(before, sorted(p.name for p in self.operation.iterdir()))
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_interrupted_without_manifest_is_incomplete(self):
        self.assertEqual(self.stage()["state"], "staged")
        (self.operation / "manifest.json").unlink()
        self.assertEqual(self.inspect()["state"], "incomplete")

    def test_missing_blob_is_incomplete(self):
        self.assertEqual(self.stage()["state"], "staged")
        (self.operation / "blob-000000").unlink()
        self.assertEqual(self.inspect()["reason"], "missing_blob")

    def test_corrupted_blob_is_damaged(self):
        self.assertEqual(self.stage()["state"], "staged")
        (self.operation / "blob-000000").write_bytes(b"tampered")
        self.assertEqual(self.inspect()["reason"], "blob_mismatch")

    def test_tampered_manifest_is_damaged(self):
        self.assertEqual(self.stage()["state"], "staged")
        path = self.operation / "manifest.json"
        manifest = json.loads(path.read_text("utf-8"))
        manifest["plan_sha256"] = "0" * 64
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(self.inspect()["reason"], "manifest_mismatch")

    def test_unexpected_entry_is_damaged_and_preserved(self):
        self.assertEqual(self.stage()["state"], "staged")
        unexpected = self.operation / "unknown"
        unexpected.write_bytes(b"keep")
        self.assertEqual(self.inspect()["reason"], "unexpected_staging_entry")
        self.assertEqual(unexpected.read_bytes(), b"keep")

    def test_independent_plan_mismatch_is_damaged(self):
        self.assertEqual(self.stage()["state"], "staged")
        changed = [dict(entry) for entry in self.entries]
        changed[0]["sha256"] = "0" * 64
        self.assertEqual(self.inspect(changed)["reason"], "manifest_mismatch")

    def test_invalid_operation_id_is_blocked(self):
        result = inspect_staged_installation(self.root, "../outside", self.entries)
        self.assertEqual(result["state"], "blocked")

    @unittest.skipUnless(os.name == "nt", "Windows junction-specific test")
    def test_junction_operation_is_blocked(self):
        outside = self.base / "outside"
        outside.mkdir()
        command = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(self.operation), str(outside)],
            capture_output=True)
        if command.returncode:
            self.skipTest("junction creation unavailable")
        self.assertEqual(self.inspect()["reason"], "unsafe_operation_path")
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
