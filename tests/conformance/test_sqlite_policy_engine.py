"""SQLite MAP policy engine persistence and concurrency tests."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sys import path

ROOT = Path(__file__).resolve().parents[2]
path.insert(0, str(ROOT / "server"))
from sqlite_policy_engine import SQLitePolicyEngine

EXAMPLES = ROOT / "examples" / "map" / "v0.1"


class SQLitePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = Path(self.tmp.name) / "policy.sqlite"
        self.agent = json.loads((EXAMPLES / "shared-agent.json").read_text())
        self.grant = json.loads((EXAMPLES / "delegation-grant.json").read_text())
        self.engine = SQLitePolicyEngine(self.database)
        self.assertTrue(self.engine.register_agent(self.agent).allowed)
        self.assertTrue(self.engine.add_grant(self.grant, verified_actor="user.alice").allowed)

    def check(self, engine=None, **overrides):
        args = dict(verified_requester="user.charlie", delegation_id="grant.01",
                    scope="game.test_feedback", target_id="game.maze",
                    at="2026-10-31T12:15:00Z")
        args.update(overrides)
        return (engine or self.engine).authorize(**args)

    def test_restart_persists_budget_and_dedup(self):
        self.assertTrue(self.check(cost_minor=150,operation_id="op.1").allowed)
        restarted = SQLitePolicyEngine(self.database)
        self.assertEqual(self.check(restarted,cost_minor=150,operation_id="op.1").reason,"already_allowed")
        self.assertEqual(self.check(restarted,cost_minor=60,operation_id="op.2").reason,"budget_exceeded")
        self.assertEqual(self.check(restarted,cost_minor=151,operation_id="op.1").reason,"operation_id_conflict")

    def test_restart_persists_revocation(self):
        self.assertTrue(self.engine.revoke(delegation_id="grant.01",verified_actor="user.charlie").allowed)
        self.assertEqual(self.check(SQLitePolicyEngine(self.database)).reason,"grant_revoked")

    def test_restart_persists_suspension(self):
        self.assertTrue(self.engine.set_suspended(agent_id="agent.shared.01",verified_actor="user.alice",suspended=True).allowed)
        restarted = SQLitePolicyEngine(self.database)
        self.assertEqual(self.check(restarted).reason,"agent_suspended")
        self.assertFalse(restarted.set_suspended(agent_id="agent.shared.01",verified_actor="user.bob",suspended=False).allowed)
        self.assertTrue(restarted.set_suspended(agent_id="agent.shared.01",verified_actor="user.alice",suspended=False).allowed)
        self.assertTrue(self.check().allowed)

    def test_concurrent_budget_cannot_overspend(self):
        def work(i):
            engine = SQLitePolicyEngine(self.database)
            return self.check(engine,cost_minor=30,operation_id="op."+str(i))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(work,range(20)))
        self.assertEqual(sum(d.allowed for d in results),6)
        self.assertTrue(all(d.reason in {"allowed","budget_exceeded"} for d in results))

    def test_concurrent_same_operation_deduplicates(self):
        def work(_):
            return self.check(SQLitePolicyEngine(self.database),cost_minor=100,operation_id="op.same")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(work,range(12)))
        self.assertEqual(sum(d.reason=="allowed" for d in results),1)
        self.assertEqual(sum(d.reason=="already_allowed" for d in results),11)
        self.assertEqual(self.check(cost_minor=101,operation_id="op.other").reason,"budget_exceeded")

    def test_denials(self):
        self.assertEqual(self.check(verified_requester="user.other").reason,"requester_or_grant_mismatch")
        self.assertEqual(self.check(scope="game.develop").reason,"scope_denied")
        self.assertEqual(self.check(target_id="game.other").reason,"target_denied")
        self.assertEqual(self.check(at="2026-10-31T14:00:00Z").reason,"outside_validity")
        self.assertEqual(self.check(cost_minor=-1).reason,"invalid_cost")
        self.assertEqual(self.check(cost_minor=1).reason,"operation_id_required")

    def test_operator_controls(self):
        self.assertFalse(self.engine.revoke(delegation_id="grant.01",verified_actor="user.other").allowed)
        self.assertFalse(self.engine.set_suspended(agent_id="agent.shared.01",verified_actor="user.other",suspended=True).allowed)
        self.assertEqual(self.engine.add_grant(self.grant,verified_actor="user.alice").reason,"duplicate_grant")


if __name__=="__main__":
    unittest.main()
