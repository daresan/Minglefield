import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_local_trust import local_discovery_catalog
from game_integration_updates import discover_integration_update

SOURCE = {"provider": "github", "repository": "daresan/minglefield-integration-test"}
ENTRY = {"integration_id": "community.daresan.test",
         "publisher": "daresan", "release_source": SOURCE,
         "declared_version": "1.0.0"}
EMPTY = {"state": "available", "integrations": []}


class LocalIntegrationTrustTests(unittest.TestCase):
    def test_operator_approved_source_without_central_registry(self):
        catalog, entries = local_discovery_catalog(
            EMPTY, [ENTRY], ["daresan/minglefield-integration-test"])
        self.assertEqual(entries[0]["source_state"], "registry_match")
        self.assertEqual(catalog["integrations"][0]["trust_tier"], "local")
        calls = []
        def fetch(repository):
            calls.append(repository)
            return {"state": "available", "releases": [
                {"tag_name": "v1.1.0", "release_notes": "Test"}]}
        outcome = discover_integration_update(
            entries[0], catalog, fetcher=fetch,
            compare_fetcher=lambda *_: {"state": "unknown"})
        self.assertEqual(calls, ["daresan/minglefield-integration-test"])
        self.assertEqual(outcome["available_version"], "v1.1.0")
        self.assertFalse(outcome["installation_allowed"])
        self.assertEqual(outcome["verification_state"], "unknown")

    def test_unapproved_source_is_not_promoted(self):
        catalog, entries = local_discovery_catalog(EMPTY, [ENTRY], [])
        self.assertEqual(catalog["integrations"], [])
        self.assertEqual(entries[0]["source_state"], "source_not_trusted_by_host")

    def test_registry_identity_conflict_not_overridden(self):
        catalog, entries = local_discovery_catalog(
            {"state": "available", "integrations": [{
                "integration_id": ENTRY["integration_id"], "publisher": "different",
                "release_source": SOURCE}]}, [ENTRY],
            ["daresan/minglefield-integration-test"])
        self.assertEqual(entries[0]["source_state"], "source_mismatch")
        self.assertEqual(catalog["integrations"][0]["publisher"], "different")

    def test_local_source_does_not_change_unverified_installation(self):
        catalog, entries = local_discovery_catalog(
            {"state": "unavailable", "integrations": []}, [ENTRY],
            ["daresan/minglefield-integration-test"])
        self.assertEqual(catalog["state"], "available")
        self.assertEqual(entries[0]["source_state"], "registry_match")


if __name__ == "__main__":
    unittest.main()
