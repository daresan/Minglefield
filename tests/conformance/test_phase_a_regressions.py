"""Phase A fixes and executable P1 regression reproductions.

Security properties are enforced as regular regression tests.
"""
import copy
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from sys import path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
path.insert(0, str(ROOT / "server"))
from action_gateway import ActionGateway
from policy_engine import PolicyEngine
from session_store import SessionStore
from sqlite_policy_engine import SQLitePolicyEngine


class PhaseARegressions(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "security.sqlite"
        examples = ROOT / "examples/map/v0.1"
        self.agent = json.loads((examples / "shared-agent.json").read_text())
        self.grant = json.loads((examples / "delegation-grant.json").read_text())
        self.policy = SQLitePolicyEngine(self.db)
        self.assertTrue(self.policy.register_agent(self.agent).allowed)
        self.memory = PolicyEngine(copy.deepcopy(self.agent))
        for engine in (self.policy, self.memory):
            self.assertTrue(engine.add_grant(copy.deepcopy(self.grant),
                                            verified_actor="user.alice").allowed)
        now = datetime(2026, 10, 31, 12, 15, tzinfo=timezone.utc).timestamp()
        self.sessions = SessionStore(self.db, clock=lambda: now)
        self.credential = self.sessions.enroll("user.charlie")
        self.token = self.issue("agent.shared.01")
        self.args = dict(verified_requester="user.charlie", delegation_id="grant.01",
                         scope="game.test_feedback", target_id="game.maze",
                         at="2026-10-31T12:15:00Z")

    def issue(self, agent_id):
        return self.sessions.issue(user_id="user.charlie", credential=self.credential,
                                   agent_id=agent_id, delegation_id="grant.01")

    def gateway_args(self, token, agent_id="agent.shared.01"):
        return dict(token=token, agent_id=agent_id, delegation_id="grant.01",
                    scope="game.test_feedback", target_id="game.maze",
                    cost_minor=200, operation_id="op.binding")

    def test_gateway_rejects_false_agent_binding_without_reserving(self):
        other = copy.deepcopy(self.agent)
        other["agent_id"] = "agent.other"
        self.assertTrue(self.policy.register_agent(other).allowed)
        gateway = ActionGateway(self.sessions, SQLitePolicyEngine(self.db))
        for agent_id in ("agent.unregistered", "agent.other"):
            with self.subTest(agent_id=agent_id):
                result = gateway.authorize(**self.gateway_args(self.issue(agent_id), agent_id))
                self.assertFalse(result.allowed)
                self.assertEqual(result.reason, "agent_delegation_mismatch")
        # Rejected requests must not reserve budget or poison the operation key.
        self.assertEqual(gateway.authorize(**self.gateway_args(self.token)).reason, "allowed")

    def test_persisted_agent_binding_checked_on_idempotent_retry(self):
        args = self.args | dict(cost_minor=200, operation_id="retry")
        self.assertTrue(self.policy.authorize(**args, expected_agent_id="agent.shared.01").allowed)
        result = SQLitePolicyEngine(self.db).authorize(**args, expected_agent_id="agent.other")
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "agent_delegation_mismatch")

    def test_empty_paid_operation_ids_rejected_by_both_engines(self):
        for engine in (self.memory, self.policy):
            for operation_id in (None, ""):
                with self.subTest(engine=type(engine).__name__, operation_id=operation_id):
                    result = engine.authorize(**self.args, cost_minor=200, operation_id=operation_id)
                    self.assertFalse(result.allowed)
                    self.assertEqual(result.reason, "operation_id_required")
            self.assertTrue(engine.authorize(**self.args, cost_minor=200, operation_id="valid").allowed)

    def test_invalid_cost_types_do_not_reserve_or_deduplicate(self):
        for engine in (self.memory, self.policy):
            for cost in (True, False, 1.0, "1", None, [], {}, -1):
                with self.subTest(engine=type(engine).__name__, cost=repr(cost)):
                    result = engine.authorize(**self.args, cost_minor=cost, operation_id="cost")
                    self.assertFalse(result.allowed)
                    self.assertEqual(result.reason, "invalid_cost")
            self.assertTrue(engine.authorize(**self.args, cost_minor=200, operation_id="cost").allowed)

    def test_zero_cost_optional_and_empty_ids_remain_compatible(self):
        for engine in (self.memory, self.policy):
            for operation_id in (None, ""):
                with self.subTest(engine=type(engine).__name__, operation_id=operation_id):
                    self.assertTrue(engine.authorize(**self.args, operation_id=operation_id).allowed)

    def test_known_p1_revocation_between_verify_and_policy_must_deny(self):
        original = self.sessions.verify

        def verify_then_revoke(*args, **kwargs):
            session = original(*args, **kwargs)
            self.assertIsNotNone(session)
            self.assertTrue(self.sessions.revoke(self.token, user_id="user.charlie",
                                                 credential=self.credential))
            return session

        with patch.object(self.sessions, "verify", side_effect=verify_then_revoke):
            result = ActionGateway(self.sessions, self.policy).authorize(**self.gateway_args(self.token))
        self.assertIsNone(original(self.token))
        self.assertFalse(result.allowed, "revoked session must not reserve")
        self.assertEqual(result.reason, "invalid_session")
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT spent_minor FROM grants WHERE delegation_id='grant.01'"
            ).fetchone()[0], 0)
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM operations WHERE operation_id='op.binding'"
            ).fetchone()[0], 0)

    def reserve_across_grants(self, engine):
        for index in range(6):
            grant = copy.deepcopy(self.grant)
            grant["delegation_id"] = "budget." + str(index)
            self.assertTrue(engine.add_grant(grant, verified_actor="user.alice").allowed)
            engine.authorize(**(self.args | dict(delegation_id=grant["delegation_id"])),
                             cost_minor=200, operation_id="budget")

    def test_known_p1_sqlite_agent_budget_must_cover_all_grants(self):
        self.reserve_across_grants(self.policy)
        db = sqlite3.connect(self.db)
        try:
            total = db.execute("SELECT SUM(spent_minor) FROM grants WHERE agent_id=?",
                               (self.agent["agent_id"],)).fetchone()[0]
        finally:
            db.close()
        self.assertLessEqual(total, self.agent["policy"]["max_spend_minor"],
                             "P1: agent cap is currently applied separately per grant")

    def test_known_p1_memory_agent_budget_must_cover_all_grants(self):
        self.reserve_across_grants(self.memory)
        self.assertLessEqual(sum(self.memory.spent.values()),
                             self.agent["policy"]["max_spend_minor"])
