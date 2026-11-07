"""Offline deterministic tests of pinned managed-Alpha runtime archive handling."""
import io
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from build_managed_alpha_runtime import (
    BUNDLES, _safe_relative, current_variant, extract_sqlcipher_wheel,
    extract_standalone, verify_pinned_file,
)


class ManagedAlphaRuntimeBuildTests(unittest.TestCase):
    def test_supported_matrix_has_distinct_pinned_hashes_and_wheels(self):
        self.assertIn(current_variant(), BUNDLES)
        self.assertEqual(len(BUNDLES), 4)
        for variant, (triple, archive_sha, wheel, wheel_sha) in BUNDLES.items():
            self.assertIn("-cp311-cp311-", wheel)
            self.assertTrue(triple)
            self.assertEqual(len(archive_sha), 64)
            self.assertEqual(len(wheel_sha), 64)
            self.assertNotEqual(archive_sha, wheel_sha)

    def test_checksum_fails_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "archive"
            path.write_bytes(b"tampered-runtime")
            with self.assertRaises(ValueError):
                verify_pinned_file(path, "0" * 64)

    def test_reject_tar_traversal_before_any_extraction(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            tar_path = root / "bad.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                data = b"escape"
                info = tarfile.TarInfo("python/../../outside.txt")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            with self.assertRaises(ValueError):
                extract_standalone(tar_path, root / "runtime")
            self.assertFalse((root / "outside.txt").exists())

    def test_wheel_rejects_escape_but_accepts_normal_pure_module(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad.whl"
            with ZipFile(bad, "w") as z:
                z.writestr("../escape.py", b"evil")
            with self.assertRaises(ValueError):
                extract_sqlcipher_wheel(bad, root / "site")
            self.assertFalse((root / "escape.py").exists())
            good = root / "ok.whl"
            with ZipFile(good, "w") as z:
                z.writestr("sqlcipher3/__init__.py", b"# binary fixture")
            extract_sqlcipher_wheel(good, root / "good-site")
            self.assertEqual((root / "good-site/sqlcipher3/__init__.py").read_bytes(),
                             b"# binary fixture")


if __name__ == "__main__":
    unittest.main()
