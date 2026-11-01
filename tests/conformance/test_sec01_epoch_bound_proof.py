"""Regression: revocation/regrant ABA and issuing-session binding."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_remote_precommit_sim import LocalProofIssuer
from sec01_epoch_bound_proof_sim import EpochBoundProofs

KEY=b"local-only-epoch-test-key-000000000000000"
PASSWORD="local-password-123"

class EpochProofTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store=AlphaAuthStore(Path(tmp.name)/"alpha.db",clock=lambda:10000)
        self.owner=self.store.redeem(self.store.invite("user.owner"),password=PASSWORD)
        self.friend=self.store.redeem(self.store.invite("user.friend"),password=PASSWORD)
        self.store.create_agent("Bearer "+self.owner,"agent.one")
        self.auth=IntegratedAlphaAdmission(self.store)
        self.auth.provision_host("host.one","operator.one")
        self.auth.assign_agent("agent.one","host.one")
        self.service=EpochBoundProofs(LocalProofIssuer(self.auth,issuer_secret=KEY))
        self.store.grant_agent("Bearer "+self.owner,agent_id="agent.one",
                               grantee_user_id="user.friend")
        self.args=dict(effect_key="effect.one",job_id="job.one",
            fingerprint="fingerprint.one",agent_id="agent.one",
            owner_id="user.owner",executor_id="operator.one",
            host_id="host.one")

    def issue(self):
        proof=self.service.issue("Bearer "+self.friend,now=10000,**self.args)
        self.assertIsNotNone(proof)
        return proof

    def check(self,proof):
        return self.service.check(proof,requester_id="user.friend",
                                  now=10010,**self.args)

    def test_valid_epoch_bound_proof_is_precheck_only(self):
        self.assertEqual(self.check(self.issue()),
                         (True,"online_precheck_only_no_effect"))

    def test_revoke_regrant_does_not_resurrect_old_proof(self):
        proof=self.issue()
        self.store.grant_agent("Bearer "+self.owner,agent_id="agent.one",
                               grantee_user_id="user.friend",revoke=True)
        self.store.grant_agent("Bearer "+self.owner,agent_id="agent.one",
                               grantee_user_id="user.friend")
        self.assertEqual(self.check(proof)[1],"authority_epoch_changed")

    def test_issuing_session_logout_invalidates_proof(self):
        proof=self.issue()
        self.store.revoke_session("Bearer "+self.friend)
        self.assertEqual(self.check(proof)[1],"issuing_session_revoked")

    def test_new_session_cannot_resurrect_old_proof(self):
        proof=self.issue()
        self.store.revoke_session("Bearer "+self.friend)
        fresh=self.store.login("user.friend",PASSWORD)
        self.assertIsNotNone(fresh)
        self.assertEqual(self.check(proof)[1],"issuing_session_revoked")

    def test_host_disable_reenable_does_not_resurrect_proof(self):
        proof=self.issue()
        self.auth.set_host_active("host.one",False)
        self.auth.set_host_active("host.one",True)
        self.assertEqual(self.check(proof)[1],"authority_epoch_changed")

    def test_assignment_disable_reenable_does_not_resurrect_proof(self):
        proof=self.issue()
        self.auth.assign_agent("agent.one","host.one",enabled=False)
        self.auth.assign_agent("agent.one","host.one",enabled=True)
        self.assertEqual(self.check(proof)[1],"authority_epoch_changed")

    def test_mutated_epoch_payload_fails_mac(self):
        proof=self.issue()
        modified=copy.deepcopy(proof)
        key=next(iter(modified["payload"]["epochs"]))
        modified["payload"]["epochs"][key]+=1
        self.assertEqual(self.check(modified)[1],"invalid_envelope_mac")

    def test_owner_disable_triggers_epoch_change(self):
        proof=self.issue()
        self.store.disable_user("user.owner")
        self.assertEqual(self.check(proof)[1],"authority_epoch_changed")

    def test_wrong_requester_denied(self):
        proof=self.issue()
        self.assertEqual(self.service.check(proof,requester_id="user.other",
            now=10010,**self.args)[1],"requester_mismatch")

if __name__=="__main__":
    unittest.main()
