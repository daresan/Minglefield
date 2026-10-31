"""B2 session reference regression tests; no worker or external effects."""
import hashlib
import sqlite3
import unittest

from test_action_submission import SubmissionTests


class SessionBindingTests(unittest.TestCase):
    setUp = SubmissionTests.setUp
    issue = SubmissionTests.issue
    new_service = SubmissionTests.new_service
    query = SubmissionTests.query
    counts = SubmissionTests.counts

    def test_new_job_binds_verified_session_without_bearer(self):
        result = self.service.submit(**self.args)
        self.assertTrue(result.allowed)
        bound = self.query("SELECT session_token_hash FROM action_jobs WHERE job_id=?",
                           (result.job_id,))[0][0]
        self.assertEqual(bound, hashlib.sha256(self.token.encode("utf-8")).hexdigest())
        self.assertNotEqual(bound, self.token)
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_idempotent_replay_does_not_rebind_session(self):
        first = self.service.submit(**self.args)
        self.assertTrue(first.allowed)
        second_token = self.issue()
        again = self.service.submit(**(self.args | {"token": second_token}))
        self.assertEqual(first.job_id, again.job_id)
        bound = self.query("SELECT session_token_hash FROM action_jobs")[0][0]
        self.assertEqual(bound, hashlib.sha256(self.token.encode("utf-8")).hexdigest())
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_legacy_null_reference_is_preserved_on_replay_and_restart(self):
        first = self.service.submit(**self.args)
        self.assertTrue(first.allowed)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE action_jobs SET session_token_hash=NULL WHERE job_id=?",
                       (first.job_id,))
        self.new_service()
        replay = self.service.submit(**(self.args | {"token": self.issue()}))
        self.assertEqual(replay.job_id, first.job_id)
        self.assertIsNone(self.query("SELECT session_token_hash FROM action_jobs")[0][0])
        self.assertEqual(self.counts(), (1, 1, 100))

    def test_session_revocation_does_not_change_durable_binding(self):
        first = self.service.submit(**self.args)
        self.assertTrue(first.allowed)
        self.assertTrue(self.sessions.revoke(self.token, user_id="user.charlie",
                                             credential=self.credential))
        self.assertEqual(self.service.submit(**self.args).reason, "invalid_session")
        bound = self.query("SELECT session_token_hash FROM action_jobs")[0][0]
        self.assertEqual(bound, hashlib.sha256(self.token.encode("utf-8")).hexdigest())
        self.assertEqual(self.counts(), (1, 1, 100))


if __name__ == "__main__":
    unittest.main()
