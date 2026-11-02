"""SEC-01 read-only B2 intent projection tests; no effect admission."""
import sqlite3
import sys
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
import test_action_submission as fixture
from b2_worker import ClaimWorker
from b2_prestart import PrestartGate
from b2_prestart_schema import migrate_b2_prestart
from b2_dispatch_schema import migrate_b2_dispatch
from b2_dispatch import DispatchGate
from sec01_b2_intent_projection import project_committed_intent


class SEC01IntentProjectionTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    issue = fixture.SubmissionTests.issue
    new_service = fixture.SubmissionTests.new_service
    query = fixture.SubmissionTests.query
    counts = fixture.SubmissionTests.counts

    def ready(self):
        submission = self.service.submit(**self.args)
        self.assertTrue(submission.allowed)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual(claim.state, "claimed")
        migrate_b2_prestart(self.db)
        result = PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one",
            claim_token=claim.claim_token)
        self.assertEqual(result.state, "ready")
        migrate_b2_dispatch(self.db)
        return claim

    def committed(self):
        claim = self.ready()
        result = DispatchGate(self.service, adapters={
            "game.feedback": ("fake.test", "1")}).commit_intent(
                job_id=claim.job_id, worker_id="worker.one",
                claim_token=claim.claim_token)
        self.assertEqual(result.state, "dispatch_committed")
        return claim.job_id

    def test_projection_is_frozen_and_contains_only_whitelisted_fields(self):
        job_id = self.committed()
        before = self.counts()
        projection = project_committed_intent(self.db, job_id=job_id)
        self.assertEqual(projection.job_id, job_id)
        self.assertEqual(projection.action_type, "game.feedback")
        self.assertEqual((projection.adapter_id, projection.adapter_version),
                         ("fake.test", "1"))
        self.assertEqual(projection.contract_version, 1)
        self.assertEqual(self.query("SELECT fingerprint FROM action_jobs"),
                         [(projection.request_fingerprint,)])
        names = {field.name for field in fields(projection)}
        self.assertFalse({"session_token_hash", "claim_token_hash", "token",
                          "parameters", "request_json", "claimed_by"} & names)
        with self.assertRaises(FrozenInstanceError):
            projection.target_id = "tampered"
        self.assertEqual(self.counts(), before)

    def test_uncommitted_and_unknown_jobs_have_no_projection(self):
        claim = self.ready()
        self.assertIsNone(project_committed_intent(self.db, job_id=claim.job_id))
        self.assertIsNone(project_committed_intent(self.db, job_id="job.unknown"))
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("ready",)])

    def test_invalid_input_is_rejected(self):
        self.committed()
        for job_id in (None, "", 123, "x" * 129):
            with self.subTest(job_id=job_id):
                with self.assertRaises(ValueError):
                    project_committed_intent(self.db, job_id=job_id)

    def test_fingerprint_mutation_fails_closed_without_job_update(self):
        job_id = self.committed()
        before = self.counts()
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE action_jobs SET dispatch_fingerprint=? WHERE job_id=?",
                       ("0" * 64, job_id))
            db.commit()
        with self.assertRaisesRegex(ValueError, "invalid committed intent"):
            project_committed_intent(self.db, job_id=job_id)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.query("SELECT state FROM action_jobs"),
                         [("dispatch_committed",)])

    def test_binding_mutation_fails_closed(self):
        job_id = self.committed()
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE action_jobs SET user_id=? WHERE job_id=?",
                       ("user.alice", job_id))
            db.commit()
        with self.assertRaisesRegex(ValueError, "invalid committed intent"):
            project_committed_intent(self.db, job_id=job_id)

    def test_restart_projection_is_deterministic_and_inert(self):
        job_id = self.committed()
        before = self.counts()
        first = project_committed_intent(self.db, job_id=job_id)
        second = project_committed_intent(self.new_service().database, job_id=job_id)
        self.assertEqual(first, second)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.query("SELECT state FROM action_jobs"),
                         [("dispatch_committed",)])


if __name__ == "__main__":
    unittest.main()
