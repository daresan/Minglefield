"""Per-request operator approval reload and revocation regression tests."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_assessment_approvals import preview_with_operator_approvals

REPO = "daresan/minglefield-integration-test"
SOURCE = {"provider": "github", "repository": REPO}
ARGS = dict(integration_id="community.daresan.test", release_source=SOURCE,
            from_version="v1.0.0", to_version="v1.1.0")
DOCUMENT = {**ARGS, "contract_version": "0.1",
            "requirements": [{"capability": "game.api", "constraint": ">=1.0"}]}
RAW = json.dumps(DOCUMENT).encode()
ROW = dict(kind="compatibility", integration_id=ARGS["integration_id"],
           repository=REPO, from_version="v1.0.0", to_version="v1.1.0",
           commit="6df11272a9ca14dcfb8dc3bbe26b29c189d12253",
           sha256=hashlib.sha256(RAW).hexdigest())


class ApprovalReloadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "approvals.json"
        self.calls = []

    def write(self, approvals):
        self.path.write_text(json.dumps({"format_version": "0.1",
                                         "approvals": approvals}), encoding="utf-8")

    def preview(self):
        def loader(repo, commit, kind):
            self.calls.append((repo, commit, kind))
            return RAW
        return preview_with_operator_approvals(
            manifest_path=self.path, byte_loader=loader, **ARGS)

    def test_approval_then_revocation_takes_effect_next_request(self):
        self.write([ROW])
        approved = self.preview()
        self.assertEqual(approved["compatibility"]["document_provenance"], "verified")
        self.assertEqual(len(self.calls), 1)
        self.write([])
        revoked = self.preview()
        self.assertNotIn("document_provenance", revoked["compatibility"])
        self.assertEqual(revoked["compatibility"]["state"], "unknown")
        self.assertEqual(len(self.calls), 1)
        self.assertIs(revoked["installation_allowed"], False)

    def test_missing_and_malformed_manifest_never_use_previous_approval(self):
        self.write([ROW])
        self.assertEqual(self.preview()["compatibility"]["document_provenance"], "verified")
        self.path.unlink()
        self.assertEqual(self.preview()["compatibility"]["state"], "unknown")
        self.path.write_text("{broken", encoding="utf-8")
        self.assertEqual(self.preview()["compatibility"]["state"], "unknown")
        self.assertEqual(len(self.calls), 1)

    def test_new_approval_only_affects_subsequent_request(self):
        self.write([])
        self.assertEqual(self.preview()["compatibility"]["state"], "unknown")
        self.write([ROW])
        self.assertEqual(self.preview()["compatibility"]["document_provenance"], "verified")
        self.assertEqual(len(self.calls), 1)

    def test_bad_digest_never_promotes_document(self):
        self.write([{**ROW, "sha256": "0" * 64}])
        result = self.preview()
        self.assertNotIn("document_provenance", result["compatibility"])
        self.assertIs(result["installation_allowed"], False)


if __name__ == "__main__":
    unittest.main()
