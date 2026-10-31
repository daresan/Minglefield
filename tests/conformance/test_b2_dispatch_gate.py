"""B2.3b dispatch intent tests; no effects."""
import unittest
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
