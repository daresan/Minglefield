"""B2.3a migration tests: schema only, no dispatch or effects."""
import sqlite3
import unittest

import test_action_submission as fixture
from b2_worker import ClaimWorker
from b2_prestart import PrestartGate
from b2_prestart_schema import migrate_b2_prestart
from b2_dispatch_schema import migrate_b2_dispatch


class DispatchMigrationTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    query = fixture.SubmissionTests.query
    counts = fixture.SubmissionTests.counts

    def ready_job(self):
        submitted = self.service.submit(**self.args)
        self.assertTrue(submitted.allowed)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual(claim.state, "claimed")
        migrate_b2_prestart(self.db)
        gate = PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        self.assertEqual(gate.state, "ready")
        return claim.job_id

    def test_preserves_ready_job_events_and_budget_on_repeat(self):
        self.ready_job()
        old_jobs = self.query("SELECT * FROM action_jobs")
        old_events = self.query("SELECT * FROM action_audit ORDER BY event_id")
        old_counts = self.counts()
        migrate_b2_dispatch(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(4,)])
        self.assertEqual([row[:15] for row in self.query("SELECT * FROM action_jobs")], old_jobs)
        self.assertEqual(self.query("SELECT * FROM action_audit ORDER BY event_id"), old_events)
        self.assertEqual(self.counts(), old_counts)
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])
        migrate_b2_dispatch(self.db)
        self.assertEqual(self.counts(), old_counts)

    def test_rejects_v1_without_changes(self):
        with self.assertRaisesRegex(ValueError, "requires action schema"):
            migrate_b2_dispatch(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(1,)])

    def test_collision_rolls_back_everything(self):
        self.ready_job()
        db = sqlite3.connect(self.db)
        try:
            db.execute("CREATE TABLE action_jobs_v4 (sentinel TEXT)")
            db.commit()
        finally:
            db.close()
        before = self.counts()
        with self.assertRaises(sqlite3.OperationalError):
            migrate_b2_dispatch(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(3,)])
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("ready",)])
        self.assertEqual(self.counts(), before)

    def test_new_dispatch_fields_null_and_partial_dispatch_rejected(self):
        self.ready_job()
        migrate_b2_dispatch(self.db)
        self.assertEqual(self.query("""SELECT effect_idempotency_key,dispatch_fingerprint,
            adapter_id,adapter_version,dispatched_at FROM action_jobs"""),
            [(None, None, None, None, None)])
        db = sqlite3.connect(self.db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("""UPDATE action_jobs SET state='dispatch_committed'
                    WHERE state='ready'""")
            db.rollback()
        finally:
            db.close()
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("ready",)])

    def test_repeated_v4_rejects_missing_dispatch_column(self):
        self.ready_job()
        migrate_b2_dispatch(self.db)
        db = sqlite3.connect(self.db)
        try:
            db.execute("ALTER TABLE action_jobs DROP COLUMN adapter_version")
            db.commit()
        finally:
            db.close()
        with self.assertRaisesRegex(ValueError, "incomplete action schema"):
            migrate_b2_dispatch(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(4,)])


if __name__ == "__main__":
    unittest.main()
