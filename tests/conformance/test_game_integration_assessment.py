"""P1.4f.3: offline fail-closed assessment checks; no installation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_assessment import assess_compatibility, assess_migration


class GameIntegrationAssessmentTests(unittest.TestCase):
    def test_compatibility_defaults_and_untrusted_claims(self):
        expected = {"state": "unknown", "reason": "no_verified_compatibility_contract",
                    "requires_manual_review": True}
        self.assertEqual(assess_compatibility(), expected)
        self.assertEqual(assess_compatibility(
            {"contract_version": "0.1"}, release_bound=True,
            target_facts_verified=True, requirements_satisfied=True), expected)

    def test_compatibility_requires_complete_independent_checks(self):
        contract = {"contract_version": "0.1"}
        common = dict(trusted_contract=True, release_bound=True,
                      target_facts_verified=True, requirements_satisfied=True)
        for change in ({"release_bound": False}, {"target_facts_verified": False},
                       {"requirements_satisfied": None}):
            with self.subTest(change=change):
                self.assertEqual(assess_compatibility(contract, **(common | change))["state"], "unknown")
        self.assertEqual(assess_compatibility({"contract_version": "999"}, **common)["state"], "unknown")
        self.assertEqual(assess_compatibility(contract, **common)["state"], "compatible")
        self.assertEqual(assess_compatibility(
            contract, **(common | {"requirements_satisfied": False}))["state"], "incompatible")

    def test_migration_never_grants_installation(self):
        plan = {"plan_version": "0.1"}
        self.assertEqual(assess_migration()["state"], "unknown")
        self.assertEqual(assess_migration(plan, release_bound=True)["state"], "unknown")
        common = dict(trusted_plan=True, release_bound=True,
                      prerequisites_verified=True, recovery_verified=True)
        for change in ({"release_bound": False}, {"prerequisites_verified": False},
                       {"recovery_verified": False}):
            with self.subTest(change=change):
                self.assertEqual(assess_migration(plan, **(common | change))["state"], "unknown")
        self.assertEqual(assess_migration({"plan_version": "999"}, **common)["state"], "unknown")
        result = assess_migration(plan, **common)
        self.assertEqual(result["state"], "review_required")
        self.assertTrue(result["requires_manual_review"])


if __name__ == "__main__":
    unittest.main()
