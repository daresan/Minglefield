"""Disposable-only Windows relative handle disposition tests."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_windows_relative_delete import delete_relative_test_file
from game_integration_install_cleanup_windows import (
    inspect_windows_directory_handle, inspect_windows_staged_file)


class WindowsRelativeDeleteTests(unittest.TestCase):
    def identities(self, parent, child):
        directory = inspect_windows_directory_handle(parent)
        file = inspect_windows_staged_file(child)
        self.assertEqual(directory["state"], "inspected", directory)
        self.assertEqual(file["state"], "inspected", file)
        return dict(expected_parent_volume_serial=directory["volume_serial"],
                    expected_parent_file_index=directory["file_index"],
                    expected_file_volume_serial=file["volume_serial"],
                    expected_file_index=file["file_index"])

    def test_other_platform_fails_closed(self):
        if os.name == "nt":
            self.skipTest("Windows-only")
        self.assertEqual(delete_relative_test_file(".", "blob")["reason"], "windows_only")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_relative_disposition_removes_only_disposable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob"
            other = Path(tmp) / "keep"
            path.write_bytes(b"delete")
            other.write_bytes(b"keep")
            result = delete_relative_test_file(tmp, "blob", **self.identities(tmp, path))
            self.assertEqual(result["state"], "removed", result)
            self.assertFalse(path.exists())
            self.assertEqual(other.read_bytes(), b"keep")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_replaced_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob"
            path.write_bytes(b"original")
            expected = self.identities(tmp, path)
            path.rename(Path(tmp) / "original")
            path.write_bytes(b"replacement")
            result = delete_relative_test_file(tmp, "blob", **expected)
            self.assertEqual(result["reason"], "native_file_identity_mismatch", result)
            self.assertEqual(path.read_bytes(), b"replacement")
            self.assertEqual((Path(tmp) / "original").read_bytes(), b"original")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_replaced_parent_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "operation"
            parent.mkdir()
            path = parent / "blob"
            path.write_bytes(b"original")
            expected = self.identities(parent, path)
            parent.rename(Path(tmp) / "original")
            parent.mkdir()
            (parent / "blob").write_bytes(b"replacement")
            result = delete_relative_test_file(parent, "blob", **expected)
            self.assertEqual(result["reason"], "native_parent_identity_mismatch", result)
            self.assertEqual((parent / "blob").read_bytes(), b"replacement")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_missing_identity_and_traversal_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob"
            path.write_bytes(b"keep")
            self.assertEqual(delete_relative_test_file(tmp, "blob")["reason"],
                             "expected_native_identities_required")
            for name in ("..", "../blob", "a\\b", "blob."):
                self.assertEqual(delete_relative_test_file(tmp, name)["reason"],
                                 "invalid_child_name")
            self.assertEqual(path.read_bytes(), b"keep")
