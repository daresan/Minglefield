import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.platform_payload_builder import build_inventory, write_inventory
from server.platform_payload_integrity import PayloadError, verify_payload


class PlatformPayloadBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = self.root / "payload"
        (self.payload / "app").mkdir(parents=True)
        (self.payload / "app" / "main.py").write_bytes(b"print(1)\n")
        (self.payload / "config.json").write_bytes(b"{}")

    def test_deterministic_inventory(self):
        self.assertEqual(build_inventory(self.payload), build_inventory(self.payload))

    def test_complete_inventory_verifies(self):
        raw = build_inventory(self.payload)
        self.assertEqual(verify_payload(self.payload, raw), 2)
        self.assertEqual([x["path"] for x in json.loads(raw)["files"]],
                         ["app/main.py", "config.json"])

    def test_digest_matches_written_bytes(self):
        path = self.root / "files.json"
        digest = write_inventory(self.payload, path)
        self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(verify_payload(self.payload, path.read_bytes(),
                                        expected_inventory_sha256=digest), 2)

    def test_refuse_overwrite(self):
        path = self.root / "files.json"
        write_inventory(self.payload, path)
        with self.assertRaises(FileExistsError):
            write_inventory(self.payload, path)

    def test_refuse_inside_payload(self):
        with self.assertRaises(PayloadError):
            write_inventory(self.payload, self.payload / "inventory.json")

    def test_refuse_empty_payload(self):
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(PayloadError):
            build_inventory(empty)

    def test_mutation_detected_after_generation(self):
        raw = build_inventory(self.payload)
        (self.payload / "config.json").write_bytes(b"changed")
        with self.assertRaises(PayloadError):
            verify_payload(self.payload, raw)

    def test_symlink_rejected_when_available(self):
        link = self.payload / "shortcut"
        try:
            link.symlink_to(self.payload / "app", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(PayloadError):
            build_inventory(self.payload)

    def test_case_collisions_rejected(self):
        (self.payload / "APP").mkdir()
        (self.payload / "APP" / "MAIN.PY").write_bytes(b"other")
        with self.assertRaises(PayloadError):
            build_inventory(self.payload)


if __name__ == "__main__":
    unittest.main()
