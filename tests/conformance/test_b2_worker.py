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


if __name__ == "__main__":
    unittest.main()
