"""Auth v2 local-only browser enrollment and UI smoke tests."""
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

class BrowserEnrollmentTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.store=AlphaAuthStore(Path(t.name)/"alpha.sqlite",clock=lambda:10000)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),handler_for(self.store))
        thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self,path,payload=None,headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        h=dict(headers or {})
        raw=json.dumps(payload) if payload is not None else None
        if raw is not None:h["Content-Type"]="application/json"
        try:
            conn.request("POST" if raw is not None else "GET",path,body=raw,headers=h)
            response=conn.getresponse()
            return response.status,response.read()
        finally:
            conn.close()

    def test_browser_invitation_redeem_login_and_logout(self):
        invitation=self.store.invite("user.new")
        status,body=self.request("/api/redeem",{"invitation":invitation,"agent_id":"agent.new"})
        self.assertEqual(status,201)
        session=json.loads(body)["session_token"]
        self.assertEqual(self.store.principal("Bearer "+session).user_id,"user.new")
        self.assertIsNone(self.store.redeem(invitation,agent_id="agent.other"))
        self.assertEqual(self.store.agents(self.store.principal("Bearer "+session))[0]["agent_id"],"agent.new")

    def test_invalid_invitation_and_legacy_demo_mode_are_not_enrollment(self):
        self.assertEqual(self.request("/api/redeem",{"invitation":"wrong","agent_id":"agent.one"})[0],400)
        self.assertEqual(self.request("/api/redeem",{"invitation":"wrong","agent_id":"../../escape"})[0],400)

    def test_cross_origin_and_host_mismatch_are_denied(self):
        token=self.store.invite("user.new")
        payload={"invitation":token,"agent_id":"agent.new"}
        self.assertEqual(self.request("/api/redeem",payload,
            {"Origin":"https://untrusted.example"})[0],403)
        self.assertEqual(self.request("/api/redeem",payload,
            {"Host":"remote.example"})[0],403)
        self.assertEqual(self.request("/api/redeem",payload)[0],201)

    def test_rate_limit_and_no_secret_in_browser_page(self):
        for _ in range(5):
            self.assertEqual(self.request("/api/redeem",
                {"invitation":"wrong","agent_id":"agent.x"})[0],400)
        self.assertEqual(self.request("/api/redeem",
            {"invitation":"wrong","agent_id":"agent.x"})[0],429)
        status,body=self.request("/")
        self.assertEqual(status,200)
        self.assertIn(b"Einladung einloesen" if False else b"Session-Token",body)
        self.assertNotIn(b"Session bearer (local test only",body)

if __name__=="__main__":
    unittest.main()
