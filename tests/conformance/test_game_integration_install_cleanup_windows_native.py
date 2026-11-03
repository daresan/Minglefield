"""Isolated native Windows file disposition tests; never use production paths."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_windows_native import delete_isolated_regular_file_by_handle
from game_integration_install_cleanup_windows import (inspect_windows_staged_file,
                                                      inspect_windows_directory_handle)


class WindowsNativeDispositionTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_disposable_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "disposable"
            path.write_bytes(b"payload")
            identity = inspect_windows_staged_file(path)
            self.assertEqual(identity["state"], "inspected")
            parent = inspect_windows_directory_handle(tmp)
            self.assertEqual(parent["state"], "inspected")
            result = delete_isolated_regular_file_by_handle(
                path, expected_volume_serial=identity["volume_serial"],
                expected_file_index=identity["file_index"],
                expected_parent_volume_serial=parent["volume_serial"],
                expected_parent_file_index=parent["file_index"])
            self.assertEqual(result["state"], "removed", result)
            self.assertFalse(path.exists())
            self.assertFalse(result["cleanup_allowed"])

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_replaced_file_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "disposable"
            displaced = Path(tmp) / "displaced"
            path.write_bytes(b"original")
            identity = inspect_windows_staged_file(path)
            self.assertEqual(identity["state"], "inspected")
            parent = inspect_windows_directory_handle(tmp)
            self.assertEqual(parent["state"], "inspected")
            path.rename(displaced)
            path.write_bytes(b"replacement")
            result = delete_isolated_regular_file_by_handle(
                path, expected_volume_serial=identity["volume_serial"],
                expected_file_index=identity["file_index"],
                expected_parent_volume_serial=parent["volume_serial"],
                expected_parent_file_index=parent["file_index"])
            self.assertEqual(result["reason"], "native_file_identity_mismatch")
            self.assertEqual(path.read_bytes(), b"replacement")
            self.assertEqual(displaced.read_bytes(), b"original")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_replaced_parent_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent_path = Path(tmp) / "operation"
            parent_path.mkdir()
            path = parent_path / "blob"
            path.write_bytes(b"original")
            file_identity = inspect_windows_staged_file(path)
            parent_identity = inspect_windows_directory_handle(parent_path)
            moved = Path(tmp) / "moved"
            parent_path.rename(moved)
            parent_path.mkdir()
            replacement = parent_path / "blob"
            replacement.write_bytes(b"foreign")
            result = delete_isolated_regular_file_by_handle(
                replacement,
                expected_volume_serial=file_identity["volume_serial"],
                expected_file_index=file_identity["file_index"],
                expected_parent_volume_serial=parent_identity["volume_serial"],
                expected_parent_file_index=parent_identity["file_index"])
            self.assertEqual(result["reason"], "native_parent_identity_mismatch")
            self.assertEqual(replacement.read_bytes(), b"foreign")
            self.assertEqual((moved / "blob").read_bytes(), b"original")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_missing_parent_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob"
            path.write_bytes(b"keep")
            file_identity = inspect_windows_staged_file(path)
            result = delete_isolated_regular_file_by_handle(
                path, expected_volume_serial=file_identity["volume_serial"],
                expected_file_index=file_identity["file_index"])
            self.assertEqual(result["reason"], "expected_parent_identity_required")
            self.assertEqual(path.read_bytes(), b"keep")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_missing_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "disposable"
            path.write_bytes(b"keep")
            result = delete_isolated_regular_file_by_handle(path)
            self.assertEqual(result["reason"], "expected_file_identity_required")
            self.assertEqual(path.read_bytes(), b"keep")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_hardlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file"
            other = Path(tmp) / "link"
            path.write_bytes(b"payload")
            os.link(path, other)
            parent = inspect_windows_directory_handle(tmp)
            self.assertEqual(parent["state"], "inspected")
            result = delete_isolated_regular_file_by_handle(
                path, expected_volume_serial=0, expected_file_index=0,
                expected_parent_volume_serial=parent["volume_serial"],
                expected_parent_file_index=parent["file_index"])
            self.assertEqual(result["reason"], "unsafe_staging_hardlink")
            self.assertTrue(path.exists())
            self.assertEqual(other.read_bytes(), b"payload")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "directory"
            path.mkdir()
            result = delete_isolated_regular_file_by_handle(
                path, expected_volume_serial=0, expected_file_index=0)
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
