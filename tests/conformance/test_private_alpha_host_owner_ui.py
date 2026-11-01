"""Local host ownership: claim requires console secret; effect is metadata only."""
import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from private_alpha_auth import AlphaAuthStore
from private_alpha_gateway import handler_for
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy

class OwnerUiTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store=AlphaAuthStore(Path(temp.name)/"db.sqlite",clock=lambda:10000)
        self.owner=self.store.redeem(self.store.invite("user.owner"),
                                     password="password-123456")
        self.other=self.store.redeem(self.store.invite("user.other"),
                                     password="password-123456")
        self.policy=HostCommitPolicy(IntegratedAlphaAdmission(self.store))
        self.store._host_policy=self.policy
        self.server=ThreadingHTTPServer(("127.0.0.1",0),
            handler_for(self.store,local_bootstrap_secret="local-only-secret"))
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,2)

    def req(self,path,token=None,payload=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)
        headers={"Authorization":"Bearer "+token} if token else {}
        if payload is not None:headers["Content-Type"]="application/json"
        try:
            conn.request("POST" if payload is not None else "GET",path,
                body=json.dumps(payload) if payload is not None else None,headers=headers)
            resp=conn.getresponse()
            return resp.status,json.loads(resp.read())
        finally:conn.close()

    def claim(self,token,secret="local-only-secret"):
        return self.req("/api/host/claim",token,
            dict(host_id="host.local",bootstrap_secret=secret))

    def test_host_claim_controls_really_exist_in_html(self):
        from private_alpha_gateway import PAGE
        for control in ('id="claimHost"', 'id="claimSecret"',
                        'id="claimHostButton"', 'id="effectSave"',
                        'id="effectManual"', 'id="hostJobsRefresh"', 'id="hostJobCancel"', 'id="hostJobEvaluate"', 'id="hostJobReserve"', 'id="hostJobRelease"'):
            self.assertIn(control,PAGE)
        self.assertNotIn("Host-Admin-Rechte müssen lokal vergeben werden",PAGE)
        self.assertNotIn("Nur Hosts, für die dein angemeldeter Benutzer",PAGE)

    def test_owner_can_claim_and_configure_without_admin_fixture(self):
        self.assertEqual(self.claim(self.owner)[0],200)
        self.assertEqual(self.req("/api/hosts",self.owner)[1]["hosts"][0]["host_id"],
                         "host.local")
        config=dict(mode="automatic",idle_only=False,gpu_max_percent=70,
            max_parallel_effects=2,timezone="UTC",weekdays=list(range(7)),
            start_minute=0,end_minute=1440)
        status,_=self.req("/api/host/rules",self.owner,
            dict(host_id="host.local",rule_id="rule.one",priority=1,
                 enabled=True,config=config))
        self.assertEqual(status,200)
        self.assertEqual(self.req("/api/host/effects",self.owner,
            dict(host_id="host.local",effect_id="effect.demo",
                 description="only metadata",enabled=True))[0],200)
        result=self.req("/api/host/effects/manual",self.owner,
            dict(host_id="host.local",effect_id="effect.demo"))
        self.assertEqual(result[0],200)
        self.assertEqual(result[1]["state"],"queued_mock")
        self.assertTrue(result[1]["reason"].startswith("hostjob."))
        jobs=self.req("/api/host/jobs?host_id=host.local",self.owner)
        self.assertEqual(jobs[0],200)
        self.assertEqual(len(jobs[1]["jobs"]),1)
        self.assertEqual(jobs[1]["jobs"][0]["state"],"queued")
        self.assertEqual(jobs[1]["jobs"][0]["job_id"],result[1]["reason"])
        self.assertEqual(self.req("/api/host/jobs?host_id=host.local",self.other)[0],403)
        reopened=HostCommitPolicy(IntegratedAlphaAdmission(self.store))
        self.assertEqual(reopened.list_host_jobs("host.local","user.owner"),
                         jobs[1]["jobs"])

    def test_owner_can_cancel_queued_job_without_execution(self):
        self.assertEqual(self.claim(self.owner)[0],200)
        self.assertEqual(self.req("/api/host/effects",self.owner,
            dict(host_id="host.local",effect_id="effect.demo",
                 description="metadata",enabled=True))[0],200)
        status,created=self.req("/api/host/effects/manual",self.owner,
            dict(host_id="host.local",effect_id="effect.demo"))
        self.assertEqual(status,200)
        job_id=created["reason"]
        payload=dict(host_id="host.local",job_id=job_id)
        self.assertEqual(self.req("/api/host/jobs/cancel",self.other,payload)[0],403)
        self.assertEqual(self.req("/api/host/jobs/cancel",self.owner,payload)[0],200)
        self.assertEqual(self.req("/api/host/jobs/cancel",self.owner,payload)[1]["reason"],
                         "already_cancelled")
        jobs=self.req("/api/host/jobs?host_id=host.local",self.owner)[1]["jobs"]
        self.assertEqual(jobs[0]["state"],"cancelled")
        self.assertEqual(self.policy.active_count("host.local"),0)

    def test_policy_preflight_waits_without_reservation(self):
        self.assertEqual(self.claim(self.owner)[0],200)
        self.assertEqual(self.req("/api/host/effects",self.owner,
            dict(host_id="host.local",effect_id="effect.demo",
                 description="metadata",enabled=True))[0],200)
        _,created=self.req("/api/host/effects/manual",self.owner,
            dict(host_id="host.local",effect_id="effect.demo"))
        job_id=created["reason"]
        payload=dict(host_id="host.local",job_id=job_id)
        self.assertEqual(self.req("/api/host/jobs/evaluate",self.other,payload)[0],403)
        status,decision=self.req("/api/host/jobs/evaluate",self.owner,payload)
        self.assertEqual(status,200)
        self.assertEqual(decision["state"],"waiting")
        self.assertEqual(decision["reason"],"no_enabled_rule")
        self.assertEqual(self.policy.active_count("host.local"),0)
        self.assertEqual(self.req("/api/host/jobs?host_id=host.local",
                                  self.owner)[1]["jobs"][0]["state"],"waiting")
        self.assertEqual(self.req("/api/host/jobs/cancel",self.owner,payload)[0],200)
        self.assertEqual(self.req("/api/host/jobs/evaluate",self.owner,payload)[0],403)

    def test_mock_reservation_enforces_limit_and_owner_release(self):
        self.assertEqual(self.claim(self.owner)[0],200)
        self.assertEqual(self.req("/api/host/effects",self.owner,
            dict(host_id="host.local",effect_id="effect.demo",
                 description="metadata",enabled=True))[0],200)
        config=dict(mode="automatic",idle_only=False,gpu_max_percent=None,
            max_parallel_effects=1,timezone="UTC",weekdays=list(range(7)),
            start_minute=0,end_minute=1440)
        self.assertEqual(self.req("/api/host/rules",self.owner,
            dict(host_id="host.local",rule_id="rule.one",priority=1,
                 enabled=True,config=config))[0],200)
        payloads=[]
        for _ in range(2):
            _,created=self.req("/api/host/effects/manual",self.owner,
                dict(host_id="host.local",effect_id="effect.demo"))
            payload=dict(host_id="host.local",job_id=created["reason"])
            self.assertEqual(self.req("/api/host/jobs/evaluate",self.owner,payload)[0],200)
            payloads.append(payload)
        self.assertEqual(self.req("/api/host/jobs/reserve",self.other,payloads[0])[0],403)
        status,first=self.req("/api/host/jobs/reserve",self.owner,payloads[0])
        self.assertEqual((status,first["state"]),(200,"reserved_mock"))
        self.assertEqual(self.policy.active_count("host.local"),1)
        self.assertEqual(self.req("/api/host/jobs/reserve",self.owner,payloads[0])[0],403)
        status,blocked=self.req("/api/host/jobs/reserve",self.owner,payloads[1])
        self.assertEqual((status,blocked["reason"]),(409,"parallel_limit_reached"))
        self.assertEqual(self.req("/api/host/jobs/cancel",self.owner,payloads[0])[0],403)
        self.assertEqual(self.req("/api/host/jobs/release",self.other,payloads[0])[0],403)
        self.assertEqual(self.req("/api/host/jobs/release",self.owner,payloads[0])[0],200)
        self.assertEqual(self.policy.active_count("host.local"),0)
        self.assertEqual(self.req("/api/host/jobs?host_id=host.local",self.owner)[1]["jobs"][0]["state"],"waiting")
        self.assertEqual(self.req("/api/host/jobs/reserve",self.owner,payloads[1])[0],200)

    def test_alpha_tabs_and_one_click_selectors_present(self):
        from private_alpha_gateway import PAGE
        for marker in ('id="alphaNav"', 'id="effectSelect"',
                       'id="hostJobSelect"', 'id="hostJobPanel"',
                       'id="jobActionOutput"', 'id="jobEffectSelect"', 'renderAlphaTabs()',
                       'loadSelectedEffect', 'button.disabled=!credential'):
            self.assertIn(marker,PAGE)

    def test_requester_may_cancel_own_waiting_or_reserved_job(self):
        self.assertEqual(self.claim(self.owner)[0],200)
        self.assertEqual(self.req("/api/host/effects",self.owner,
            dict(host_id="host.local",effect_id="effect.demo",
                 description="metadata",enabled=True))[0],200)
        _,created=self.req("/api/host/effects/manual",self.owner,
            dict(host_id="host.local",effect_id="effect.demo"))
        job_id=created["reason"]
        payload=dict(host_id="host.local",job_id=job_id)
        self.assertEqual(self.req("/api/host/jobs/cancel",self.owner,payload)[0],200)
        self.assertEqual(self.req("/api/host/jobs/cancel",self.other,payload)[0],403)

    def test_claim_requires_console_secret_and_cannot_steal(self):
        self.assertEqual(self.claim(self.owner,"wrong")[0],403)
        self.assertEqual(self.claim(self.owner)[0],200)
        self.assertEqual(self.claim(self.other)[0],403)
        self.assertEqual(self.req("/api/hosts",self.other)[1]["hosts"],[])

    def test_non_owner_cannot_define_or_start_effect(self):
        self.claim(self.owner)
        self.assertEqual(self.req("/api/host/effects",self.other,
            dict(host_id="host.local",effect_id="effect.demo",
                 description="untrusted",enabled=True))[0],403)
        self.assertEqual(self.req("/api/host/effects/manual",self.other,
            dict(host_id="host.local",effect_id="effect.demo"))[0],403)

    def test_unclaimed_host_has_no_effect_execution(self):
        self.assertEqual(self.req("/api/host/effects/manual",self.owner,
            dict(host_id="host.local",effect_id="effect.demo"))[0],403)
        self.assertEqual(self.req("/api/host/claim",payload=dict(
            host_id="host.local",bootstrap_secret="local-only-secret"))[0],401)

if __name__=="__main__":
    unittest.main()
