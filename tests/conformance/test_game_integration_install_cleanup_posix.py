"""POSIX isolated staging cleanup primitive; not wired into runtime/HTTP."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_posix import cleanup_staged_operation_posix
from game_integration_install_cleanup_backend import inspect_cleanup_backend_capabilities
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

    def test_operation_replaced_during_unlink_does_not_delete_replacement(self):
        capability = inspect_cleanup_backend_capabilities()
        if capability["state"] != "candidate":
            self.skipTest("POSIX handle-relative cleanup unavailable: " + capability["reason"])
        self.stage()
        original_unlink = os.unlink
        operation = self.root / "op1"
        displaced = self.root / "displaced"
        replacement = self.base / "replacement"
        replacement.mkdir()
        (replacement / "keep.txt").write_bytes(b"foreign")
        switched = False

        def swap_then_unlink(path, *args, **kwargs):
            nonlocal switched
            if not switched and kwargs.get("dir_fd") is not None:
                switched = True
                operation.rename(displaced)
                replacement.rename(operation)
            return original_unlink(path, *args, **kwargs)

        with patch("game_integration_install_cleanup_posix.os.unlink",
                   side_effect=swap_then_unlink):
            result = self.cleanup()
        self.assertTrue(switched, result)
        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["reason"], "operation_identity_changed")
        self.assertEqual((operation / "keep.txt").read_bytes(), b"foreign")
        self.assertTrue(operation.is_dir())

    def test_operation_symlink_swap_before_open_is_blocked(self):
        capability = inspect_cleanup_backend_capabilities()
        if capability["state"] != "candidate":
            self.skipTest("POSIX handle-relative cleanup unavailable: " + capability["reason"])
        self.stage()
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_bytes(b"foreign")
        operation = self.root / "op1"
        original_open = os.open
        swapped = False

        def swap_before_open(path, *args, **kwargs):
            nonlocal swapped
            if path == "op1" and kwargs.get("dir_fd") is not None and not swapped:
                swapped = True
                operation.rename(self.root / "displaced")
                operation.symlink_to(outside, target_is_directory=True)
            return original_open(path, *args, **kwargs)

        with patch("game_integration_install_cleanup_posix.os.open",
                   side_effect=swap_before_open):
            result = self.cleanup()
        self.assertTrue(swapped, result)
        self.assertEqual(result["state"], "blocked")
        self.assertEqual((outside / "keep.txt").read_bytes(), b"foreign")

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
