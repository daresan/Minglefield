"""B2.3b prerequisite: existing B1/B2 operations on explicitly migrated v4."""
import unittest

import test_action_submission as fixture
from b2_worker import ClaimWorker
from b2_prestart import PrestartGate
from b2_prestart_schema import migrate_b2_prestart
from b2_dispatch_schema import migrate_b2_dispatch


class V4CompatibilityTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    issue = fixture.SubmissionTests.issue
    new_service = fixture.SubmissionTests.new_service
    query = fixture.SubmissionTests.query
    counts = fixture.SubmissionTests.counts

    def migrate(self):
        ClaimWorker(self.service)
        migrate_b2_prestart(self.db)
        migrate_b2_dispatch(self.db)

    def test_v4_submit_replay_claim_and_ready(self):
        self.migrate()
        service = self.new_service()
        first = service.submit(**self.args)
        self.assertTrue(first.allowed)
        replay = service.submit(**self.args)
        self.assertEqual(replay.job_id, first.job_id)
        claim = ClaimWorker(service).claim_next("worker.one")
        self.assertEqual(claim.state, "claimed")
        self.assertEqual(claim.job_id, first.job_id)
        ready = PrestartGate(service).authorize(
            job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        self.assertEqual(ready.state, "ready")
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("ready",)])
        self.assertEqual(self.counts(), (1, 3, 100))
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_v4_preserves_existing_ready_and_accepts_new_job(self):
        first = self.service.submit(**self.args)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        migrate_b2_prestart(self.db)
        ready = PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        self.assertEqual(ready.state, "ready")
        migrate_b2_dispatch(self.db)
        service = self.new_service()
        second = service.submit(**(self.args | {"idempotency_key": "request.2"}))
        self.assertTrue(second.allowed)
        self.assertEqual(ClaimWorker(service).claim_next("worker.two").job_id, second.job_id)
        self.assertEqual(dict(self.query("SELECT job_id,state FROM action_jobs")),
                         {first.job_id: "ready", second.job_id: "claimed"})
        self.assertEqual(self.counts(), (2, 5, 200))

    def test_v4_rejects_bad_claim_without_mutation(self):
        self.migrate()
        job = self.new_service().submit(**self.args)
        claim = ClaimWorker(self.new_service()).claim_next("worker.one")
        before = self.counts()
        rejected = PrestartGate(self.new_service()).authorize(
            job_id=job.job_id, worker_id="worker.one", claim_token="incorrect")
        self.assertEqual(rejected.state, "rejected")
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("claimed",)])


if __name__ == "__main__":
    unittest.main()
