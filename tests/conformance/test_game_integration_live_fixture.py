"""Opt-in T4: real GitHub release discovery with a host-local trust source.

Run with MINGLEFIELD_LIVE_GITHUB=1. No GitHub calls during routine CI.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_local_trust import local_discovery_catalog
from game_integration_updates import discover_integration_update

REPOSITORY = "daresan/minglefield-integration-test"
SOURCE = {"provider": "github", "repository": REPOSITORY}
ENTRY = {"integration_id": "community.daresan.test", "publisher": "daresan",
         "release_source": SOURCE, "declared_version": "1.0.0"}
EMPTY_REGISTRY = {"state": "available", "integrations": []}


@unittest.skipUnless(os.environ.get("MINGLEFIELD_LIVE_GITHUB") == "1",
                     "T4 requires explicit MINGLEFIELD_LIVE_GITHUB=1")
class LiveHostLocalReleaseTests(unittest.TestCase):
    def test_real_github_release_discovery_without_central_registry(self):
        catalog, entries = local_discovery_catalog(
            EMPTY_REGISTRY, [ENTRY], [REPOSITORY])
        self.assertEqual(entries[0]["source_state"], "registry_match")
        # No fetcher or compare_fetcher injection: both use real GitHub APIs.
        result = discover_integration_update(entries[0], catalog)
        self.assertNotIn(result.get("reason"), (
            "not_in_curated_registry", "untrusted_source", "registry_unavailable"))
        self.assertNotEqual(result.get("reason"), "release_source_unavailable",
                            "Live GitHub release API unavailable")
        self.assertNotEqual(result.get("reason"), "no_comparable_releases",
                            "Fixture repository needs a stable GitHub release")
        self.assertIn("available_version", result, result)
        self.assertEqual(result["comparison_basis"], "declared_version")
        self.assertEqual(result["verification_state"], "unknown")
        self.assertFalse(result["installation_allowed"])

    def test_unapproved_source_never_contacts_github(self):
        catalog, entries = local_discovery_catalog(EMPTY_REGISTRY, [ENTRY], [])
        self.assertEqual(entries[0]["source_state"], "source_not_trusted_by_host")
        self.assertEqual(catalog["integrations"], [])


if __name__ == "__main__":
    unittest.main()
