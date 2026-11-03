"""Exact release binding tests: schema validity never implies provenance."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_assessment_binding import validate_assessment_binding

SOURCE = {"provider": "github", "repository": "alice/godot"}
IDENTITY = dict(expected_integration_id="community.alice.godot",
                authorized_source=SOURCE, from_version="v1.0.0", to_version="v1.1.0")
BASE = dict(integration_id=IDENTITY["expected_integration_id"],
            release_source=SOURCE, from_version="v1.0.0", to_version="v1.1.0")
DOCS = {
    "compatibility": {**BASE, "contract_version": "0.1",
                      "requirements": [{"capability": "game.api", "constraint": ">=1"}]},
    "migration": {**BASE, "plan_version": "0.1",
                  "operations": [{"kind": "replace", "path": "plugins/main.py"}],
                  "recovery": {"strategy": "restore_backup"}},
}


class AssessmentBindingTests(unittest.TestCase):
    def test_valid_identity_is_not_trust_or_installation(self):
        for kind, document in DOCS.items():
            with self.subTest(kind=kind):
                result = validate_assessment_binding(kind, document, **IDENTITY)
                self.assertEqual(result["state"], "matched")
                self.assertIs(result["provenance_verified"], False)
                self.assertIs(result["installation_allowed"], False)

    def test_source_version_and_package_mismatch_fail_closed(self):
        for kind, document in DOCS.items():
            for field, value in (
                ("integration_id", "community.evil.godot"),
                ("release_source", {"provider": "github", "repository": "evil/godot"}),
                ("from_version", "v0.9.0"),
                ("to_version", "v2.0.0"),
            ):
                with self.subTest(kind=kind, field=field):
                    result = validate_assessment_binding(kind, {**document, field: value}, **IDENTITY)
                    self.assertEqual(result["state"], "invalid")
                    self.assertEqual(result["reason"], "assessment_release_identity_mismatch")

    def test_malformed_and_missing_authority_fail_closed(self):
        self.assertEqual(validate_assessment_binding("other", {}, **IDENTITY)["state"], "invalid")
        for kind, document in DOCS.items():
            with self.subTest(kind=kind):
                self.assertEqual(validate_assessment_binding(kind, {**document, "unexpected": True},
                                                             **IDENTITY)["state"], "invalid")
                self.assertEqual(validate_assessment_binding(kind, document,
                    **{**IDENTITY, "authorized_source": None})["state"], "unknown")
                self.assertEqual(validate_assessment_binding(kind, None, **IDENTITY)["state"], "invalid")


if __name__ == "__main__":
    unittest.main()
