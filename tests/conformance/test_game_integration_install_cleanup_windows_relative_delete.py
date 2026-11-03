"""Disposable-only Windows relative handle disposition tests."""
import os
import subprocess
import threading
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
    def test_hardlinked_file_and_external_alias_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blob"
            alias = Path(tmp) / "alias"
            path.write_bytes(b"shared")
            expected = self.identities(tmp, path)
            os.link(path, alias)
            result = delete_relative_test_file(tmp, "blob", **expected)
            self.assertEqual(result["reason"], "unsafe_staging_hardlink", result)
            self.assertEqual(path.read_bytes(), b"shared")
            self.assertEqual(alias.read_bytes(), b"shared")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_junction_parent_cannot_delete_external_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "external"
            external.mkdir()
            blob = external / "blob"
            blob.write_bytes(b"foreign")
            junction = root / "junction"
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(external)],
                capture_output=True)
            self.assertEqual(created.returncode, 0,
                             created.stderr.decode(errors="replace"))
            expected = self.identities(external, blob)
            result = delete_relative_test_file(junction, "blob", **expected)
            self.assertEqual(result["reason"], "unsafe_parent_path", result)
            self.assertEqual(blob.read_bytes(), b"foreign")

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_reparse_child_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            (target / "keep").write_bytes(b"foreign")
            junction = root / "child"
            created = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
                capture_output=True)
            self.assertEqual(created.returncode, 0,
                             created.stderr.decode(errors="replace"))
            parent = inspect_windows_directory_handle(root)
            self.assertEqual(parent["state"], "inspected", parent)
            result = delete_relative_test_file(
                root, "child",
                expected_parent_volume_serial=parent["volume_serial"],
                expected_parent_file_index=parent["file_index"],
                expected_file_volume_serial=0, expected_file_index=0)
            self.assertIn(result["reason"],
                          ("native_relative_open_failed", "windows_reparse_point"),
                          result)
            self.assertEqual((target / "keep").read_bytes(), b"foreign")
            self.assertTrue(junction.exists())

    @unittest.skipUnless(os.name == "nt", "Windows-only")
    def test_concurrent_parent_replacement_preserves_foreign_sentinel(self):
        """Adversarial rename attempts; no guarantee the scheduler hits every window."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operation = root / "operation"
            operation.mkdir()
            original = operation / "blob"
            original.write_bytes(b"original")
            expected = self.identities(operation, original)
            foreign = root / "foreign"
            foreign.mkdir()
            sentinel = foreign / "blob"
            sentinel.write_bytes(b"foreign-sentinel")
            displaced = root / "displaced"
            start = threading.Event()
            stop = threading.Event()
            errors = []

            def adversary():
                start.wait(5)
                while not stop.is_set():
                    try:
                        if operation.exists() and not displaced.exists():
                            operation.rename(displaced)
                            foreign.rename(operation)
                        if operation.exists() and not foreign.exists():
                            operation.rename(foreign)
                        if displaced.exists() and not operation.exists():
                            displaced.rename(operation)
                    except OSError:
                        # Open handles can prevent a rename on some Windows builds.
                        continue
                    except Exception as exc:
                        errors.append(exc)
                        return

            worker = threading.Thread(target=adversary, daemon=True)
            worker.start()
            start.set()
            try:
                result = delete_relative_test_file(operation, "blob", **expected)
            finally:
                stop.set()
                worker.join(timeout=5)
            self.assertFalse(worker.is_alive(), "adversary did not terminate")
            self.assertFalse(errors, errors)
            # The foreign file may be under either name after the last swap.
            surviving = [p for p in (root / "foreign" / "blob",
                                     root / "operation" / "blob",
                                     root / "displaced" / "blob")
                         if p.exists() and p.read_bytes() == b"foreign-sentinel"]
            self.assertTrue(surviving, result)
            self.assertIn(result["state"], ("blocked", "removed"))
            self.assertFalse(result["cleanup_allowed"])

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
