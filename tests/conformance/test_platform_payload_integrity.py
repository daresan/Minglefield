import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.platform_payload_integrity import PayloadError, parse_inventory, verify_payload


class PlatformPayloadIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "app").mkdir()
        (self.root / "app" / "start.py").write_bytes(b"print('alpha')\n")
        self.raw = json.dumps({"format_version": 1, "files": [{
            "path": "app/start.py",
            "sha256": hashlib.sha256(b"print('alpha')\n").hexdigest(),
            "size": len(b"print('alpha')\n")
        }]}).encode()

    def test_valid_payload(self):
        self.assertEqual(verify_payload(self.root, self.raw), 1)

    def test_inventory_digest(self):
        self.assertEqual(verify_payload(self.root, self.raw,
            expected_inventory_sha256=hashlib.sha256(self.raw).hexdigest()), 1)

    def test_bad_inventory_digest(self):
        with self.assertRaises(PayloadError):
            verify_payload(self.root, self.raw, expected_inventory_sha256="0" * 64)

    def test_modified_payload(self):
        (self.root / "app" / "start.py").write_bytes(b"print('omega')\n")
        with self.assertRaises(PayloadError):
            verify_payload(self.root, self.raw)

    def test_missing_payload(self):
        (self.root / "app" / "start.py").unlink()
        with self.assertRaises(PayloadError):
            verify_payload(self.root, self.raw)

    def test_extra_payload(self):
        (self.root / "extra").write_bytes(b"unexpected")
        with self.assertRaises(PayloadError):
            verify_payload(self.root, self.raw)

    def test_traversal_rejected(self):
        doc = json.loads(self.raw)
        doc["files"][0]["path"] = "../escape"
        with self.assertRaises(PayloadError):
            parse_inventory(json.dumps(doc).encode())

    def test_duplicate_path_rejected(self):
        doc = json.loads(self.raw)
        doc["files"].append(dict(doc["files"][0]))
        with self.assertRaises(PayloadError):
            parse_inventory(json.dumps(doc).encode())

    def test_case_collision_rejected(self):
        doc = json.loads(self.raw)
        doc["files"].append({**doc["files"][0], "path": "APP/START.PY"})
        with self.assertRaises(PayloadError):
            parse_inventory(json.dumps(doc).encode())

    def test_symlink_rejected(self):
        link = self.root / "shortcut"
        try:
            link.symlink_to(self.root / "app", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(PayloadError):
            verify_payload(self.root, self.raw)

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(PayloadError):
            parse_inventory(b'{"format_version":1,"format_version":1,"files":[]}')

    def test_invalid_size_rejected(self):
        doc = json.loads(self.raw)
        doc["files"][0]["size"] = True
        with self.assertRaises(PayloadError):
            parse_inventory(json.dumps(doc).encode())


if __name__ == "__main__":
    unittest.main()
