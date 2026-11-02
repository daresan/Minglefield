"""Multi-agent account/commissioning tests: authorization is explicit and revocable."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore

PASSWORD="local-test-password-123"

class DelegatedAlphaAgentTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store=AlphaAuthStore(Path(temporary.name)/"alpha.db",clock=lambda:10000)
        self.owner=self.store.redeem(self.store.invite("user.owner"),password=PASSWORD)
        self.friend=self.store.redeem(self.store.invite("user.friend"),password=PASSWORD)

    def request(self, token, agent, key="request.one"):
        return self.store.submit_agent("Bearer "+token,{
            "agent_id":agent,"action":"demo.echo","idempotency_key":key})

    def test_account_can_exist_without_any_agents(self):
        principal=self.store.principal("Bearer "+self.owner)
        self.assertIsNotNone(principal)
        self.assertEqual(self.store.available_agents("Bearer "+self.owner),[])
        self.assertEqual(self.request(self.owner,"agent.one")[0],403)

    def test_one_user_can_own_multiple_agents(self):
        for agent in ("agent.one","agent.two"):
            self.assertEqual(self.store.create_agent("Bearer "+self.owner,agent)[0],201)
        agents=self.store.available_agents("Bearer "+self.owner)
        self.assertEqual([a["agent_id"] for a in agents],["agent.one","agent.two"])
        self.assertTrue(all(a["relationship"]=="owned" for a in agents))
        self.assertEqual(self.request(self.owner,"agent.one","one")[0],201)
        self.assertEqual(self.request(self.owner,"agent.two","two")[0],201)

    def test_commission_external_agent_with_revoke(self):
        self.store.create_agent("Bearer "+self.owner,"agent.shared")
        self.assertEqual(self.request(self.friend,"agent.shared")[0],403)
        self.assertEqual(self.store.grant_agent("Bearer "+self.owner,
            agent_id="agent.shared",grantee_user_id="user.friend")[0],200)
        available=self.store.available_agents("Bearer "+self.friend)
        self.assertEqual(len(available),1)
        self.assertEqual(available[0]["relationship"],"delegated")
        self.assertEqual(available[0]["owner"],"user.owner")
        self.assertEqual(self.request(self.friend,"agent.shared","one")[0],201)
        self.assertEqual(self.store.grant_agent("Bearer "+self.owner,
            agent_id="agent.shared",grantee_user_id="user.friend",revoke=True)[0],200)
        self.assertEqual(self.store.available_agents("Bearer "+self.friend),[])
        self.assertEqual(self.request(self.friend,"agent.shared","two")[0],403)

    def test_only_owner_can_delegate_and_id_is_not_identity(self):
        self.store.create_agent("Bearer "+self.owner,"user.friend")
        self.assertEqual(self.store.grant_agent("Bearer "+self.friend,
            agent_id="user.friend",grantee_user_id="user.owner")[0],403)
        self.assertEqual(self.request(self.friend,"user.friend")[0],403)
        self.assertEqual(self.store.create_agent("Bearer "+self.friend,"user.friend")[0],409)

    def test_delegation_does_not_reassign_ownership_or_expose_jobs(self):
        self.store.create_agent("Bearer "+self.owner,"agent.shared")
        self.store.grant_agent("Bearer "+self.owner,agent_id="agent.shared",
                               grantee_user_id="user.friend")
        self.request(self.friend,"agent.shared","friend-job")
        self.assertEqual(self.store.jobs(self.store.principal("Bearer "+self.owner)),[])
        jobs=self.store.jobs(self.store.principal("Bearer "+self.friend))
        self.assertEqual(jobs[0]["user_id"],"user.friend")
        self.assertEqual(jobs[0]["agent_id"],"agent.shared")

    def test_disable_owner_invalidates_delegated_usage(self):
        self.store.create_agent("Bearer "+self.owner,"agent.shared")
        self.store.grant_agent("Bearer "+self.owner,agent_id="agent.shared",
                               grantee_user_id="user.friend")
        self.store.disable_user("user.owner")
        self.assertEqual(self.store.available_agents("Bearer "+self.friend),[])
        self.assertEqual(self.request(self.friend,"agent.shared")[0],403)

if __name__=="__main__":
    unittest.main()
