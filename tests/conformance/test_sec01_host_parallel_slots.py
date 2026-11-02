"""SEC-01 host parallel-slot limits and JSON binding regression."""
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy

class ParallelSlotTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store=AlphaAuthStore(Path(tmp.name)/"alpha.db",clock=lambda:10000)
        self.session=self.store.redeem(self.store.invite("user.owner"),
            agent_id="agent.one",password="local-password-123")
        self.auth=IntegratedAlphaAdmission(self.store)
        self.auth.provision_host("host.one","operator.one")
        self.auth.assign_agent("agent.one","host.one")
        self.policy=HostCommitPolicy(self.auth)
        self.policy.add_admin_fixture("host.one","admin.one")
        self.config=dict(mode="automatic",idle_only=False,
            gpu_max_percent=None,timezone="UTC",weekdays=list(range(7)),
            start_minute=0,end_minute=1440,max_parallel_effects=2)
        self.assertEqual(self.policy.upsert_rule("host.one","admin.one",
            "limit.two",priority=1,enabled=True,config=self.config).state,"saved")
        self.now=10000

    def admission(self,n):
        key="effect."+str(n)
        job="job."+str(n)
        fingerprint="fingerprint."+str(n)
        self.assertTrue(self.auth.admit("Bearer "+self.session,
            effect_key=key,job_id=job,fingerprint=fingerprint,
            agent_id="agent.one",owner_id="user.owner",
            executor_id="operator.one",host_id="host.one").accepted)
        binding=json.dumps([job,fingerprint,"user.owner","agent.one",
            "user.owner","operator.one","host.one","demo.echo"],
            separators=(",",":"))
        return dict(host_id="host.one",effect_key=key,binding=binding,now=self.now)

    def test_parallel_limit_two_and_release(self):
        a,b,c=[self.admission(i) for i in range(3)]
        self.assertEqual(self.policy.decide(**a).state,"committed_mock")
        self.assertEqual(self.policy.decide(**b).state,"committed_mock")
        self.assertEqual(self.policy.active_count("host.one"),2)
        self.assertEqual(self.policy.decide(**c).reason,"parallel_limit_reached")
        self.assertEqual(self.policy.finish_mock("host.one","admin.one",
            "effect.1").state,"finished_mock")
        self.assertEqual(self.policy.decide(**c).state,"committed_mock")
        self.assertEqual(self.policy.commit_count(),3)

    def test_concurrent_slot_claims_never_exceed_limit(self):
        requests=[self.admission(i) for i in range(6)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(lambda x:self.policy.decide(**x).state,requests))
        self.assertEqual(results.count("committed_mock"),2)
        self.assertEqual(results.count("waiting"),4)
        self.assertEqual(self.policy.active_count("host.one"),2)

    def test_non_admin_cannot_release_slot(self):
        a=self.admission(1)
        self.policy.decide(**a)
        self.assertEqual(self.policy.finish_mock("host.one","user.owner",
            "effect.1").reason,"not_host_admin")
        self.assertEqual(self.policy.active_count("host.one"),1)

    def test_invalid_parallel_limits_rejected(self):
        for invalid in (0,-1,True,1025,"2"):
            cfg=self.config|{"max_parallel_effects":invalid}
            self.assertEqual(self.policy.upsert_rule("host.one","admin.one",
                "bad",priority=1,enabled=True,config=cfg).reason,"invalid_rule")

    def test_json_binding_is_valid_not_invalid_intent(self):
        a=self.admission(1)
        self.assertEqual(self.policy.decide(**a).state,"committed_mock")

if __name__=="__main__":
    unittest.main()
