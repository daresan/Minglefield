"""Offline tests for the Finder .app envelope around an unchanged managed Alpha."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest

from build_managed_alpha_runtime import managed_file_inventory
from package_macos_alpha_app import package_macos_app, verify_native_macos_source


def create_fixture(root):
    source = root / "managed-alpha"
    source.mkdir()
    executable = source / "Minglefield"
    executable.write_bytes(b"#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    worker = source / "application/server/installed_alpha_launch.py"
    worker.parent.mkdir(parents=True)
    worker.write_text("# Bundled Alpha entrypoint\n", encoding="utf-8")
    inventory = source / "managed-file-inventory.json"
    inventory.write_text(
        json.dumps(managed_file_inventory(source), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(inventory.read_bytes()).hexdigest()
    manifest = {
        "schemaVersion": 1,
        "platform": "darwin-aarch64",
        "nativeApplicationIncluded": True,
        "nativeApplicationExecutable": "Minglefield",
        "applicationEntrypoint": "application/server/installed_alpha_launch.py",
        "managedFileInventorySha256": digest,
    }
    (source / "runtime-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return source, digest


@unittest.skipIf(os.name == "nt", "macOS executable mode requires POSIX filesystem")
class MacOSBundleTests(unittest.TestCase):
    def test_builds_native_bundle_with_unchanged_managed_inventory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, digest = create_fixture(root)
            target = root / "Minglefield.app"
            result = package_macos_app(source, target)
            self.assertEqual(result["status"], "native_macos_app_bundle_created")
            self.assertEqual(result["managedFileInventorySha256"], digest)
            self.assertFalse(result["codeSigningVerified"])
            self.assertFalse(result["finderUserAcceptanceVerified"])
            with (target / "Contents/Info.plist").open("rb") as handle:
                info = plistlib.load(handle)
            self.assertEqual(info["CFBundleExecutable"], "Minglefield")
            self.assertEqual(info["CFBundlePackageType"], "APPL")
            bundled = target / "Contents/MacOS"
            self.assertTrue((bundled / "Minglefield").stat().st_mode & 0o111)
            self.assertEqual(
                (bundled / "managed-file-inventory.json").read_bytes(),
                (source / "managed-file-inventory.json").read_bytes(),
            )
            self.assertEqual(
                (bundled / "runtime-manifest.json").read_bytes(),
                (source / "runtime-manifest.json").read_bytes(),
            )
            self.assertRaises(ValueError, package_macos_app, source, target)
            (bundled / "application/server/installed_alpha_launch.py").write_text(
                "# TAMPERED\n", encoding="utf-8"
            )
            self.assertRaises(
                ValueError,
                verify_native_macos_source,
                bundled,
            )

    def test_rejects_non_macos_and_existing_destination_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, _ = create_fixture(root)
            manifest = source / "runtime-manifest.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["platform"] = "windows-amd64"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            target = root / "Minglefield.app"
            with self.assertRaises(ValueError):
                package_macos_app(source, target)
            self.assertFalse(target.exists())
            data["platform"] = "darwin-aarch64"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            target.mkdir()
            sentinel = target / "EXISTING-OWNER-FILE"
            sentinel.write_text("must remain\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                package_macos_app(source, target)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "must remain\n")

    def test_rejects_recursive_output_and_leaking_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, _ = create_fixture(root)
            with self.assertRaises(ValueError):
                package_macos_app(source, source / "Minglefield.app")
            if os.name != "nt":
                outside = root / "outside"
                outside.write_text("outside\n", encoding="utf-8")
                (source / "leak").symlink_to(outside)
                with self.assertRaises(ValueError):
                    package_macos_app(source, root / "Minglefield.app")


if __name__ == "__main__":
    unittest.main()
