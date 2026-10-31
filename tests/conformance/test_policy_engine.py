"""MAP policy decision point unit tests; run python -m unittest discover -s tests/conformance -p 'test_*.py'."""
import json
import unittest
from pathlib import Path
from sys import path

ROOT = Path(__file__).resolve().parents[2]
path.insert(0, str(ROOT / "server"))
from policy_engine import PolicyEngine

EXAMPLES = ROOT / "examples" / "map" / "v0.1"


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.agent = json.loads((EXAMPLES / "shared-agent.json").read_text())
        self.grant = json.loads((EXAMPLES / "delegation-grant.json").read_text())
        self.engine = PolicyEngine(self.agent)
        self.assertTrue(self.engine.add_grant(self.grant, verified_actor="user.alice").allowed)

    def check(self, **overrides):
        args = dict(verified_requester="user.charlie", delegation_id="grant.01",
                    scope="game.test_feedback", target_id="game.maze",
                    at="2026-10-31T12:15:00Z")
        args.update(overrides)
        return self.engine.authorize(**args)

    def test_valid(self):
        self.assertTrue(self.check().allowed)

    def test_wrong_requester(self):
        self.assertFalse(self.check(verified_requester="user.mallory").allowed)

    def test_scope_and_target(self):
        self.assertEqual(self.check(scope="game.develop").reason, "scope_denied")
        self.assertEqual(self.check(target_id="game.other").reason, "target_denied")

    def test_expiry(self):
        self.assertEqual(self.check(at="2026-10-31T14:00:00Z").reason, "outside_validity")

    def test_budget_and_idempotency(self):
        self.assertTrue(self.check(cost_minor=150, operation_id="op.1").allowed)
        self.assertTrue(self.check(cost_minor=150, operation_id="op.1").allowed)
        self.assertEqual(self.check(cost_minor=60, operation_id="op.2").reason, "budget_exceeded")

    def test_operation_conflict(self):
        self.assertTrue(self.check(cost_minor=10, operation_id="op.1").allowed)
        self.assertEqual(self.check(cost_minor=20, operation_id="op.1").reason, "operation_id_conflict")

    def test_invalid_cost(self):
        self.assertEqual(self.check(cost_minor=-1, operation_id="op.1").reason, "invalid_cost")
        self.assertEqual(self.check(cost_minor=1).reason, "operation_id_required")

    def test_revoke(self):
        self.assertFalse(self.engine.revoke(delegation_id="grant.01", verified_actor="user.mallory").allowed)
        self.assertTrue(self.engine.revoke(delegation_id="grant.01", verified_actor="user.charlie").allowed)
        self.assertEqual(self.check().reason, "grant_revoked")

    def test_suspend_resume(self):
        self.assertFalse(self.engine.suspend(verified_actor="user.bob").allowed)
        self.assertTrue(self.engine.suspend(verified_actor="user.alice").allowed)
        self.assertEqual(self.check().reason, "agent_suspended")
        self.assertTrue(self.engine.resume(verified_actor="user.alice").allowed)
        self.assertTrue(self.check().allowed)

    def test_grant_approval_and_duplicate(self):
        other = PolicyEngine(self.agent)
        self.assertFalse(other.add_grant(self.grant, verified_actor="user.bob").allowed)
        self.assertFalse(other.add_grant(self.grant, verified_actor="user.mallory").allowed)
        self.assertEqual(self.engine.add_grant(self.grant, verified_actor="user.alice").reason,
                         "duplicate_or_revoked_grant")


if __name__ == "__main__":
    unittest.main()
