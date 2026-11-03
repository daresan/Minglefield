"""POSIX isolated staging cleanup primitive; not wired into runtime/HTTP."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_posix import cleanup_staged_operation_posix
from game_integration_install_executor import stage_installation_bytes
from game_integration_install_staging import validate_staging_manifest


@unittest.skipIf(os.name == "nt", "Native Windows handle backend not implemented")
class PosixCleanupTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve(strict=True)
        self.repo = self.base / "repo"
        self.root = self.base / "staging"
        self.repo.mkdir()
        self.root.mkdir()
        self.payload = b"isolated staging payload"
        self.entries = [{"path": "asset.bin", "size": len(self.payload),
                         "sha256": hashlib.sha256(self.payload).hexdigest()}]
        self.digest = validate_staging_manifest(self.entries)["plan_sha256"]

    def stage(self):
        result = stage_installation_bytes(
            self.root, "op1", self.repo, self.entries, lambda _: self.payload)
        self.assertEqual(result["state"], "staged")

    def cleanup(self, **overrides):
        args = dict(journal_operation_id="op1", journal_plan_sha256=self.digest,
                    journal_state="cancelled", owner_authorized=True)
        args.update(overrides)
        return cleanup_staged_operation_posix(self.root, "op1", self.entries, **args)

    def test_terminal_cancelled_removes_only_staging(self):
        self.stage()
        result = self.cleanup()
        self.assertEqual(result["state"], "removed")
        self.assertTrue(result["deletion_performed"])
        self.assertFalse((self.root / "op1").exists())
        self.assertTrue(self.repo.is_dir())

    def test_shared_writable_root_is_rejected(self):
        self.stage()
        original = self.root.stat().st_mode & 0o777
        try:
            self.root.chmod(0o777)
            result = self.cleanup()
            self.assertEqual(result["reason"], "insecure_staging_root_permissions")
            self.assertFalse(result["deletion_performed"])
            self.assertTrue((self.root / "op1" / "manifest.json").exists())
        finally:
            self.root.chmod(original)

    def test_shared_writable_operation_is_rejected(self):
        self.stage()
        operation = self.root / "op1"
        original = operation.stat().st_mode & 0o777
        try:
            operation.chmod(0o777)
            result = self.cleanup()
            self.assertEqual(result["reason"], "insecure_operation_permissions")
            self.assertFalse(result["deletion_performed"])
            self.assertTrue((operation / "manifest.json").exists())
        finally:
            operation.chmod(original)

    def test_prepared_journal_does_not_delete(self):
        self.stage()
        result = self.cleanup(journal_state="prepared")
        self.assertEqual(result["state"], "blocked")
        self.assertTrue((self.root / "op1" / "manifest.json").exists())

    def test_wrong_digest_does_not_delete(self):
        self.stage()
        result = self.cleanup(journal_plan_sha256="0" * 64)
        self.assertEqual(result["state"], "blocked")
        self.assertTrue((self.root / "op1").exists())

    def test_unknown_file_does_not_delete(self):
        self.stage()
        (self.root / "op1" / "unexpected").write_bytes(b"keep")
        result = self.cleanup()
        self.assertEqual(result["state"], "blocked")
        self.assertTrue((self.root / "op1" / "unexpected").exists())

    def test_symlink_operation_does_not_delete_target(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "keep").write_bytes(b"keep")
        (self.root / "op1").symlink_to(outside, target_is_directory=True)
        result = self.cleanup()
        self.assertEqual(result["state"], "blocked")
        self.assertEqual((outside / "keep").read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
