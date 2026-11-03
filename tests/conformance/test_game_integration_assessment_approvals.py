"""Operator approval manifest tests; no production trust anchors are created."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_assessment_approvals import (
    read_operator_approvals, make_operator_assessment_resolver)

ROW = {"kind": "compatibility", "integration_id": "community.daresan.test",
       "repository": "daresan/minglefield-integration-test",
       "from_version": "v1.0.0", "to_version": "v1.1.0",
       "commit": "6df11272a9ca14dcfb8dc3bbe26b29c189d12253",
       "sha256": "d14e3952d1afad096ffb31c20f12fab4b74f1ca57af3edefbc3be0c72aef11e5"}


class OperatorApprovalsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "operator.json"

    def write(self, approvals, **extra):
        self.path.write_text(json.dumps(
            {"format_version": "0.1", "approvals": approvals, **extra}),
            encoding="utf-8")

    def test_explicit_manifest_and_exact_lookup(self):
        self.write([ROW])
        records = read_operator_approvals(self.path)
        self.assertEqual(len(records), 1)
        calls = []
        resolver = make_operator_assessment_resolver(
            self.path, byte_loader=lambda *args: calls.append(args) or b"{}")
        result = resolver(kind="compatibility", integration_id=ROW["integration_id"],
                          release_source={"provider": "github", "repository": ROW["repository"]},
                          from_version="v1.0.0", to_version="v1.1.0")
        self.assertEqual(result["expected_sha256"], ROW["sha256"])
        self.assertEqual(calls[0][1], ROW["commit"])
        self.assertIsNone(resolver(
            kind="compatibility", integration_id=ROW["integration_id"],
            release_source={"provider": "github", "repository": ROW["repository"]},
            from_version="v1.0.0", to_version="v9.9.9"))

    def test_missing_relative_and_symlink_paths_denied(self):
        for path in (None, "operator.json", self.path):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    read_operator_approvals(path)
        self.write([ROW])
        alias = Path(self.temp.name) / "alias.json"
        try:
            alias.symlink_to(self.path)
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(ValueError):
            read_operator_approvals(alias)

    def test_duplicate_and_malformed_approvals_denied(self):
        for rows in ([ROW, ROW], [{**ROW, "commit": "main"}],
                     [{**ROW, "sha256": "bad"}], [{**ROW, "extra": True}]):
            with self.subTest(rows=rows):
                self.write(rows)
                with self.assertRaises(ValueError):
                    read_operator_approvals(self.path)

    def test_empty_manifest_has_no_approvals(self):
        self.write([])
        self.assertEqual(read_operator_approvals(self.path), {})


if __name__ == "__main__":
    unittest.main()
