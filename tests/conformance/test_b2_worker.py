"""B2.1 claim-only worker tests."""
import sqlite3
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


if __name__ == "__main__":
    unittest.main()
