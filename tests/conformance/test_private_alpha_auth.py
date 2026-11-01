"""Auth v1 isolated SQLite security tests. Local and simulated only."""
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from private_alpha_auth import AlphaAuthStore

class AlphaAuthTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)/"auth.sqlite"
        self.now = 10000
        self.auth = AlphaAuthStore(self.path, clock=lambda: self.now)

    def provision(self, user="user.one", agent="agent.one"):
        invite = self.auth.invite(user)
        session = self.auth.redeem(invite, agent_id=agent)
        self.assertIsNotNone(session)
        return invite, session

    def test_owner_can_list_delegations_without_exposing_to_other_users(self):
        _, owner=self.provision()
        _, friend=self.provision("user.friend","agent.friend")
        self.assertEqual(self.auth.grant_agent("Bearer "+owner,
            agent_id="agent.one",grantee_user_id="user.friend")[0],200)
        status,data=self.auth.owned_agent_grants("Bearer "+owner,"agent.one")
        self.assertEqual(status,200)
        self.assertEqual(data["grantees"],["user.friend"])
        self.assertEqual(self.auth.owned_agent_grants("Bearer "+friend,"agent.one")[0],403)
        self.assertEqual(self.auth.owned_agent_grants("Bearer invalid","agent.one")[0],401)
        self.assertEqual(self.auth.grant_agent("Bearer "+owner,
            agent_id="agent.one",grantee_user_id="user.friend",revoke=True)[0],200)
        self.assertEqual(self.auth.owned_agent_grants("Bearer "+owner,
            "agent.one")[1]["grantees"],[])

    def test_grantable_user_directory_requires_session_and_filters_disabled(self):
        _, owner = self.provision()
        self.provision("user.friend", "agent.friend")
        self.provision("user.disabled", "agent.disabled")
        self.assertIsNone(self.auth.grantable_users("Bearer invalid"))
        self.assertEqual(self.auth.grantable_users("Bearer "+owner),
                         [{"user_id":"user.disabled"},{"user_id":"user.friend"}])
        self.auth.disable_user("user.disabled")
        self.assertEqual(self.auth.grantable_users("Bearer "+owner),
                         [{"user_id":"user.friend"}])

    def test_invite_one_time_and_no_open_enrollment(self):
        invite, session = self.provision()
        self.assertIsNone(self.auth.redeem(invite, agent_id="agent.two"))
        self.assertIsNone(self.auth.redeem("wrong", agent_id="agent.three"))
        self.assertEqual(self.auth.principal("Bearer "+session).user_id,"user.one")

    def test_invite_expiration(self):
        invite = self.auth.invite("user.one", ttl=1)
        self.now += 1
        self.assertIsNone(self.auth.redeem(invite, agent_id="agent.one"))

    def test_session_expiration_logout_and_restart(self):
        _, session = self.provision()
        restored = AlphaAuthStore(self.path, clock=lambda: self.now)
        self.assertIsNotNone(restored.principal("Bearer "+session))
        self.assertTrue(restored.revoke_session("Bearer "+session))
        self.assertFalse(restored.revoke_session("Bearer "+session))
        self.assertIsNone(restored.principal("Bearer "+session))
        other = self.auth.invite("user.two")
        token = self.auth.redeem(other,agent_id="agent.two",session_ttl=1)
        self.now += 1
        self.assertIsNone(restored.principal("Bearer "+token))

    def test_user_disable_revokes_session(self):
        _, session = self.provision()
        self.assertTrue(self.auth.disable_user("user.one"))
        self.assertIsNone(self.auth.principal("Bearer "+session))
        self.assertFalse(self.auth.disable_user("user.unknown"))

    def test_isolated_agents_jobs_and_persistent_history(self):
        _, a = self.provision()
        _, b = self.provision("user.two","agent.two")
        p = self.auth.principal("Bearer "+a)
        q = self.auth.principal("Bearer "+b)
        status, job = self.auth.submit(p,{"action":"demo.echo","idempotency_key":"once"})
        self.assertEqual(status,201)
        self.assertEqual(self.auth.jobs(q),[])
        self.assertEqual(self.auth.agents(q)[0]["agent_id"],"agent.two")
        restored = AlphaAuthStore(self.path,clock=lambda:self.now)
        self.assertEqual(restored.jobs(p)[0]["job_id"],job["job_id"])
        self.assertEqual(restored.submit(p,{"action":"demo.echo","idempotency_key":"once"})[0],200)

    def test_parallel_invite_redemption_single_winner(self):
        token = self.auth.invite("user.one")
        def redeem(i):
            return self.auth.redeem(token,agent_id="agent."+str(i))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(redeem,range(2)))
        self.assertEqual(sum(r is not None for r in results),1)

    def test_quota_invalid_actions_and_unknown_identity(self):
        _, session = self.provision()
        p = self.auth.principal("Bearer "+session)
        self.assertIsNone(self.auth.principal("Bearer wrong"))
        self.assertEqual(self.auth.submit(p,{"action":"shell","idempotency_key":"1"})[0],400)
        for i in range(5):
            self.assertEqual(self.auth.submit(p,{"action":"demo.echo","idempotency_key":str(i)})[0],201)
        self.assertEqual(self.auth.submit(p,{"action":"demo.echo","idempotency_key":"extra"})[0],429)

if __name__=="__main__":
    unittest.main()
