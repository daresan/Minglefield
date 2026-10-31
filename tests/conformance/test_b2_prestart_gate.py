"""B2.2 pre-start authorization and claim fencing tests."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import unittest

import test_action_submission as fixture
from b2_worker import ClaimWorker
from b2_prestart_schema import migrate_b2_prestart
from b2_prestart import PrestartGate


class PrestartGateTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    issue = fixture.SubmissionTests.issue
    new_service = fixture.SubmissionTests.new_service
    query = fixture.SubmissionTests.query
    counts = fixture.SubmissionTests.counts

    def claimed(self):
        submission = self.service.submit(**self.args)
        self.assertTrue(submission.allowed)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual(claim.state, "claimed")
        migrate_b2_prestart(self.db)
        return claim

    def test_valid_claim_becomes_ready_once_without_effect(self):
        claim = self.claimed()
        gate = PrestartGate(self.new_service())
        result = gate.authorize(job_id=claim.job_id, worker_id="worker.one",
                                claim_token=claim.claim_token)
        self.assertEqual(result.state, "ready")
        self.assertEqual(self.counts(), (1, 3, 100))
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("ready",)])
        again = gate.authorize(job_id=claim.job_id, worker_id="worker.one",
                               claim_token=claim.claim_token)
        self.assertEqual(again.state, "rejected")
        self.assertEqual(self.counts(), (1, 3, 100))

    def test_wrong_worker_and_token_do_not_change_job(self):
        claim = self.claimed()
        gate = PrestartGate(self.service)
        for worker, token in [("worker.other", claim.claim_token),
                              ("worker.one", "wrong")]:
            self.assertEqual(gate.authorize(job_id=claim.job_id, worker_id=worker,
                                            claim_token=token).state, "rejected")
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("claimed",)])
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_revoked_original_session_denies(self):
        claim = self.claimed()
        self.assertTrue(self.sessions.revoke(self.token, credential=self.credential, user_id='user.charlie'))
        result = PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        self.assertEqual(result.state, "denied")
        self.assertEqual(result.reason, "invalid_original_session")
        self.assertEqual(self.counts(), (1, 3, 100))

    def test_new_job_claimed_on_v3_and_authorized(self):
        first = self.service.submit(**self.args)
        self.assertTrue(first.allowed)
        ClaimWorker(self.service)  # legacy v1 -> v2
        migrate_b2_prestart(self.db)
        second = self.service.submit(**(self.args | {"idempotency_key": "request.2"}))
        self.assertTrue(second.allowed)
        worker = ClaimWorker(self.new_service())
        first_claim = worker.claim_next("worker.one")
        second_claim = worker.claim_next("worker.two")
        self.assertEqual((first_claim.state, second_claim.state), ("claimed", "claimed"))
        self.assertEqual({first_claim.job_id, second_claim.job_id},
                         {first.job_id, second.job_id})
        result = PrestartGate(self.new_service()).authorize(
            job_id=second_claim.job_id, worker_id="worker.two",
            claim_token=second_claim.claim_token)
        self.assertEqual(result.state, "ready")
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(3,)])
        self.assertEqual(self.counts(), (2, 5, 200))

    def test_requires_schema_v3(self):
        submission = self.service.submit(**self.args)
        self.assertTrue(submission.allowed)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        with self.assertRaisesRegex(ValueError, "schema v3"):
            PrestartGate(self.service).authorize(job_id=claim.job_id,
                worker_id="worker.one", claim_token=claim.claim_token)

    def test_revoked_grant_after_claim_denies(self):
        claim = self.claimed()
        self.assertTrue(self.policy.revoke(
            delegation_id="grant.01", verified_actor="user.alice").allowed)
        result = PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        self.assertEqual((result.state, result.reason), ("denied", "grant_revoked"))
        self.assertEqual(self.counts(), (1, 3, 100))

    def test_suspended_agent_after_claim_denies(self):
        claim = self.claimed()
        self.assertTrue(self.policy.set_suspended(
            agent_id=self.agent["agent_id"], verified_actor="user.alice",
            suspended=True).allowed)
        result = PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        self.assertEqual((result.state, result.reason), ("denied", "agent_suspended"))
        self.assertEqual(self.counts(), (1, 3, 100))

    def test_concurrent_gate_allows_exactly_one_transition(self):
        claim = self.claimed()
        gate = PrestartGate(self.service)
        def authorize(_):
            return gate.authorize(job_id=claim.job_id, worker_id="worker.one",
                                  claim_token=claim.claim_token)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(authorize, range(8)))
        self.assertEqual(sum(result.state == "ready" for result in results), 1)
        self.assertEqual(sum(result.state == "rejected" for result in results), 7)
        self.assertEqual(self.query(
            "SELECT COUNT(*) FROM action_audit WHERE event_type='job.ready'"), [(1,)])
        self.assertEqual(self.counts(), (1, 3, 100))

    def test_audit_failure_rolls_back_ready_transition(self):
        claim = self.claimed()
        db = sqlite3.connect(self.db)
        try:
            db.execute("""CREATE TRIGGER reject_ready_audit BEFORE INSERT ON action_audit
                WHEN NEW.event_type='job.ready'
                BEGIN SELECT RAISE(ABORT,'injected ready audit failure'); END""")
            db.commit()
        finally:
            db.close()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected ready audit failure"):
            PrestartGate(self.service).authorize(
                job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("claimed",)])
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_restart_preserves_claim_fencing(self):
        claim = self.claimed()
        restarted = PrestartGate(self.new_service())
        self.assertEqual(restarted.authorize(
            job_id=claim.job_id, worker_id="worker.other",
            claim_token=claim.claim_token).state, "rejected")
        self.assertEqual(restarted.authorize(
            job_id=claim.job_id, worker_id="worker.one",
            claim_token=claim.claim_token).state, "ready")
        self.assertEqual(self.counts(), (1, 3, 100))


if __name__ == "__main__":
    unittest.main()
