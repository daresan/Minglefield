"""Offline negative and positive provenance checks; no network or Game writes."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_assessment_provenance import verify_assessment_document_bytes

IDENTITY = dict(expected_integration_id="community.daresan.test",
                authorized_source={"provider": "github", "repository": "daresan/minglefield-integration-test"},
                from_version="v1.0.0", to_version="v1.1.0")
BASE = dict(integration_id=IDENTITY["expected_integration_id"],
            release_source=IDENTITY["authorized_source"],
            from_version="v1.0.0", to_version="v1.1.0")
DOCUMENTS = {
    "compatibility": {**BASE, "contract_version": "0.1",
                      "requirements": [{"capability": "game.api", "constraint": ">=1"}]},
    "migration": {**BASE, "plan_version": "0.1",
                  "operations": [{"kind": "replace", "path": "plugins/main.py"}],
                  "recovery": {"strategy": "restore_backup"}},
}


def raw(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def check(kind, data, **overrides):
    args = {**IDENTITY, "expected_sha256": hashlib.sha256(data).hexdigest(),
            "independent_digest_authenticated": True, **overrides}
    return verify_assessment_document_bytes(kind, data, **args)


class AssessmentProvenanceTests(unittest.TestCase):
    def test_exact_bytes_and_binding(self):
        for kind, doc in DOCUMENTS.items():
            with self.subTest(kind=kind):
                result = check(kind, raw(doc))
                self.assertEqual(result["state"], "verified")
                self.assertIs(result["provenance_verified"], True)
                self.assertIs(result["installation_allowed"], False)

    def test_digest_and_authority_fail_closed(self):
        for kind, doc in DOCUMENTS.items():
            data = raw(doc)
            with self.subTest(kind=kind):
                self.assertEqual(check(kind, data, independent_digest_authenticated=False)["state"], "unknown")
                self.assertEqual(check(kind, data, expected_sha256=None)["state"], "unknown")
                self.assertEqual(check(kind, data, expected_sha256="0" * 64)["reason"], "assessment_digest_mismatch")
                changed = data + b" "
                self.assertEqual(check(kind, changed, expected_sha256=hashlib.sha256(data).hexdigest())["state"], "invalid")

    def test_bound_digest_does_not_override_wrong_identity(self):
        for kind, doc in DOCUMENTS.items():
            with self.subTest(kind=kind):
                self.assertEqual(check(kind, raw({**doc, "to_version": "v2.0.0"}))["reason"],
                                 "assessment_release_identity_mismatch")
                self.assertEqual(check(kind, raw(doc), authorized_source={
                    "provider": "github", "repository": "attacker/other"})["state"], "invalid")

    def test_malformed_json_and_schema_fail_closed(self):
        self.assertEqual(check("compatibility", b"{bad")["reason"], "invalid_assessment_json")
        self.assertEqual(check("compatibility", raw({"foo": 1}))["reason"], "assessment_schema_invalid")
        self.assertEqual(check("compatibility", b"")["reason"], "invalid_assessment_bytes")
        self.assertEqual(check("compatibility", b"x" * (1024 * 1024 + 1))["reason"],
                         "invalid_assessment_bytes")


if __name__ == "__main__":
    unittest.main()
