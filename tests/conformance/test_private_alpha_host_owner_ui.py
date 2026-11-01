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
                        'id="effectManual"'):
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
        self.assertEqual(self.req("/api/host/effects/manual",self.owner,
            dict(host_id="host.local",effect_id="effect.demo"))[1]["reason"],
            "manual_intent_only_no_execution")

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
