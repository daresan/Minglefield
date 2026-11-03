"""Conformance tests for the *platform* release manifest, not game installers."""
import copy
import json
import unittest

from server.platform_release_manifest import ManifestError, load_manifest, validate_manifest


def valid_manifest():
    h = "a" * 64
    return {
        "format_version": 1,
        "product_id": "org.minglefield.app",
        "release": {"version": "0.1.0-alpha.1", "channel": "alpha"},
        "target": {"os": "windows", "arch": "x86_64"},
        "payload": {"entrypoint": "Minglefield.exe", "files_manifest": "payload-files.sha256",
                    "files_manifest_sha256": h},
        "runtime": {"kind": "bundled-python", "python_version": "3.11.9",
                    "lockfile": "runtime-lock.json", "lockfile_sha256": h},
        "data": {"schema_version": "alpha1", "minimum_compatible_schema": "alpha1",
                 "migration_manifest": None},
        "legal": {"license_manifest": "licenses.json", "license_manifest_sha256": h},
        "provenance": {"source_revision": "b" * 40, "build_id": "ci-1",
                       "signature": "unverified-placeholder"},
    }


class PlatformManifestTests(unittest.TestCase):
    def test_valid_alpha(self):
        doc = valid_manifest()
        self.assertEqual(validate_manifest(doc, expected_os="windows", expected_arch="x86_64"), doc)
        self.assertEqual(load_manifest(json.dumps(doc).encode()), doc)

    def test_missing_hash_rejected(self):
        doc = valid_manifest()
        del doc["payload"]["files_manifest_sha256"]
        with self.assertRaises(ManifestError):
            validate_manifest(doc)

    def test_bad_hash_rejected(self):
        doc = valid_manifest()
        doc["runtime"]["lockfile_sha256"] = "A" * 64
        with self.assertRaises(ManifestError):
            validate_manifest(doc)

    def test_unsafe_paths_rejected(self):
        for name in ("../Minglefield.exe", "/tmp/app", "a/../b", "C:/Windows/a",
                     "a\\b", "a//b", "./a", "a/"):
            with self.subTest(name=name):
                doc = valid_manifest()
                doc["payload"]["entrypoint"] = name
                with self.assertRaises(ManifestError):
                    validate_manifest(doc)

    def test_wrong_target_rejected(self):
        with self.assertRaises(ManifestError):
            validate_manifest(valid_manifest(), expected_os="linux")
        with self.assertRaises(ManifestError):
            validate_manifest(valid_manifest(), expected_arch="arm64")

    def test_wrong_product_rejected(self):
        doc = valid_manifest()
        doc["product_id"] = "org.other.app"
        with self.assertRaises(ManifestError):
            validate_manifest(doc)

    def test_unknown_fields_rejected(self):
        doc = valid_manifest()
        doc["installer_command"] = "do-something"
        with self.assertRaises(ManifestError):
            validate_manifest(doc)

    def test_unsupported_format_rejected(self):
        doc = valid_manifest()
        doc["format_version"] = 2
        with self.assertRaises(ManifestError):
            validate_manifest(doc)

    def test_invalid_json_rejected(self):
        with self.assertRaises(ManifestError):
            load_manifest(b"{broken")

    def test_no_trust_claim(self):
        # Metadata validation does NOT authenticate this self-asserted signature.
        doc = valid_manifest()
        doc["provenance"]["signature"] = "fake-signature"
        self.assertEqual(validate_manifest(doc), doc)


if __name__ == "__main__":
    unittest.main()
