"""Read-only discovery must reload operator approvals for every request."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_assessment_approvals import discover_with_operator_approvals

REPO = "daresan/minglefield-integration-test"
SOURCE = {"provider": "github", "repository": REPO}
IDENTITY = "community.daresan.test"
DOCUMENT = {"contract_version": "0.1", "integration_id": IDENTITY,
            "release_source": SOURCE, "from_version": "v1.0.0",
            "to_version": "v1.1.0",
            "requirements": [{"capability": "game.api", "constraint": ">=1.0"}]}
RAW = json.dumps(DOCUMENT).encode()
ROW = {"kind": "compatibility", "integration_id": IDENTITY,
       "repository": REPO, "from_version": "v1.0.0",
       "to_version": "v1.1.0", "commit": "6df11272a9ca14dcfb8dc3bbe26b29c189d12253",
       "sha256": hashlib.sha256(RAW).hexdigest()}
ENTRY = {"integration_id": IDENTITY, "source_state": "registry_match",
         "release_source": SOURCE, "declared_version": "v1.0.0"}
CATALOG = {"state": "available", "integrations": [
    {"integration_id": IDENTITY, "release_source": SOURCE,
     "publisher": "test-publisher"}]}


class DiscoveryApprovalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "approvals.json"
        self.calls = []

    def write(self, rows):
        self.path.write_text(json.dumps({"format_version": "0.1",
                                         "approvals": rows}), encoding="utf-8")

    def discover(self):
        def loader(*args):
            self.calls.append(args)
            return RAW
        return discover_with_operator_approvals(
            ENTRY, CATALOG, manifest_path=self.path, byte_loader=loader,
            fetcher=lambda repo: {"state": "available", "complete": True,
                                  "releases": [{"tag_name": "v1.1.0",
                                                "draft": False, "prerelease": False}]},
            compare_fetcher=lambda *args: {"state": "available", "files": []})

    def test_discovery_reload_and_revocation(self):
        self.write([ROW])
        approved = self.discover()
        self.assertEqual(approved["preview"]["compatibility"]["document_provenance"], "verified")
        self.assertEqual(approved["preview"]["compatibility"]["state"], "unknown")
        self.assertFalse(approved["installation_allowed"])
        self.write([])
        revoked = self.discover()
        self.assertNotIn("document_provenance", revoked["preview"]["compatibility"])
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(revoked["preview"]["installation_allowed"])

    def test_manifest_removed_fails_closed(self):
        self.write([ROW])
        self.discover()
        self.path.unlink()
        result = self.discover()
        self.assertEqual(result["preview"]["compatibility"]["state"], "unknown")
        self.assertNotIn("document_provenance", result["preview"]["compatibility"])
        self.assertEqual(len(self.calls), 1)

    def test_untrusted_registry_does_not_fetch_approved_document(self):
        self.write([ROW])
        entry = {**ENTRY, "source_state": "unverified"}
        result = discover_with_operator_approvals(
            entry, CATALOG, manifest_path=self.path,
            byte_loader=lambda *args: self.fail("must not fetch"),
            fetcher=lambda *args: self.fail("must not discover"))
        self.assertEqual(result["reason"], "untrusted_source")
        self.assertFalse(result["installation_allowed"])


if __name__ == "__main__":
    unittest.main()
