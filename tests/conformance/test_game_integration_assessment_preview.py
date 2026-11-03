"""Focused read-only assessment preview trust-boundary tests."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_assessment_preview import preview_release_assessments

SOURCE = {"provider": "github", "repository": "daresan/minglefield-integration-test"}
ARGS = dict(integration_id="community.daresan.test", release_source=SOURCE,
            from_version="v1.0.0", to_version="v1.1.0")


def document(kind):
    base = dict(integration_id=ARGS["integration_id"], release_source=SOURCE,
                from_version=ARGS["from_version"], to_version=ARGS["to_version"])
    if kind == "compatibility":
        return {**base, "contract_version": "0.1",
                "requirements": [{"capability": "game.api", "constraint": ">=1.0"}]}
    return {**base, "plan_version": "0.1",
            "operations": [{"kind": "replace", "path": "plugins/main.py"}],
            "recovery": {"strategy": "restore_backup"}}


def evidence(kind, *, authenticated=True, mismatch=False):
    raw = json.dumps(document(kind)).encode()
    return {"raw_bytes": raw, "expected_sha256": "0" * 64 if mismatch
            else hashlib.sha256(raw).hexdigest(), "authenticated": authenticated}


class AssessmentPreviewTests(unittest.TestCase):
    def test_missing_resolver_never_grants_trust(self):
        result = preview_release_assessments(**ARGS)
        self.assertEqual(result["compatibility"]["state"], "unknown")
        self.assertEqual(result["migration"]["state"], "unknown")
        self.assertIs(result["installation_allowed"], False)

    def test_authenticated_bytes_do_not_prove_target_or_recovery(self):
        result = preview_release_assessments(
            **ARGS, resolver=lambda *, kind, **kwargs: evidence(kind))
        self.assertEqual(result["compatibility"]["state"], "unknown")
        self.assertEqual(result["migration"]["state"], "unknown")
        self.assertEqual(result["compatibility"]["document_provenance"], "verified")
        self.assertEqual(result["migration"]["document_provenance"], "verified")
        self.assertIs(result["installation_allowed"], False)

    def test_untrusted_or_changed_evidence_is_not_promoted(self):
        for authenticated, mismatch in ((False, False), (True, True)):
            with self.subTest(authenticated=authenticated, mismatch=mismatch):
                result = preview_release_assessments(
                    **ARGS, resolver=lambda *, kind, **kwargs:
                    evidence(kind, authenticated=authenticated, mismatch=mismatch))
                self.assertNotIn("document_provenance", result["compatibility"])
                self.assertNotIn("document_provenance", result["migration"])
                self.assertIs(result["installation_allowed"], False)

    def test_resolver_failure_is_unknown(self):
        def broken(**kwargs):
            raise RuntimeError("offline")
        result = preview_release_assessments(**ARGS, resolver=broken)
        self.assertEqual(result["compatibility"]["state"], "unknown")
        self.assertEqual(result["migration"]["state"], "unknown")


if __name__ == "__main__":
    unittest.main()
