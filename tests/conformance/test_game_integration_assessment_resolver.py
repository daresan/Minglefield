"""Focused tests for operator-controlled assessment resolver."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_assessment_resolver import make_assessment_resolver
from game_integration_assessment_preview import preview_release_assessments

REPO = "daresan/minglefield-integration-test"
COMMIT = "6df11272a9ca14dcfb8dc3bbe26b29c189d12253"
SOURCE = {"provider": "github", "repository": REPO}
ARGS = {"integration_id": "community.daresan.test", "release_source": SOURCE,
        "from_version": "v1.0.0", "to_version": "v1.1.0"}
DOC = {**ARGS, "contract_version": "0.1",
       "requirements": [{"capability": "game.api", "constraint": ">=1.0"}]}
RAW = json.dumps(DOC).encode()
KEY = ("compatibility", ARGS["integration_id"], REPO, "v1.0.0", "v1.1.0")


class ApprovedResolverTests(unittest.TestCase):
    def test_exact_approved_identity_and_digest(self):
        calls = []
        records = {KEY: {"sha256": hashlib.sha256(RAW).hexdigest(), "commit": COMMIT}}
        def load(repo, commit, kind):
            calls.append((repo, commit, kind))
            return RAW
        resolver = make_assessment_resolver(records, byte_loader=load)
        records.clear()  # Mutating caller's manifest must not alter the resolver.
        result = preview_release_assessments(**ARGS, resolver=resolver)
        self.assertEqual(result["compatibility"]["document_provenance"], "verified")
        self.assertEqual(result["compatibility"]["state"], "unknown")
        self.assertEqual(result["migration"]["state"], "unknown")
        self.assertEqual(calls, [(REPO, COMMIT, "compatibility")])
        self.assertIs(result["installation_allowed"], False)

    def test_unapproved_source_or_version_never_fetches(self):
        calls = []
        resolver = make_assessment_resolver(
            {KEY: {"sha256": hashlib.sha256(RAW).hexdigest(), "commit": COMMIT}},
            byte_loader=lambda *args: calls.append(args))
        for args in ({**ARGS, "to_version": "v1.2.0"},
                     {**ARGS, "release_source": {"provider": "github", "repository": "evil/repo"}}):
            result = preview_release_assessments(**args, resolver=resolver)
            self.assertEqual(result["compatibility"]["state"], "unknown")
        self.assertEqual(calls, [])

    def test_wrong_bytes_and_loader_failure_fail_closed(self):
        manifest = {KEY: {"sha256": hashlib.sha256(RAW).hexdigest(), "commit": COMMIT}}
        for loader in (lambda *args: RAW + b" ", lambda *args: (_ for _ in ()).throw(OSError("offline"))):
            result = preview_release_assessments(
                **ARGS, resolver=make_assessment_resolver(manifest, byte_loader=loader))
            self.assertNotEqual(result["compatibility"].get("document_provenance"), "verified")
            self.assertIs(result["installation_allowed"], False)

    def test_invalid_manifest_rejected(self):
        with self.assertRaises(ValueError):
            make_assessment_resolver({KEY: {"sha256": "0" * 64, "commit": "main"}},
                                     byte_loader=lambda *args: RAW)


if __name__ == "__main__":
    unittest.main()
