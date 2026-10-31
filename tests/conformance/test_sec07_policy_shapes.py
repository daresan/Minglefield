"""SEC-07 adversarial stored-policy shape reproductions (submission boundary).

These tests deliberately mutate trusted bootstrap records after registration.
No external effects are performed.
"""
import json
import sqlite3
import unittest

import test_action_submission as fixture


class StoredPolicyShapes(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp

    def mutate_json(self, table, column, field, value):
        with sqlite3.connect(self.db) as db:
            row = db.execute(f"SELECT {column} FROM {table}").fetchone()
            document = json.loads(row[0])
            document[field] = value
            db.execute(f"UPDATE {table} SET {column}=?", (json.dumps(document),))

    @unittest.expectedFailure
    def test_string_grant_scopes_must_not_authorize(self):
        self.mutate_json("grants", "grant_json", "scopes", "game.test_feedback")
        result = self.service.submit(**self.args)
        self.assertFalse(result.allowed)
        self.assertEqual(fixture.SubmissionTests.counts(self), (0, 0, 0))

    @unittest.expectedFailure
    def test_string_agent_scopes_must_not_authorize(self):
        with sqlite3.connect(self.db) as db:
            agent = json.loads(db.execute("SELECT descriptor FROM agents").fetchone()[0])
            agent["policy"]["allowed_scopes"] = "game.test_feedback"
            db.execute("UPDATE agents SET descriptor=?", (json.dumps(agent),))
        result = self.service.submit(**self.args)
        self.assertFalse(result.allowed)
        self.assertEqual(fixture.SubmissionTests.counts(self), (0, 0, 0))

    @unittest.expectedFailure
    def test_boolean_grant_budget_must_fail_closed(self):
        self.mutate_json("grants", "grant_json", "max_spend_minor", True)
        result = self.service.submit(**self.args)
        self.assertFalse(result.allowed)
        self.assertEqual(fixture.SubmissionTests.counts(self), (0, 0, 0))
