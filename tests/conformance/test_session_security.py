"""MAP v0.3 session and authenticated gateway tests."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from sys import path

ROOT = Path(__file__).resolve().parents[2]
path.insert(0, str(ROOT / "server"))
from session_store import SessionStore
from sqlite_policy_engine import SQLitePolicyEngine
from action_gateway import ActionGateway

EXAMPLES = ROOT / "examples" / "map" / "v0.1"
T0 = datetime(2026,10,31,12,15,tzinfo=timezone.utc).timestamp()


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "sessions.sqlite"
        self.now = [T0]
        self.sessions = SessionStore(self.db,clock=lambda:self.now[0])
        self.credential = self.sessions.enroll("user.charlie")
        self.token = self.sessions.issue(user_id="user.charlie",credential=self.credential,
                                         agent_id="agent.shared.01",delegation_id="grant.01",ttl_seconds=600)

    def test_login_and_wrong_credentials(self):
        self.assertIsNotNone(self.token)
        self.assertIsNone(self.sessions.issue(user_id="user.charlie",credential="invalid",
                                               agent_id="agent.shared.01"))
        self.assertIsNone(self.sessions.issue(user_id="user.unknown",credential="invalid",
                                               agent_id="agent.shared.01"))
        self.assertEqual(self.sessions.verify(self.token).user_id,"user.charlie")

    def test_expiry_and_ttl_bounds(self):
        self.now[0] += 600
        self.assertIsNone(self.sessions.verify(self.token))
        with self.assertRaises(ValueError):
            self.sessions.issue(user_id="user.charlie",credential=self.credential,
                                agent_id="agent.shared.01",ttl_seconds=3601)

    def test_session_binding(self):
        self.assertIsNone(self.sessions.verify(self.token,agent_id="agent.other"))
        self.assertIsNone(self.sessions.verify(self.token,delegation_id="grant.other"))
        self.assertIsNotNone(self.sessions.verify(self.token,agent_id="agent.shared.01",
                                                   delegation_id="grant.01"))

    def test_revoke_persists_restart(self):
        self.assertFalse(self.sessions.revoke(self.token,user_id="user.charlie",credential="wrong"))
        self.assertTrue(self.sessions.revoke(self.token,user_id="user.charlie",credential=self.credential))
        self.assertIsNone(SessionStore(self.db,clock=lambda:self.now[0]).verify(self.token))

    def test_disable_revokes_all(self):
        self.assertTrue(self.sessions.disable_user("user.charlie",credential=self.credential))
        self.assertIsNone(self.sessions.verify(self.token))
        self.assertIsNone(self.sessions.issue(user_id="user.charlie",credential=self.credential,
                                               agent_id="agent.shared.01"))

    def test_gateway_authorization_and_denials(self):
        policy = SQLitePolicyEngine(self.db)
        agent = json.loads((EXAMPLES / "shared-agent.json").read_text())
        grant = json.loads((EXAMPLES / "delegation-grant.json").read_text())
        self.assertTrue(policy.register_agent(agent).allowed)
        self.assertTrue(policy.add_grant(grant,verified_actor="user.alice").allowed)
        gateway = ActionGateway(self.sessions,policy)
        args = dict(token=self.token,delegation_id="grant.01",agent_id="agent.shared.01",
                    scope="game.test_feedback",target_id="game.maze",cost_minor=50,
                    operation_id="op.1")
        self.assertTrue(gateway.authorize(**args).allowed)
        self.assertEqual(gateway.authorize(**args).reason,"already_allowed")
        self.assertEqual(gateway.authorize(**(args | {"token":"invalid"})).reason,"invalid_session")
        self.assertEqual(gateway.authorize(**(args | {"agent_id":"agent.other"})).reason,"invalid_session")
        self.assertEqual(gateway.authorize(**(args | {"scope":"game.develop"})).reason,"scope_denied")
        self.assertTrue(policy.revoke(delegation_id="grant.01",verified_actor="user.alice").allowed)
        self.assertEqual(gateway.authorize(**args).reason,"grant_revoked")

    def test_gateway_server_time_not_caller_time(self):
        policy = SQLitePolicyEngine(self.db)
        agent = json.loads((EXAMPLES / "shared-agent.json").read_text())
        grant = json.loads((EXAMPLES / "delegation-grant.json").read_text())
        policy.register_agent(agent)
        policy.add_grant(grant,verified_actor="user.alice")
        gateway = ActionGateway(self.sessions,policy)
        self.now[0] = datetime(2026,10,31,14,1,tzinfo=timezone.utc).timestamp()
        fresh = self.sessions.issue(user_id="user.charlie",credential=self.credential,
                                    agent_id="agent.shared.01",delegation_id="grant.01")
        result = gateway.authorize(token=fresh,delegation_id="grant.01",agent_id="agent.shared.01",
                                   scope="game.test_feedback",target_id="game.maze")
        self.assertEqual(result.reason,"outside_validity")


if __name__=="__main__":
    unittest.main()
