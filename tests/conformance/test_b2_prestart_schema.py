"""B2.2 v3 migration tests; no executor or pre-start gate."""
import sqlite3
import unittest

import test_action_submission as fixture
from b2_schema import migrate_b2
from b2_prestart_schema import migrate_b2_prestart
from b2_worker import ClaimWorker


class PrestartMigrationTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    issue = fixture.SubmissionTests.issue
    new_service = fixture.SubmissionTests.new_service
    query = fixture.SubmissionTests.query
    counts = fixture.SubmissionTests.counts

    def test_populated_v2_claim_preserved_and_idempotent(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual(claim.state, "claimed")
        before_job = self.query("SELECT * FROM action_jobs")
        before_audit = self.query("SELECT * FROM action_audit ORDER BY event_id")
        before_counts = self.counts()
        migrate_b2_prestart(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(3,)])
        self.assertEqual(self.query("SELECT * FROM action_jobs"), before_job)
        self.assertEqual(self.query("SELECT * FROM action_audit ORDER BY event_id"), before_audit)
        self.assertEqual(self.counts(), before_counts)
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])
        migrate_b2_prestart(self.db)
        self.assertEqual(self.counts(), before_counts)

    def test_v3_accepts_ready_and_ready_audit(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        migrate_b2(self.db)
        migrate_b2_prestart(self.db)
        db = sqlite3.connect(self.db)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("UPDATE action_jobs SET state='ready' WHERE job_id=?", (job.job_id,))
            db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                       ("event.ready", job.job_id, "user.charlie", "job.ready", self.now))
            db.commit()
        finally:
            db.close()
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("ready",)])
        self.assertEqual(self.counts(), (1, 2, 100))

    def test_rejects_v1_without_changes(self):
        with self.assertRaisesRegex(ValueError, "requires action schema"):
            migrate_b2_prestart(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(1,)])
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_failed_migration_rolls_back(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        migrate_b2(self.db)
        db = sqlite3.connect(self.db)
        try:
            # An existing name collision forces a failure after BEGIN IMMEDIATE.
            db.execute("CREATE TABLE action_jobs_v3 (sentinel TEXT)")
            db.commit()
        finally:
            db.close()
        with self.assertRaises(sqlite3.OperationalError):
            migrate_b2_prestart(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(2,)])
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("queued",)])
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_action_service_submit_and_replay_after_v3_migration(self):
        first = self.service.submit(**self.args)
        self.assertTrue(first.allowed)
        migrate_b2(self.db)
        migrate_b2_prestart(self.db)
        restarted = self.new_service()
        replay = restarted.submit(**self.args)
        self.assertTrue(replay.allowed)
        self.assertEqual(replay.job_id, first.job_id)
        second = restarted.submit(**(self.args | {"idempotency_key": "request.2"}))
        self.assertTrue(second.allowed)
        self.assertNotEqual(second.job_id, first.job_id)
        self.assertEqual(self.counts(), (2, 2, 200))
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_repeat_v3_migration_preserves_ready_job_and_audit(self):
        job = self.service.submit(**self.args)
        self.assertTrue(job.allowed)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        self.assertEqual(claim.state, "claimed")
        migrate_b2_prestart(self.db)
        from b2_prestart import PrestartGate
        result = PrestartGate(self.new_service()).authorize(
            job_id=claim.job_id, worker_id="worker.one", claim_token=claim.claim_token)
        self.assertEqual(result.state, "ready")
        before_jobs = self.query("SELECT * FROM action_jobs")
        before_events = self.query("SELECT * FROM action_audit ORDER BY event_id")
        before_counts = self.counts()
        migrate_b2_prestart(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(3,)])
        self.assertEqual(self.query("SELECT * FROM action_jobs"), before_jobs)
        self.assertEqual(self.query("SELECT * FROM action_audit ORDER BY event_id"), before_events)
        self.assertEqual(self.counts(), before_counts)
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])


if __name__ == "__main__":
    unittest.main()
