import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_staging import validate_staging_manifest, verify_staged_bytes


class InstallStagingTests(unittest.TestCase):
    def setUp(self):
        self.content = {"assets/a.glb": b"model", "scripts/main.py": b"print(1)"}
        self.entries = [{"path": path, "size": len(data),
                         "sha256": hashlib.sha256(data).hexdigest()}
                        for path, data in self.content.items()]

    def test_plan_identity_is_order_independent(self):
        a = validate_staging_manifest(self.entries)
        b = validate_staging_manifest(list(reversed(self.entries)))
        self.assertEqual(a["state"], "valid")
        self.assertEqual(a["plan_sha256"], b["plan_sha256"])
        self.assertFalse(a["mutation_performed"])

    def test_staged_bytes_match_and_never_grant_installation(self):
        plan = validate_staging_manifest(self.entries)
        result = verify_staged_bytes(plan, self.content.__getitem__)
        self.assertEqual(result["state"], "verified_snapshot")
        self.assertFalse(result["installation_allowed"])

    def test_tampered_or_missing_staged_bytes_fail_closed(self):
        plan = validate_staging_manifest(self.entries)
        self.assertEqual(verify_staged_bytes(
            plan, lambda p: b"changed")["reason"], "staged_bytes_mismatch")
        self.assertEqual(verify_staged_bytes(
            plan, lambda p: (_ for _ in ()).throw(OSError()))["reason"],
            "staged_file_unavailable")

    def test_duplicate_overlapping_and_unsafe_paths_rejected(self):
        for entries, reason in (
            (self.entries + [dict(self.entries[0])], "duplicate_destination_path"),
            ([{**self.entries[0], "path": "assets"},
              self.entries[0]], "overlapping_destination_paths"),
            ([{**self.entries[0], "path": "../escape"}], "invalid_staging_entry"),
            ([{**self.entries[0], "size": True}], "invalid_staging_entry"),
        ):
            with self.subTest(reason=reason):
                self.assertEqual(validate_staging_manifest(entries)["reason"], reason)


if __name__ == "__main__":
    unittest.main()
