"""Offline deterministic tests of pinned managed-Alpha runtime archive handling."""
import io
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from build_managed_alpha_runtime import (
    BUNDLES, RUNTIME_REQUIREMENTS, PINNED_APPLICATION_WHEELS,
    _safe_relative, current_variant, managed_file_inventory,
    verify_managed_file_inventory, MANAGED_FILES_NAME,
    extract_sqlcipher_wheel, extract_standalone, verify_pinned_file,
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

    def test_external_alpha_runtime_versions_are_exactly_pinned(self):
        self.assertEqual(len(RUNTIME_REQUIREMENTS), 7)
        self.assertEqual(
            {name for name, _ in RUNTIME_REQUIREMENTS},
            {"attrs", "jsonschema", "jsonschema_specifications",
             "packaging", "referencing", "rpds_py", "typing_extensions"})
        for name, version in RUNTIME_REQUIREMENTS:
            self.assertTrue(name.replace("_", "").isalnum())
            self.assertTrue(version)
            self.assertNotIn(">", version)
            self.assertNotIn("<", version)
            self.assertNotIn("*", version)

    def test_every_supported_platform_has_exactly_pinned_dependency_hashes(self):
        common = {filename for filename in PINNED_APPLICATION_WHEELS
                  if not filename.startswith("rpds_py-")}
        self.assertEqual(len(common), 6)
        for variant in BUNDLES:
            if variant[0] == "windows":
                rpds_platform = "win_amd64"
            elif variant[0] == "linux":
                rpds_platform = "manylinux_2_17_x86_64"
            else:
                rpds_platform = ("macosx_11_0_arm64" if variant[1] == "aarch64"
                                 else "macosx_10_12_x86_64")
            candidates = [filename for filename in PINNED_APPLICATION_WHEELS
                          if filename.startswith("rpds_py-")
                          and rpds_platform in filename]
            self.assertEqual(len(candidates), 1)
            self.assertEqual(len(common | set(candidates)), len(RUNTIME_REQUIREMENTS))
        self.assertTrue(all(len(digest) == 64 and
                            all(character in "0123456789abcdef" for character in digest)
                            for digest in PINNED_APPLICATION_WHEELS.values()))

    def test_managed_inventory_detects_tampering_and_unexpected_files(self):
        import hashlib
        import json
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "application").mkdir()
            target = root / "application" / "installed.py"
            target.write_bytes(b"print('minglefield')\n")
            listing = managed_file_inventory(root)
            self.assertEqual(len(listing["files"]), 1)
            inventory_file = root / MANAGED_FILES_NAME
            inventory_file.write_text(
                json.dumps(listing, sort_keys=True), encoding="utf-8")
            digest = hashlib.sha256(inventory_file.read_bytes()).hexdigest()
            self.assertEqual(verify_managed_file_inventory(root, digest), 1)
            target.write_bytes(b"print('modified')\n")
            with self.assertRaisesRegex(ValueError, "content changed"):
                verify_managed_file_inventory(root, digest)
            target.write_bytes(b"print('minglefield')\n")
            (root / "application" / "unlisted.py").write_bytes(b"evil")
            with self.assertRaisesRegex(ValueError, "content changed"):
                verify_managed_file_inventory(root, digest)

    def test_inventory_rejects_symlink_leaving_source_tree(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            inside = root / "payload"
            inside.mkdir()
            (root / "private.txt").write_bytes(b"must not be packaged")
            try:
                (inside / "escape").symlink_to(root / "private.txt")
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaisesRegex(ValueError, "symlink escapes"):
                managed_file_inventory(inside)

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
