"""Native Windows cleanup groundwork: handle-based read-only identity."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_windows import (inspect_windows_directory_handle,
                                                      inspect_windows_staging_binding)


class WindowsCleanupHandleTests(unittest.TestCase):
    def test_platform_gate_never_authorizes_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect_windows_directory_handle(tmp)
            self.assertFalse(result["cleanup_allowed"])
            self.assertFalse(result["deletion_performed"])
            if os.name == "nt":
                self.assertEqual(result["state"], "inspected")
                self.assertIsInstance(result["file_index"], int)
            else:
                self.assertEqual(result["reason"], "windows_only")

    def test_staging_binding_platform_gate_and_invalid_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "staging"
            root.mkdir()
            (root / "op1").mkdir()
            result = inspect_windows_staging_binding(root, "op1")
            self.assertFalse(result["cleanup_allowed"])
            self.assertFalse(result["deletion_performed"])
            if os.name == "nt":
                self.assertEqual(result["state"], "inspected")
                for invalid in ("../outside", "..", "C:escape", "op1/child"):
                    self.assertEqual(
                        inspect_windows_staging_binding(root, invalid)["state"],
                        "blocked")
            else:
                self.assertEqual(result["reason"], "windows_only")

    @unittest.skipUnless(os.name == "nt", "Windows native handle test")
    def test_staging_binding_rejects_junction_operation(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "staging"
            target = Path(tmp) / "foreign"
            root.mkdir()
            target.mkdir()
            (target / "keep").write_text("keep")
            junction = root / "op1"
            proc = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
                capture_output=True)
            if proc.returncode:
                self.skipTest("Junction creation unavailable")
            result = inspect_windows_staging_binding(root, "op1")
            self.assertEqual(result["reason"], "windows_reparse_point")
            self.assertEqual((target / "keep").read_text(), "keep")

    @unittest.skipUnless(os.name == "nt", "Windows native handle test")
    def test_native_handles_block_concurrent_operation_rename(self):
        from game_integration_install_cleanup_windows import (
            inspect_windows_directory_handle as original_inspect)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "staging"
            operation = root / "op1"
            root.mkdir()
            operation.mkdir()
            attempted = []

            def attempt_rename(path):
                if Path(path) == operation and not attempted:
                    try:
                        operation.rename(root / "moved")
                        attempted.append("unexpected_success")
                    except OSError:
                        attempted.append("blocked")
                return original_inspect(path)

            with patch("game_integration_install_cleanup_windows.inspect_windows_directory_handle",
                       side_effect=attempt_rename):
                result = inspect_windows_staging_binding(root, "op1")
            self.assertEqual(attempted, ["blocked"])
            self.assertEqual(result["state"], "inspected")
            self.assertTrue(operation.is_dir())
            self.assertFalse(result["deletion_performed"])

    @unittest.skipUnless(os.name == "nt", "Windows native handle test")
    def test_changed_native_binding_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "staging"
            root.mkdir()
            (root / "op1").mkdir()
            with patch("game_integration_install_cleanup_windows.inspect_windows_directory_handle",
                       return_value={"state": "inspected",
                                     "volume_serial": 0, "file_index": -1}):
                result = inspect_windows_staging_binding(root, "op1")
            self.assertEqual(result["reason"], "windows_staging_binding_changed")
            self.assertFalse(result["deletion_performed"])

    @unittest.skipUnless(os.name == "nt", "Windows native handle test")
    def test_file_is_not_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "ordinary.txt"
            file.write_text("keep")
            result = inspect_windows_directory_handle(file)
            self.assertEqual(result["state"], "blocked")
            self.assertEqual(result["reason"], "not_directory")
            self.assertEqual(file.read_text(), "keep")

    @unittest.skipUnless(os.name == "nt", "Windows native handle test")
    def test_junction_is_rejected_without_following(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            junction = root / "junction"
            target.mkdir()
            (target / "keep").write_bytes(b"keep")
            proc = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
                capture_output=True)
            if proc.returncode:
                self.skipTest("Junction creation unavailable")
            result = inspect_windows_directory_handle(junction)
            self.assertEqual(result["reason"], "windows_reparse_point")
            self.assertEqual((target / "keep").read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
