"""Curated integration registry contract checks; no network or writes."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

from game_integration_registry import load_registry, validate_registry


class GameIntegrationRegistryTests(unittest.TestCase):
    def test_committed_registry_is_valid_and_empty_until_verified(self):
        self.assertEqual(load_registry()["integrations"], [])

    def test_development_fixture_is_explicit_and_not_in_default_registry(self):
        fixture_path = ROOT / "tests" / "fixtures" / "integrations" / "registry.json"
        fixture = load_registry(path=fixture_path)
        self.assertEqual(len(fixture["integrations"]), 1)
        entry = fixture["integrations"][0]
        self.assertEqual(entry["integration_id"], "community.daresan.test")
        self.assertEqual(entry["trust_tier"], "community")
        self.assertEqual(entry["release_source"], {
            "provider": "github",
            "repository": "daresan/minglefield-integration-test",
        })
        self.assertNotIn(
            entry["integration_id"],
            [item["integration_id"] for item in load_registry()["integrations"]],
        )

    def test_official_and_community_entries(self):
        data = {"registry_version": "0.1", "integrations": [
            {"integration_id": "minglefield.game.core", "name": "Core",
             "publisher": "minglefield", "trust_tier": "official",
             "release_source": {"provider": "github", "repository": "example/core"}},
            {"integration_id": "community.alice.godot", "name": "Godot",
             "publisher": "alice", "trust_tier": "community",
             "release_source": {"provider": "github", "repository": "alice/godot"}}
        ]}
        self.assertEqual(len(validate_registry(data)["integrations"]), 2)
        duplicate = copy.deepcopy(data)
        duplicate["integrations"].append(copy.deepcopy(duplicate["integrations"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate_integration_id"):
            validate_registry(duplicate)

    def test_reserved_namespaces_and_publisher_binding(self):
        template = {"registry_version": "0.1", "integrations": [
            {"integration_id": "community.alice.game", "name": "Example",
             "publisher": "alice", "trust_tier": "community",
             "release_source": {"provider": "github", "repository": "alice/game"}}
        ]}
        for integration_id, tier, publisher in [
            ("minglefield.game", "community", "alice"),
            ("community.alice.game", "official", "alice"),
            ("community.bob.game", "community", "alice"),
            ("community.alice", "community", "alice"),
        ]:
            data = copy.deepcopy(template)
            data["integrations"][0].update(integration_id=integration_id, trust_tier=tier, publisher=publisher)
            with self.subTest(integration_id=integration_id, tier=tier):
                with self.assertRaises(ValueError):
                    validate_registry(data)

    def test_rejects_unknown_fields_and_malformed_sources(self):
        template = {"registry_version": "0.1", "integrations": [
            {"integration_id": "minglefield.game.core", "name": "Core",
             "publisher": "minglefield", "trust_tier": "official",
             "release_source": {"provider": "github", "repository": "example/core"}}
        ]}
        for change in ("unknown", "bad_provider", "bad_repository"):
            data = copy.deepcopy(template)
            if change == "unknown":
                data["integrations"][0]["unreviewed_url"] = "https://example.com"
            elif change == "bad_provider":
                data["integrations"][0]["release_source"]["provider"] = "arbitrary"
            else:
                data["integrations"][0]["release_source"]["repository"] = "https://example.com"
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_registry(data)


if __name__ == "__main__":
    unittest.main()
