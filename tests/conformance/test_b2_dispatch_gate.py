"""B2.3b dispatch intent tests; no effects."""
import sqlite3
import json
import unittest
from contextlib import closing
import test_action_submission as fixture
from b2_worker import ClaimWorker
from b2_prestart import PrestartGate
from b2_prestart_schema import migrate_b2_prestart
from b2_dispatch_schema import migrate_b2_dispatch
from b2_dispatch import DispatchGate

class DispatchGateTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    issue = fixture.SubmissionTests.issue
    new_service = fixture.SubmissionTests.new_service
    query = fixture.SubmissionTests.query
    execute = fixture.SubmissionTests.execute
    counts = fixture.SubmissionTests.counts

    def prepare(self):
        job = self.service.submit(**self.args)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        migrate_b2_prestart(self.db)
        ready = PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        self.assertEqual(ready.state, "ready")
        migrate_b2_dispatch(self.db)
        return claim

    def dispatch(self, claim, **changes):
        args = dict(job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        return DispatchGate(self.new_service(), adapters={"game.feedback": ("fake.test", "1")}).commit_intent(
            **(args | changes))

 
    def test_corrupt_structural_records_after_ready_fail_closed(self):
        for table, column, mutation in (
                ("agents", "descriptor", lambda data: data.update({"operators": []})),
                ("grants", "grant_json", lambda data: data.update({"issuer_user_id": "bad id"})),
                ("action_jobs", "request_json", lambda data: data.update({"parameters": []}))):
            with self.subTest(table=table):
                self.setUp()
                claim = self.prepare()
                with closing(sqlite3.connect(self.db)) as db:
                    raw = db.execute(f"SELECT {column} FROM {table}").fetchone()[0]
                    data = json.loads(raw)
                    mutation(data)
                    db.execute(f"UPDATE {table} SET {column}=?", (json.dumps(data),))
                    db.commit()
                result = self.dispatch(claim)
                self.assertEqual((result.state, result.reason), ("denied", "invalid_policy"))
                self.assertEqual(self.query(
                    "SELECT state,effect_idempotency_key FROM action_jobs"),
                    [("denied", None)])
                self.assertEqual(self.counts(), (1, 4, 100))

    def test_commits_intent_once(self):
        claim = self.prepare()
        self.assertEqual(self.dispatch(claim).state, "dispatch_committed")
        self.assertEqual(self.dispatch(claim).state, "rejected")
        self.assertEqual(self.counts(), (1, 4, 100))
        row = self.query("SELECT effect_idempotency_key,adapter_id,adapter_version,dispatch_fingerprint,fingerprint FROM action_jobs")[0]
        self.assertTrue(row[0].startswith("effect."))
        self.assertEqual(row[1:3], ("fake.test", "1"))
        self.assertEqual(row[3], row[4])

    def test_wrong_claim_is_inert(self):
        claim = self.prepare()
        before = self.counts()
        self.assertEqual(self.dispatch(claim, claim_token="wrong").state, "rejected")
        self.assertEqual(self.dispatch(claim, worker_id="other").state, "rejected")
        self.assertEqual(self.counts(), before)

    def test_revoked_grant_denies(self):
        claim = self.prepare()
        self.policy.revoke(delegation_id="grant.01", verified_actor="user.alice")
        self.assertEqual(self.dispatch(claim).state, "denied")
        self.assertEqual(self.query("SELECT state,effect_idempotency_key FROM action_jobs"),
                         [("denied", None)])


    def test_parallel_dispatch_only_one_intent(self):
        from concurrent.futures import ThreadPoolExecutor
        claim = self.prepare()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.dispatch(claim), range(2)))
        self.assertEqual(sorted(result.state for result in results),
                         ["dispatch_committed", "rejected"])
        self.assertEqual(self.counts(), (1, 4, 100))

    def test_audit_write_failure_rolls_back_intent(self):
        import sqlite3
        claim = self.prepare()
        self.execute("""CREATE TRIGGER fail_dispatch_audit BEFORE INSERT ON action_audit
            WHEN NEW.event_type='job.dispatch_committed'
            BEGIN SELECT RAISE(ABORT, 'injected'); END""")
        before = self.counts()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected"):
            self.dispatch(claim)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.query("SELECT state,effect_idempotency_key FROM action_jobs"),
                         [("ready", None)])

    def test_revoked_original_session_denies(self):
        claim = self.prepare()
        self.assertTrue(self.sessions.revoke(
            self.token, user_id="user.charlie", credential=self.credential))
        self.assertEqual(self.dispatch(claim).state, "denied")
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("denied",)])

    def test_expired_original_session_denies(self):
        claim = self.prepare()
        self.now += 901
        self.assertEqual(self.dispatch(claim).state, "denied")
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("denied",)])

    def test_suspended_agent_denies(self):
        claim = self.prepare()
        self.assertTrue(self.policy.set_suspended(
            agent_id=self.agent["agent_id"], verified_actor="user.alice",
            suspended=True).allowed)
        self.assertEqual(self.dispatch(claim).state, "denied")
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("denied",)])

    def test_action_rule_change_denies(self):
        from action_service import ActionRule
        claim = self.prepare()
        self.actions["game.feedback"] = ActionRule("game.other", 100, "price.2")
        self.assertEqual(self.dispatch(claim).state, "denied")
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("denied",)])

    def test_request_fingerprint_tampering_denies(self):
        claim = self.prepare()
        self.execute("UPDATE action_jobs SET fingerprint='tampered' WHERE state='ready'")
        result = self.dispatch(claim)
        self.assertEqual((result.state, result.reason),
                         ("denied", "invalid_dispatch_binding"))
        self.assertEqual(self.query("SELECT state,effect_idempotency_key FROM action_jobs"),
                         [("denied", None)])

    def test_unconfigured_adapter_denies(self):
        claim = self.prepare()
        result = DispatchGate(self.new_service(), adapters={}).commit_intent(
            job_id=claim.job_id, worker_id="worker.one",
            claim_token=claim.claim_token)
        self.assertEqual(result.state, "denied")
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("denied",)])

    def test_invalid_adapter_configuration_rejected(self):
        with self.assertRaises(ValueError):
            DispatchGate(self.service, adapters={"game.feedback": ("", "1")})


    def test_malformed_session_expiry_denies_without_intent(self):
        claim = self.prepare()
        self.execute("UPDATE auth_sessions SET expires_at='invalid-expiry'")
        result = self.dispatch(claim)
        self.assertEqual((result.state, result.reason),
                         ("denied", "invalid_original_session"))
        self.assertEqual(self.query(
            "SELECT state,effect_idempotency_key,adapter_id,dispatched_at FROM action_jobs"),
            [("denied", None, None, None)])
        self.assertEqual(self.counts(), (1, 4, 100))

    def test_malformed_grant_json_denies_without_intent(self):
        claim = self.prepare()
        self.execute("UPDATE grants SET grant_json='not json'")
        result = self.dispatch(claim)
        self.assertEqual((result.state, result.reason), ("denied", "invalid_policy"))
        self.assertEqual(self.query(
            "SELECT state,effect_idempotency_key,dispatch_fingerprint FROM action_jobs"),
            [("denied", None, None)])
        self.assertEqual(self.counts(), (1, 4, 100))


    def test_corrupt_delegation_after_ready_denies_dispatch(self):
        claim = self.prepare()
        import json
        with closing(sqlite3.connect(self.db)) as db:
            grant = json.loads(db.execute("SELECT grant_json FROM grants").fetchone()[0])
            grant["delegation_id"] = "grant.other"
            db.execute("UPDATE grants SET grant_json=?", (json.dumps(grant),))
            db.commit()
        result = self.dispatch(claim)
        self.assertEqual((result.state, result.reason), ("denied", "invalid_policy"))
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("denied",)])
        self.assertEqual(self.counts(), (1, 4, 100))
        self.assertEqual(self.query("SELECT effect_idempotency_key FROM action_jobs"), [(None,)])


    def test_adapter_configuration_is_immutable_snapshot(self):
        adapters = {"game.feedback": ("fake.test", "1")}
        gate = DispatchGate(self.service, adapters=adapters)
        adapters["game.feedback"] = ("fake.changed", "2")
        self.assertEqual(gate.adapters["game.feedback"], ("fake.test", "1"))
        with self.assertRaises(TypeError):
            gate.adapters["game.feedback"] = ("fake.changed", "2")
        claim = self.prepare()
        result = gate.commit_intent(job_id=claim.job_id, worker_id="worker.one",
                                    claim_token=claim.claim_token)
        self.assertEqual(result.state, "dispatch_committed")
        self.assertEqual(self.query("SELECT adapter_id,adapter_version FROM action_jobs"),
                         [("fake.test", "1")])
        self.assertEqual(self.counts(), (1, 4, 100))

    def test_bad_claim_preserves_all_dispatch_fields_and_budget(self):
        claim = self.prepare()
        before = self.counts()
        result = self.dispatch(claim, claim_token="bad")
        self.assertEqual(result.state, "rejected")
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.query("""SELECT state,effect_idempotency_key,
            dispatch_fingerprint,adapter_id,adapter_version,dispatched_at
            FROM action_jobs"""), [("ready", None, None, None, None, None)])
