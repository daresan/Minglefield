"""Isolated native Windows file disposition tests; never use production paths."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_windows_native import delete_isolated_regular_file_by_handle


class WindowsNativeDispositionTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_disposable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "disposable"
            path.write_bytes(b"payload")
            result = delete_isolated_regular_file_by_handle(path)
            self.assertEqual(result["state"], "removed", result)
            self.assertFalse(path.exists())
            self.assertFalse(result["cleanup_allowed"])

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_hardlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file"
            other = Path(tmp) / "link"
            path.write_bytes(b"payload")
            os.link(path, other)
            result = delete_isolated_regular_file_by_handle(path)
            self.assertEqual(result["reason"], "unsafe_staging_hardlink")
            self.assertTrue(path.exists())
            self.assertEqual(other.read_bytes(), b"payload")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "directory"
            path.mkdir()
            result = delete_isolated_regular_file_by_handle(path)
            self.assertEqual(result["state"], "blocked")
            self.assertTrue(path.exists())

    def test_other_platform_fails_closed(self):
        if os.name == "nt":
            self.skipTest("Native platform")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keep"
            path.write_bytes(b"keep")
            self.assertEqual(delete_isolated_regular_file_by_handle(path)["reason"], "windows_only")
            self.assertTrue(path.exists())
