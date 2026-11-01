"""SEC-01 original-session reference checks; no external credentials/effects."""
import sys
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
import test_action_submission as fixture
from b2_worker import ClaimWorker
from b2_prestart import PrestartGate
from b2_prestart_schema import migrate_b2_prestart
from b2_dispatch_schema import migrate_b2_dispatch
from b2_dispatch import DispatchGate
from sec01_b2_intent_projection import project_committed_intent
from sec01_original_session_binding import (
    original_session_reference, verify_original_session_reference)

SECRET = b"test-only-issuer-secret-not-for-production-123"


class SEC01OriginalSessionBindingTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    issue = fixture.SubmissionTests.issue
    new_service = fixture.SubmissionTests.new_service
    query = fixture.SubmissionTests.query
    counts = fixture.SubmissionTests.counts

    def committed(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        migrate_b2_prestart(self.db)
        self.assertEqual(PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one",
            claim_token=claim.claim_token).state, "ready")
        migrate_b2_dispatch(self.db)
        result = DispatchGate(self.service, adapters={
            "game.feedback": ("fake.test", "1")}).commit_intent(
            job_id=claim.job_id, worker_id="worker.one",
            claim_token=claim.claim_token)
        self.assertEqual(result.state, "dispatch_committed")
        return project_committed_intent(self.db, job_id=job.job_id)

    def reference(self, intent):
        return original_session_reference(
            self.db, intent=intent, issuer_secret=SECRET, now=self.now)

    def verify(self, intent, reference):
        return verify_original_session_reference(
            self.db, intent=intent, issuer_secret=SECRET,
            expected_reference=reference, now=self.now)

    def test_original_session_reference_is_opaque_and_stable_after_restart(self):
        intent = self.committed()
        before = self.counts()
        reference = self.reference(intent)
        self.assertEqual(len(reference), 64)
        self.assertNotEqual(reference, self.query(
            "SELECT session_token_hash FROM action_jobs")[0][0])
        self.assertEqual(reference, self.reference(intent))
        self.new_service()
        self.assertEqual(self.verify(intent, reference).reason,
                         "original_session_bound_not_authenticated")
        self.assertEqual(self.counts(), before)

    def test_another_issued_session_cannot_replace_the_original(self):
        intent = self.committed()
        original = self.reference(intent)
        other = self.issue()
        from session_store import _digest
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE action_jobs SET session_token_hash=? WHERE job_id=?",
                       (_digest(other), intent.job_id))
            db.commit()
        self.assertEqual(self.verify(intent, original).reason,
                         "original_session_mismatch")

    def test_revoked_and_expired_original_session_fail_closed(self):
        intent = self.committed()
        reference = self.reference(intent)
        self.assertTrue(self.sessions.revoke(
            self.token, user_id="user.charlie", credential=self.credential))
        self.assertEqual(self.verify(intent, reference).reason,
                         "original_session_unavailable")

    def test_expiry_after_lookup_denies_new_validation(self):
        intent = self.committed()
        reference = self.reference(intent)
        self.now += 901
        self.assertEqual(self.verify(intent, reference).reason,
                         "original_session_unavailable")

    def test_wrong_secret_or_reference_is_rejected(self):
        intent = self.committed()
        reference = self.reference(intent)
        self.assertEqual(self.verify(intent, "0" * 64).reason,
                         "original_session_mismatch")
        result = verify_original_session_reference(
            self.db, intent=intent, issuer_secret=b"x" * 32,
            expected_reference=reference, now=self.now)
        self.assertEqual(result.reason, "original_session_mismatch")
        self.assertEqual(self.verify(intent, self.token).reason,
                         "invalid_session_reference")

    def test_uncommitted_job_and_malformed_context_denied(self):
        submission = self.service.submit(**self.args)
        self.assertTrue(submission.allowed)
        self.assertIsNone(project_committed_intent(
            self.db, job_id=submission.job_id))
        with self.assertRaises(ValueError):
            original_session_reference(
                self.db, intent=None, issuer_secret=SECRET, now=self.now)


if __name__ == "__main__":
    unittest.main()
