"""Schema-oriented B2 persisted-record validation regression tests."""
import copy
import json
import unittest
from pathlib import Path
from sys import path

ROOT = Path(__file__).resolve().parents[2]
path.insert(0, str(ROOT / "server"))
from b2_validation import valid_agent, valid_grant, valid_request


class PersistedValidationTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / "examples/map/v0.1"
        self.agent = json.loads((base / "shared-agent.json").read_text())
        self.grant = json.loads((base / "delegation-grant.json").read_text())
        self.request = dict(version=1, user_id="user.charlie",
                            agent_id="agent.shared.01", delegation_id="grant.01",
                            target_id="game.maze", action_type="game.feedback",
                            scope="game.test_feedback", parameters={"text": "hello"})

    def test_valid_fixtures(self):
        self.assertTrue(valid_agent(self.agent))
        self.assertTrue(valid_grant(self.grant))
        self.assertTrue(valid_request(self.request))

    def test_invalid_request_shape(self):
        for key, value in (("version", True), ("target_id", []),
                           ("parameters", []), ("scope", None)):
            with self.subTest(key=key):
                record = self.request | {key: value}
                self.assertFalse(valid_request(record))
        self.assertFalse(valid_request(self.request | {"unexpected": 1}))

    def test_invalid_grant_shape(self):
        for key, value in (("issuer_user_id", "bad id"), ("scopes", ["game.test_feedback"] * 2),
                           ("max_spend_minor", True), ("target_id", [])):
            with self.subTest(key=key):
                record = self.grant | {key: value}
                self.assertFalse(valid_grant(record))
        self.assertFalse(valid_grant(self.grant | {"unexpected": 1}))

    def test_invalid_agent_shape(self):
        for key, value in (("revision", True), ("accountable_party_id", "bad id"),
                           ("state", "unknown"), ("operators", [])):
            with self.subTest(key=key):
                record = self.agent | {key: value}
                self.assertFalse(valid_agent(record))
        self.assertFalse(valid_agent(self.agent | {"unexpected": 1}))
        agent = copy.deepcopy(self.agent)
        agent["operators"][0]["roles"].append("admin")
        self.assertFalse(valid_agent(agent))

    def test_optional_empty_allowed_scopes(self):
        agent = copy.deepcopy(self.agent)
        agent["policy"]["allowed_scopes"] = []
        self.assertTrue(valid_agent(agent))


if __name__ == "__main__":
    unittest.main()
