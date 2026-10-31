"""B2 schema migration regression tests (opt-in; no worker)."""
import sqlite3
import unittest

from test_action_submission import SubmissionTests as _SubmissionFixture
from b2_schema import migrate_b2


class B2MigrationTests(unittest.TestCase):
    setUp = _SubmissionFixture.setUp
    issue = _SubmissionFixture.issue
    new_service = _SubmissionFixture.new_service
    query = _SubmissionFixture.query
    counts = _SubmissionFixture.counts

    def test_migrate_populated_b1_preserves_rows_and_reservations(self):
        first = self.service.submit(**self.args)
        self.assertTrue(first.allowed)
        before_job = self.query("SELECT job_id,user_id,agent_id,delegation_id,"
                                "request_json,cost_minor,state,session_token_hash FROM action_jobs")
        before_audit = self.query("SELECT * FROM action_audit")
        before_counts = self.counts()
        migrate_b2(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(2,)])
        self.assertEqual(self.query("SELECT job_id,user_id,agent_id,delegation_id,"
                                    "request_json,cost_minor,state,session_token_hash FROM action_jobs"),
                         before_job)
        self.assertEqual(self.query("SELECT * FROM action_audit"), before_audit)
        self.assertEqual(self.counts(), before_counts)
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])
        migrate_b2(self.db)
        self.assertEqual(self.counts(), before_counts)

    def test_legacy_null_session_reference_survives_migration(self):
        result = self.service.submit(**self.args)
        self.assertTrue(result.allowed)
        db = sqlite3.connect(self.db)
        try:
            db.execute("UPDATE action_jobs SET session_token_hash=NULL")
            db.commit()
        finally:
            db.close()
        migrate_b2(self.db)
        self.assertEqual(self.query("SELECT session_token_hash FROM action_jobs"), [(None,)])

    def test_v2_allows_new_states_and_multiple_audit_events(self):
        result = self.service.submit(**self.args)
        self.assertTrue(result.allowed)
        migrate_b2(self.db)
        db = sqlite3.connect(self.db)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("UPDATE action_jobs SET state='claimed' WHERE job_id=?", (result.job_id,))
            db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                       ("event.claim", result.job_id, "user.charlie", "job.claimed", self.now))
            db.commit()
        finally:
            db.close()
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("claimed",)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM action_audit"), [(2,)])

    def test_b1_submission_remains_usable_after_v2_migration(self):
        first = self.service.submit(**self.args)
        self.assertTrue(first.allowed)
        migrate_b2(self.db)
        restarted = self.new_service()
        replay = restarted.submit(**self.args)
        self.assertTrue(replay.allowed)
        self.assertEqual(replay.job_id, first.job_id)
        next_job = restarted.submit(**(self.args | {"idempotency_key": "request.2"}))
        self.assertTrue(next_job.allowed)
        self.assertNotEqual(next_job.job_id, first.job_id)
        self.assertEqual(self.counts(), (2, 2, 200))
        self.assertEqual(self.query("PRAGMA foreign_key_check"), [])

    def test_unsupported_version_fails_without_changes(self):
        db = sqlite3.connect(self.db)
        try:
            db.execute("UPDATE action_schema SET version=99")
            db.commit()
        finally:
            db.close()
        with self.assertRaisesRegex(ValueError, "unsupported"):
            migrate_b2(self.db)
        self.assertEqual(self.query("SELECT version FROM action_schema"), [(99,)])


if __name__ == "__main__":
    unittest.main()
