"""Windows native relative-open probe tests; no cleanup or mutation."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_windows_relative import inspect_windows_relative_child


class WindowsRelativeChildTests(unittest.TestCase):
    def test_non_windows_fails_closed(self):
        if os.name == "nt":
            self.skipTest("Windows platform")
        self.assertEqual(inspect_windows_relative_child(".", "blob")["reason"],
                         "windows_only")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_relative_regular_file_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob"
            path.write_bytes(b"keep")
            result = inspect_windows_relative_child(tmp, "blob")
            self.assertEqual(result["state"], "inspected", result)
            self.assertFalse(result["cleanup_allowed"])
            self.assertFalse(result["deletion_performed"])
            self.assertEqual(path.read_bytes(), b"keep")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_child_traversal_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("../blob", "..", "a\\b", "C:blob", "blob."):
                self.assertEqual(inspect_windows_relative_child(tmp, name)["reason"],
                                 "invalid_child_name")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_hardlink_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob"
            path.write_bytes(b"keep")
            os.link(path, Path(tmp) / "alias")
            result = inspect_windows_relative_child(tmp, "blob")
            self.assertEqual(result["reason"], "unsafe_staging_hardlink", result)
            self.assertEqual(path.read_bytes(), b"keep")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_directory_child_is_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "child"
            path.mkdir()
            result = inspect_windows_relative_child(tmp, "child")
            self.assertIn(result["reason"],
                          ("not_regular_file", "native_relative_open_failed"), result)
            self.assertTrue(path.is_dir())
