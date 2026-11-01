"""Private Alpha typed identity boundary tests, including equal ID strings."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore, AlphaPrincipal

class TypedAlphaIdentityTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.auth=AlphaAuthStore(Path(tmp.name)/"typed.db",clock=lambda:10000)

    def test_user_and_agent_same_id_remain_distinct_principals(self):
        secret=self.auth.invite("user.charlie")
        session=self.auth.redeem(secret,agent_id="user.charlie")
        self.assertIsNotNone(session)
        principal=self.auth.principal("Bearer "+session)
        self.assertEqual(principal,AlphaPrincipal("user.charlie","user.charlie"))
        self.assertEqual(self.auth.agents(principal),
                         [{"agent_id":"user.charlie","owner":"user.charlie",
                           "allowed_actions":["demo.echo"]}])
        status,job=self.auth.submit(principal,
            {"action":"demo.echo","idempotency_key":"request.one"})
        self.assertEqual(status,201)
        self.assertEqual((job["user_id"],job["agent_id"]),
                         ("user.charlie","user.charlie"))
        self.assertEqual(len(self.auth.jobs(principal)),1)

    def test_equal_string_does_not_grant_other_user_authority(self):
        a=self.auth.redeem(self.auth.invite("user.charlie"),
                           agent_id="user.charlie")
        b=self.auth.redeem(self.auth.invite("user.other"),
                           agent_id="agent.other")
        principal_a=self.auth.principal("Bearer "+a)
        principal_b=self.auth.principal("Bearer "+b)
        self.assertEqual(self.auth.submit(principal_a,
            {"action":"demo.echo","idempotency_key":"one"})[0],201)
        self.assertEqual(self.auth.jobs(principal_b),[])
        self.assertEqual(self.auth.agents(principal_b)[0]["owner"],"user.other")
        self.assertIsNone(self.auth.principal("Bearer user.charlie"))
        self.assertIsNone(self.auth.principal("Bearer agent.other"))

    def test_disabling_equal_named_user_revokes_session(self):
        session=self.auth.redeem(self.auth.invite("same.id"),agent_id="same.id")
        self.assertTrue(self.auth.disable_user("same.id"))
        self.assertIsNone(self.auth.principal("Bearer "+session))

if __name__=="__main__":
    unittest.main()
