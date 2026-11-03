"""Native Windows cleanup groundwork: handle-based read-only identity."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_windows import inspect_windows_directory_handle


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
