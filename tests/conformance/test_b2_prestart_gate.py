"""B2.2 pre-start authorization and claim fencing tests."""
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

    def test_requires_schema_v3(self):
        submission = self.service.submit(**self.args)
        self.assertTrue(submission.allowed)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        with self.assertRaisesRegex(ValueError, "schema v3"):
            PrestartGate(self.service).authorize(job_id=claim.job_id,
                worker_id="worker.one", claim_token=claim.claim_token)


if __name__ == "__main__":
    unittest.main()
