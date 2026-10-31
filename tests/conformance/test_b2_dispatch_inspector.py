"""Read-only dispatch diagnostic regression tests."""
import unittest
import test_action_submission as fixture
from b2_worker import ClaimWorker
from b2_prestart import PrestartGate
from b2_prestart_schema import migrate_b2_prestart
from b2_dispatch_schema import migrate_b2_dispatch
from b2_dispatch import DispatchGate
from b2_fake_adapter import FakeOutcome, FakeOutcomeRecorder
from b2_dispatch_inspector import DispatchInspector


class DispatchInspectorTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    issue = fixture.SubmissionTests.issue
    new_service = fixture.SubmissionTests.new_service
    query = fixture.SubmissionTests.query
    counts = fixture.SubmissionTests.counts

    def committed(self):
        self.service.submit(**self.args)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        migrate_b2_prestart(self.db)
        self.assertEqual(PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one",
            claim_token=claim.claim_token).state, "ready")
        migrate_b2_dispatch(self.db)
        self.assertEqual(DispatchGate(self.new_service(), adapters={
            "game.feedback": ("fake.test", "1")}).commit_intent(
                job_id=claim.job_id, worker_id="worker.one",
                claim_token=claim.claim_token).state, "dispatch_committed")
        return self.query("SELECT job_id,effect_idempotency_key FROM action_jobs")[0]

    def test_unresolved_intent_does_not_mutate(self):
        job_id, key = self.committed()
        before = self.counts()
        inspector = DispatchInspector(self.db)
        record = inspector.inspect(job_id=job_id)
        self.assertEqual(record.state, "dispatch_committed")
        self.assertEqual(record.classification, "unresolved_intent_manual_review")
        self.assertEqual(record.adapter_id, "fake.test")
        self.assertEqual(record.adapter_version, "1")
        self.assertEqual(record.audit_events, (
            "job.queued", "job.claimed", "job.ready", "job.dispatch_committed"))
        self.assertNotIn(key, repr(record))
        self.assertEqual(self.counts(), before)
        self.assertEqual(inspector.inspect(job_id=job_id), record)

    def test_terminal_and_unknown_classification(self):
        for outcome, classification in (
                ("succeeded", "recorded_terminal_outcome"),
                ("failed", "recorded_terminal_outcome"),
                ("outcome_unknown", "ambiguous_outcome_manual_review")):
            with self.subTest(outcome=outcome):
                self.setUp()
                job_id, key = self.committed()
                self.assertEqual(FakeOutcomeRecorder(self.new_service()).record(
                    job_id=job_id, effect_idempotency_key=key,
                    outcome=FakeOutcome(outcome)).state, outcome)
                before = self.counts()
                record = DispatchInspector(self.db).inspect(job_id=job_id)
                self.assertEqual((record.state, record.classification),
                                 (outcome, classification))
                self.assertEqual(record.audit_events[-1], "job." + outcome)
                self.assertEqual(self.counts(), before)

    def test_missing_job_and_invalid_id(self):
        self.committed()
        inspector = DispatchInspector(self.db)
        self.assertIsNone(inspector.inspect(job_id="job.missing"))
        for value in ("", None, 42, "x" * 129):
            with self.subTest(value=value), self.assertRaises(ValueError):
                inspector.inspect(job_id=value)

    def test_requires_v4_and_does_not_migrate(self):
        self.service.submit(**self.args)
        before = self.query("SELECT version FROM action_schema")
        with self.assertRaisesRegex(ValueError, "schema v4"):
            DispatchInspector(self.db).inspect(job_id="job.any")
        self.assertEqual(self.query("SELECT version FROM action_schema"), before)
