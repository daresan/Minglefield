"""B2.1 claim-only worker tests."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import unittest

import test_action_submission as fixture
from b2_worker import ClaimWorker


class WorkerClaimTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    issue = fixture.SubmissionTests.issue
    new_service = fixture.SubmissionTests.new_service
    query = fixture.SubmissionTests.query
    counts = fixture.SubmissionTests.counts

    def test_claim_is_atomic_and_never_reclaimed(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        worker = ClaimWorker(self.service)
        result = worker.claim_next("worker.one")
        self.assertEqual(result.state, "claimed")
        self.assertEqual(result.job_id, job.job_id)
        self.assertTrue(result.claim_token)
        self.assertEqual(worker.claim_next("worker.two").state, "empty")
        self.assertEqual(self.query("SELECT state,claimed_by FROM action_jobs"),
                         [("claimed", "worker.one")])
        self.assertEqual(self.query("SELECT event_type FROM action_audit ORDER BY created_at,event_type"),
                         [("job.claimed",), ("job.queued",)])
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_revoked_session_denies_and_keeps_reservation(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        self.assertTrue(self.sessions.revoke(self.token, user_id="user.charlie",
                                             credential=self.credential))
        result = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual((result.state, result.reason),
                         ("denied", "invalid_original_session"))
        self.assertIsNone(result.claim_token)
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_missing_legacy_binding_denied(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        db = sqlite3.connect(self.db)
        try:
            db.execute("UPDATE action_jobs SET session_token_hash=NULL")
            db.commit()
        finally:
            db.close()
        result = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual((result.state, result.reason),
                         ("denied", "missing_original_session"))

    def test_concurrent_workers_claim_one_job_once(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        worker = ClaimWorker(self.service)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(worker.claim_next, [f"worker.{i}" for i in range(8)]))
        self.assertEqual(sum(r.state == "claimed" for r in results), 1)
        self.assertEqual(sum(r.state == "empty" for r in results), 7)
        self.assertEqual(self.query("SELECT COUNT(*) FROM action_audit WHERE event_type='job.claimed'"),
                         [(1,)])
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_audit_insert_failure_rolls_back_claim(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        worker = ClaimWorker(self.service)
        db = sqlite3.connect(self.db)
        try:
            db.execute("""CREATE TRIGGER reject_claim_audit BEFORE INSERT ON action_audit
                WHEN NEW.event_type='job.claimed'
                BEGIN SELECT RAISE(ABORT,'injected audit failure'); END""")
            db.commit()
        finally:
            db.close()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected audit failure"):
            worker.claim_next("worker.one")
        self.assertEqual(self.query("SELECT state,claimed_by,claim_token_hash FROM action_jobs"),
                         [("queued", None, None)])
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_job_update_failure_rolls_back_claim(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        worker = ClaimWorker(self.service)
        db = sqlite3.connect(self.db)
        try:
            db.execute("""CREATE TRIGGER reject_claim_update BEFORE UPDATE ON action_jobs
                WHEN NEW.state='claimed'
                BEGIN SELECT RAISE(ABORT,'injected claim failure'); END""")
            db.commit()
        finally:
            db.close()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected claim failure"):
            worker.claim_next("worker.one")
        self.assertEqual(self.query("SELECT state,claimed_by,claim_token_hash FROM action_jobs"),
                         [("queued", None, None)])
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_worker_restart_does_not_reclaim(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        first = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual(first.state, "claimed")
        restarted = ClaimWorker(self.new_service())
        self.assertEqual(restarted.claim_next("worker.two").state, "empty")
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_revoked_grant_denies_claim(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        self.assertTrue(self.policy.revoke(
            delegation_id="grant.01", verified_actor="user.alice").allowed)
        result = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual((result.state, result.reason), ("denied", "grant_revoked"))
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_suspended_agent_denies_claim(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        self.assertTrue(self.policy.set_suspended(
            agent_id=self.agent["agent_id"], verified_actor="user.alice",
            suspended=True).allowed)
        result = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual((result.state, result.reason), ("denied", "agent_suspended"))
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_expired_original_session_denies_even_with_new_session(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        replacement = self.issue()
        self.assertNotEqual(replacement, self.token)
        self.now += 901
        result = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual((result.state, result.reason), ("denied", "invalid_original_session"))
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_removed_action_rule_denies_claim(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        self.actions.clear()
        result = ClaimWorker(self.new_service()).claim_next("worker.one")
        self.assertEqual((result.state, result.reason), ("denied", "action_rule_changed"))
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_fifo_claim_order_by_created_at_then_job_id(self):
        first = self.service.submit(**self.args)
        second = self.service.submit(**(self.args | {"idempotency_key": "request.2"}))
        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        # Deterministic timestamps make the documented job_id tie-breaker testable.
        db = sqlite3.connect(self.db)
        try:
            db.execute("UPDATE action_jobs SET created_at=? WHERE job_id=?", (self.now - 2, first.job_id))
            db.execute("UPDATE action_jobs SET created_at=? WHERE job_id=?", (self.now - 1, second.job_id))
            db.commit()
        finally:
            db.close()
        worker = ClaimWorker(self.service)
        self.assertEqual(worker.claim_next("worker.one").job_id, first.job_id)
        self.assertEqual(worker.claim_next("worker.two").job_id, second.job_id)
        self.assertEqual(worker.claim_next("worker.three").state, "empty")

    def test_fifo_equal_timestamps_use_job_id_tiebreaker(self):
        first = self.service.submit(**self.args)
        second = self.service.submit(**(self.args | {"idempotency_key": "request.2"}))
        self.assertTrue(first.allowed)
        self.assertTrue(second.allowed)
        db = sqlite3.connect(self.db)
        try:
            db.execute("UPDATE action_jobs SET created_at=?", (self.now,))
            db.commit()
        finally:
            db.close()
        expected = sorted((first.job_id, second.job_id))
        worker = ClaimWorker(self.service)
        actual = [worker.claim_next(f"worker.{i}").job_id for i in range(2)]
        self.assertEqual(actual, expected)
        self.assertEqual(worker.claim_next("worker.last").state, "empty")
        self.assertEqual(self.counts(), (2, 4, 200))


if __name__ == "__main__":
    unittest.main()
