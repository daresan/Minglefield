"""B1 atomic submission invariants; no external effects or worker simulation."""
import copy
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from sys import path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
path.insert(0, str(ROOT / "server"))
from action_service import ActionService, ActionRule
from session_store import SessionStore
from sqlite_policy_engine import SQLitePolicyEngine


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "submit.sqlite"
        self.now = datetime(2026, 10, 31, 12, 15, tzinfo=timezone.utc).timestamp()
        self.policy = SQLitePolicyEngine(self.db)
        self.sessions = SessionStore(self.db, clock=lambda: self.now)
        examples = ROOT / "examples/map/v0.1"
        self.agent = json.loads((examples / "shared-agent.json").read_text())
        self.grant = json.loads((examples / "delegation-grant.json").read_text())
        self.assertTrue(self.policy.register_agent(self.agent).allowed)
        self.assertTrue(self.policy.add_grant(self.grant, verified_actor="user.alice").allowed)
        self.credential = self.sessions.enroll("user.charlie")
        self.token = self.issue()
        self.actions = {"game.feedback": ActionRule("game.test_feedback", 100, "price.1")}
        self.service = self.new_service()
        self.args = dict(token=self.token, agent_id=self.agent["agent_id"],
                         delegation_id="grant.01", target_id="game.maze",
                         action_type="game.feedback", parameters={"text": "hello"},
                         idempotency_key="request.1")

    def issue(self, **changes):
        return self.sessions.issue(**(dict(user_id="user.charlie", credential=self.credential,
            agent_id=self.agent["agent_id"], delegation_id="grant.01") | changes))

    def new_service(self):
        return ActionService(self.db, actions=self.actions, clock=lambda: self.now)

    def query(self, sql, params=()):
        db = sqlite3.connect(self.db)
        try:
            return db.execute(sql, params).fetchall()
        finally:
            db.close()

    def execute(self, sql):
        db = sqlite3.connect(self.db)
        try:
            db.execute(sql)
            db.commit()
        finally:
            db.close()

    def counts(self):
        return tuple(self.query(sql)[0][0] for sql in (
            "SELECT COUNT(*) FROM action_jobs", "SELECT COUNT(*) FROM action_audit",
            "SELECT SUM(spent_minor) FROM grants"))

    def legacy_reserve(self, key="legacy", cost=100):
        return self.policy.authorize(verified_requester="user.charlie", delegation_id="grant.01",
            scope="game.test_feedback", target_id="game.maze", at="2026-10-31T12:15:00Z",
            cost_minor=cost, operation_id=key)

    def test_parallel_identical_submissions_one_job_reservation_and_event(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.new_service().submit(**self.args), range(20)))
        self.assertTrue(all(r.allowed for r in results))
        self.assertEqual(len({r.job_id for r in results}), 1)
        self.assertEqual(sum(r.reason == "queued" for r in results), 1)
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_parallel_distinct_submissions_respect_grant_limit(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: self.service.submit(**(self.args |
                dict(idempotency_key=str(i)))), range(20)))
        self.assertEqual(sum(r.allowed for r in results), 2)
        self.assertTrue(all(r.allowed or r.reason == "budget_exceeded" for r in results))
        self.assertEqual(self.counts(), (2, 2, 200))

    def test_parallel_agent_limit_across_delegations(self):
        requests = []
        for index in range(15):
            grant = copy.deepcopy(self.grant)
            grant["delegation_id"] = "grant." + str(index + 10)
            self.assertTrue(self.policy.add_grant(grant, verified_actor="user.alice").allowed)
            requests.append(self.args | dict(delegation_id=grant["delegation_id"],
                token=self.issue(delegation_id=grant["delegation_id"])))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda args: self.service.submit(**args), requests))
        self.assertEqual(sum(r.allowed for r in results), 10)
        self.assertTrue(all(r.allowed or r.reason == "budget_exceeded" for r in results))
        self.assertEqual(self.counts(), (10, 10, 1000))

    def test_revoked_session_before_begin_denied(self):
        self.assertTrue(self.sessions.revoke(self.token, user_id="user.charlie", credential=self.credential))
        self.assertEqual(self.service.submit(**self.args).reason, "invalid_session")
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_false_agent_binding_denied(self):
        token = self.issue(agent_id="agent.other")
        result = self.service.submit(**(self.args | dict(token=token, agent_id="agent.other")))
        self.assertEqual(result.reason, "agent_delegation_mismatch")
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_invalid_session_bindings_and_requester(self):
        other_credential = self.sessions.enroll("user.other")
        other_token = self.sessions.issue(user_id="user.other", credential=other_credential,
            agent_id=self.agent["agent_id"], delegation_id="grant.01")
        for change, reason in ((dict(token="bad"), "invalid_session"),
            (dict(delegation_id="other"), "invalid_session"),
            (dict(agent_id="other"), "invalid_session"),
            (dict(token=other_token), "requester_or_grant_mismatch")):
            with self.subTest(change=change):
                self.assertEqual(self.service.submit(**(self.args | change)).reason, reason)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_disabled_user_and_session_expiry(self):
        self.now += 900
        self.assertEqual(self.service.submit(**self.args).reason, "invalid_session")
        self.now -= 900
        self.assertTrue(self.sessions.disable_user("user.charlie", credential=self.credential))
        self.assertEqual(self.service.submit(**self.args).reason, "invalid_session")
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_grant_expiry_uses_server_time_with_fresh_session(self):
        self.now = datetime(2026, 10, 31, 14, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(self.service.submit(**(self.args | dict(token=self.issue()))).reason, "outside_validity")
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_policy_denials_and_replay_reauthorization(self):
        self.assertEqual(self.service.submit(**(self.args | dict(target_id="other"))).reason, "target_denied")
        self.assertEqual(self.service.submit(**(self.args | dict(action_type="unknown"))).reason, "unknown_action")
        self.assertTrue(self.service.submit(**self.args).allowed)
        self.assertTrue(self.policy.set_suspended(agent_id=self.agent["agent_id"],
                                                verified_actor="user.alice", suspended=True).allowed)
        self.assertEqual(self.service.submit(**self.args).reason, "agent_suspended")
        self.policy.set_suspended(agent_id=self.agent["agent_id"], verified_actor="user.alice", suspended=False)
        self.policy.revoke(delegation_id="grant.01", verified_actor="user.alice")
        self.assertEqual(self.service.submit(**self.args).reason, "grant_revoked")
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_scope_denied(self):
        service = ActionService(self.db, actions={"game.feedback": ActionRule("game.develop", 1, "1")},
                                clock=lambda: self.now)
        self.assertEqual(service.submit(**self.args).reason, "scope_denied")
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_rollback_at_each_write_boundary(self):
        for table, operation in (("grants", "UPDATE"), ("action_jobs", "INSERT"), ("action_audit", "INSERT")):
            with self.subTest(table=table):
                self.execute(f"CREATE TRIGGER fail_write AFTER {operation} ON {table} "
                             "BEGIN SELECT RAISE(ABORT, 'injected'); END")
                try:
                    with self.assertRaisesRegex(sqlite3.IntegrityError, "injected"):
                        self.service.submit(**self.args)
                    self.assertEqual(self.counts(), (0, 0, 0))
                finally:
                    self.execute("DROP TRIGGER fail_write")
        self.assertTrue(self.service.submit(**self.args).allowed)

    def test_restart_and_token_rotation_preserve_job(self):
        first = self.service.submit(**self.args)
        self.sessions.revoke(self.token, user_id="user.charlie", credential=self.credential)
        result = self.new_service().submit(**(self.args | dict(token=self.issue())))
        self.assertTrue(result.allowed)
        self.assertEqual(result.job_id, first.job_id)
        self.assertEqual(result.reason, "already_queued")
        self.assertEqual(self.counts(), (1, 1, 100))
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("queued",)])

    def test_canonical_payload_and_conflicts(self):
        args = self.args | dict(parameters={"a": 1, "b": {"x": True, "y": [1, 2]}})
        first = self.service.submit(**args)
        same = self.service.submit(**(args | dict(parameters={"b": {"y": [1, 2], "x": True}, "a": 1})))
        self.assertEqual(first.job_id, same.job_id)
        for params in ({"a": 2}, {"a": 1.0, "b": {"x": True, "y": [1, 2]}},
                       {"a": 1, "b": {"x": True, "y": [2, 1]}}):
            with self.subTest(params=params):
                self.assertEqual(self.service.submit(**(args | dict(parameters=params))).reason, "idempotency_conflict")
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_action_type_in_fingerprint(self):
        self.actions["game.other"] = self.actions["game.feedback"]
        service = self.new_service()
        self.assertTrue(service.submit(**self.args).allowed)
        self.assertEqual(service.submit(**(self.args | dict(action_type="game.other"))).reason, "idempotency_conflict")

    def test_prices_are_server_configured_and_retries_keep_original_price(self):
        with self.assertRaises(TypeError):
            self.service.submit(**self.args, cost_minor=0)
        with self.assertRaises(TypeError):
            self.service.submit(**self.args, at="2026-10-31T12:15:00Z")
        self.assertTrue(self.service.submit(**self.args).allowed)
        self.actions["game.feedback"] = ActionRule("game.test_feedback", 200, "price.2")
        self.assertEqual(self.new_service().submit(**self.args).reason, "already_queued")
        self.assertEqual(self.query("SELECT cost_minor,pricing_revision FROM action_jobs"), [(100, "price.1")])

    def test_legacy_reservations_preserved_and_not_promoted(self):
        self.assertTrue(self.legacy_reserve().allowed)
        before = self.query("SELECT * FROM operations")
        self.new_service()
        self.assertEqual(self.counts(), (0, 0, 100))
        self.assertEqual(self.query("SELECT * FROM operations"), before)
        self.assertEqual(self.service.submit(**(self.args | dict(idempotency_key="legacy"))).reason,
                         "legacy_operation_conflict")
        self.assertTrue(self.service.submit(**self.args).allowed)
        self.assertEqual(self.service.submit(**(self.args | dict(idempotency_key="another"))).reason, "budget_exceeded")
        self.assertEqual(self.counts(), (1, 1, 200))

    def test_legacy_cross_grant_reservations_count_toward_agent_cap(self):
        self.assertTrue(self.legacy_reserve(cost=200).allowed)
        for i in range(4):
            grant = copy.deepcopy(self.grant)
            grant["delegation_id"] = "legacy." + str(i)
            self.policy.add_grant(grant, verified_actor="user.alice")
            self.assertTrue(self.policy.authorize(verified_requester="user.charlie",
                delegation_id=grant["delegation_id"], scope="game.test_feedback", target_id="game.maze",
                at="2026-10-31T12:15:00Z", cost_minor=200, operation_id="old").allowed)
        grant = copy.deepcopy(self.grant)
        grant["delegation_id"] = "new"
        self.policy.add_grant(grant, verified_actor="user.alice")
        self.assertEqual(self.new_service().submit(**(self.args | dict(delegation_id="new",
            token=self.issue(delegation_id="new")))).reason, "budget_exceeded")
        self.assertEqual(self.counts(), (0, 0, 1000))

    def test_invalid_json_and_keys_leave_no_state(self):
        for params in ({"x": float("nan")}, {"x": float("inf")}, {1: "bad"}, {"x": (1, 2)}, []):
            with self.subTest(params=params):
                self.assertEqual(self.service.submit(**(self.args | dict(parameters=params))).reason, "invalid_request")
        self.assertEqual(self.service.submit(**(self.args | dict(idempotency_key=""))).reason, "invalid_request")
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_no_legacy_transaction_methods_used_by_submit(self):
        with patch.object(SessionStore, "verify", side_effect=AssertionError("separate session tx")), \
             patch.object(SQLitePolicyEngine, "authorize", side_effect=AssertionError("separate policy tx")):
            self.assertTrue(self.service.submit(**self.args).allowed)

    def test_queue_only_constraint_and_unknown_schema_version(self):
        self.assertTrue(self.service.submit(**self.args).allowed)
        with self.assertRaises(sqlite3.IntegrityError):
            self.execute("UPDATE action_jobs SET state='running'")
        self.execute("UPDATE action_schema SET version=2")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.new_service()
        self.assertEqual(self.counts(), (1, 1, 100))
