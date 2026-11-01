"""Host-admin policy and local atomic mock-commit conformance tests."""
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy

PW="local-test-password-123"
NOW=int(datetime(2026,11,2,12,tzinfo=timezone.utc).timestamp())
def rule(**kw):
    return dict(mode="automatic",idle_only=False,gpu_max_percent=None,
        timezone="UTC",weekdays=list(range(7)),start_minute=0,
        end_minute=1440)|kw

class HostPolicyTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.db=Path(t.name)/"alpha.db"
        self.store=AlphaAuthStore(self.db,clock=lambda:NOW)
        self.owner=self.store.redeem(self.store.invite("user.owner"),password=PW)
        self.friend=self.store.redeem(self.store.invite("user.friend"),password=PW)
        self.store.create_agent("Bearer "+self.owner,"agent.one")
        self.auth=IntegratedAlphaAdmission(self.store)
        self.auth.provision_host("host.one","operator.one")
        self.auth.assign_agent("agent.one","host.one")
        self.policy=HostCommitPolicy(self.auth)
        self.policy.add_admin_fixture("host.one","admin.one")
        self.args=dict(effect_key="effect.one",job_id="job.one",
            fingerprint="fingerprint.one",agent_id="agent.one",
            owner_id="user.owner",executor_id="operator.one",host_id="host.one")
        self.binding=json.dumps(["job.one","fingerprint.one","user.friend",
            "agent.one","user.owner","operator.one","host.one","demo.echo"],
            separators=(",",":"))
        self.store.grant_agent("Bearer "+self.owner,agent_id="agent.one",
                               grantee_user_id="user.friend")
        self.assertTrue(self.auth.admit("Bearer "+self.friend,**self.args).accepted)

    def save(self,config=None,**kw):
        return self.policy.upsert_rule("host.one","admin.one","rule.one",
            priority=1,enabled=True,config=rule() if config is None else config,
            **kw)

    def decide(self,**kw):
        return self.policy.decide(host_id="host.one",effect_key="effect.one",
            binding=self.binding,now=NOW,**kw)

    def test_default_deny_no_rules(self):
        self.assertEqual(self.decide().reason,"no_enabled_rule")

    def test_automatic_commit_is_mock_and_idempotent(self):
        self.save()
        self.assertEqual(self.decide().state,"committed_mock")
        self.assertEqual(self.decide().reason,"historical_mock_commit")
        self.assertEqual(self.policy.commit_count(),1)

    def test_non_admin_cannot_edit_or_approve(self):
        self.assertEqual(self.policy.upsert_rule("host.one","user.friend",
            "evil",priority=0,enabled=True,config=rule()).reason,"not_host_admin")
        self.assertEqual(self.policy.approve("host.one","user.friend",
            "effect.one").reason,"not_host_admin")
        self.assertEqual(self.policy.delete_rule("host.one","user.friend",
            "rule.one").reason,"not_host_admin")

    def test_manual_approval(self):
        self.save(rule(mode="manual"))
        self.assertEqual(self.decide().reason,"manual_approval_required")
        self.policy.approve("host.one","admin.one","effect.one")
        self.assertEqual(self.decide().state,"committed_mock")

    def test_idle_and_gpu_threshold(self):
        self.save(rule(idle_only=True,gpu_max_percent=60))
        self.assertEqual(self.decide().reason,"telemetry_unavailable")
        self.assertEqual(self.decide(running_effects=1,gpu_percent=20).reason,"host_busy")
        self.assertEqual(self.decide(running_effects=0,gpu_percent=60).reason,
                         "gpu_threshold_not_met")
        self.assertEqual(self.decide(running_effects=0,gpu_percent=59).state,
                         "committed_mock")

    def test_schedule_blocks_outside_window(self):
        self.save(rule(weekdays=[0],start_minute=0,end_minute=60))
        self.assertEqual(self.decide().reason,"outside_schedule")

    def test_disable_edit_delete_rule(self):
        self.save()
        self.policy.upsert_rule("host.one","admin.one","rule.one",priority=1,
            enabled=False,config=rule())
        self.assertEqual(self.decide().reason,"no_enabled_rule")
        self.save(rule(mode="manual"))
        self.assertEqual(self.decide().reason,"manual_approval_required")
        self.assertEqual(self.policy.delete_rule("host.one","admin.one",
            "rule.one").state,"deleted")
        self.assertEqual(self.decide().reason,"no_enabled_rule")

    def test_multiple_rules_prioritized_and_first_matching_blocks(self):
        self.save(rule(mode="manual"))
        self.policy.upsert_rule("host.one","admin.one","rule.two",
            priority=2,enabled=True,config=rule())
        self.assertEqual(self.decide().reason,"manual_approval_required")

    def test_missing_admission_and_wrong_binding_denied(self):
        self.save()
        self.assertEqual(self.policy.decide(host_id="host.one",effect_key="missing",
            binding=self.binding,now=NOW).reason,"admission_binding_missing")
        self.assertEqual(self.policy.decide(host_id="host.one",effect_key="effect.one",
            binding="fake",now=NOW).reason,"admission_binding_missing")

    def test_revoke_before_commit_denies(self):
        self.save()
        self.store.grant_agent("Bearer "+self.owner,agent_id="agent.one",
            grantee_user_id="user.friend",revoke=True)
        self.assertEqual(self.decide().reason,"grant_revoked")

    def test_host_deactivation_denies(self):
        self.save()
        self.auth.set_host_active("host.one",False)
        self.assertEqual(self.decide().reason,"host_unavailable")

    def test_concurrent_commit_only_one_record(self):
        self.save()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.decide().state,(0,1)))
        self.assertEqual(sorted(results),["committed_mock","duplicate"])
        self.assertEqual(self.policy.commit_count(),1)

    def test_persists_after_reopen(self):
        self.save()
        self.assertEqual(self.decide().state,"committed_mock")
        again=HostCommitPolicy(IntegratedAlphaAdmission(AlphaAuthStore(
            self.db,clock=lambda:NOW)))
        self.assertEqual(again.decide(host_id="host.one",effect_key="effect.one",
            binding=self.binding,now=NOW).state,"duplicate")

    def test_bad_rule_rejected(self):
        self.assertEqual(self.save(rule(gpu_max_percent=101)).reason,"invalid_rule")
        self.assertEqual(self.save(rule(start_minute=1300,end_minute=100)).reason,
                         "invalid_rule")

if __name__=="__main__":
    unittest.main()
