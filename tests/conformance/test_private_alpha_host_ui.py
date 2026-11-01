"""Alpha host administration API and UI smoke tests (local-only)."""
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
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy
from private_alpha_gateway import handler_for

class HostUiTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store=AlphaAuthStore(Path(temp.name)/"alpha.db",clock=lambda:10000)
        self.admin=self.store.redeem(self.store.invite("user.admin"),password="password-123456")
        self.other=self.store.redeem(self.store.invite("user.other"),password="password-123456")
        authority=IntegratedAlphaAdmission(self.store)
        authority.provision_host("host.one","operator.one")
        self.policy=HostCommitPolicy(authority)
        self.policy.add_admin_fixture("host.one","user.admin")
        self.store._host_policy=self.policy
        server=ThreadingHTTPServer(("127.0.0.1",0),handler_for(self.store))
        self.server=server
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,2)

    def req(self,path,session=None,body=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=5)
        headers={"Authorization":"Bearer "+session} if session else {}
        if body is not None:headers["Content-Type"]="application/json"
        try:
            conn.request("POST" if body is not None else "GET",path,
                         body=json.dumps(body) if body is not None else None,headers=headers)
            resp=conn.getresponse()
            return resp.status,resp.read()
        finally:conn.close()

    def test_ui_displays_all_host_controls(self):
        status,html=self.req("/")
        self.assertEqual(status,200)
        for marker in (b"hostParallel",b"hostGpu",b"hostMode",b"hostDays",
                       b"hostStart",b"hostEnd",b"hostIdle",b"hostRuleSelect",
                       b"hostSave",b"hostDelete",b"hostToggle"):
            self.assertIn(marker,html)

    def test_only_admin_sees_host_and_can_edit(self):
        self.assertEqual(json.loads(self.req("/api/hosts",self.other)[1])["hosts"],[])
        self.assertEqual(len(json.loads(self.req("/api/hosts",self.admin)[1])["hosts"]),1)
        config=dict(mode="automatic",idle_only=False,gpu_max_percent=60,
                    max_parallel_effects=2,timezone="UTC",weekdays=list(range(7)),
                    start_minute=0,end_minute=1440)
        payload=dict(host_id="host.one",rule_id="rule.one",priority=1,
                     enabled=True,config=config)
        self.assertEqual(self.req("/api/host/rules",self.other,payload)[0],403)
        self.assertEqual(self.req("/api/host/rules",self.admin,payload)[0],200)
        host=json.loads(self.req("/api/hosts",self.admin)[1])["hosts"][0]
        self.assertEqual(host["rules"][0]["config"]["max_parallel_effects"],2)
        self.assertEqual(self.req("/api/host/rules/delete",self.other,
            dict(host_id="host.one",rule_id="rule.one"))[0],403)
        self.assertEqual(self.req("/api/host/rules/delete",self.admin,
            dict(host_id="host.one",rule_id="rule.one"))[0],200)

    def test_unauthenticated_denied(self):
        self.assertEqual(self.req("/api/hosts")[0],401)
        self.assertEqual(self.req("/api/host/rules",body={})[0],401)

if __name__=="__main__":
    unittest.main()
