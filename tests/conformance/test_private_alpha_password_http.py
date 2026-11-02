"""Private Alpha v4 local HTTP password enrollment and repeat-login tests."""
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

class PasswordHTTPTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.now=10000
        self.store=AlphaAuthStore(Path(t.name)/"alpha.sqlite",clock=lambda:self.now)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),handler_for(self.store))
        worker=threading.Thread(target=self.server.serve_forever,daemon=True)
        worker.start()
        self.addCleanup(worker.join,2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self,path,payload=None,token=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        headers={}
        if token:
            headers["Authorization"]="Bearer "+token
        if payload is not None:
            headers["Content-Type"]="application/json"
        try:
            conn.request("POST" if payload is not None else "GET",path,
                         body=json.dumps(payload) if payload is not None else None,
                         headers=headers)
            resp=conn.getresponse()
            return resp.status,json.loads(resp.read())
        finally:
            conn.close()

    def test_new_user_password_login_after_expiration(self):
        invitation=self.store.invite("user.v4")
        status,result=self.request("/api/redeem",
            {"invitation":invitation,"agent_id":"agent.v4",
             "password":"local-test-password-123"})
        self.assertEqual(status,201)
        old=result["session_token"]
        self.now+=901
        self.assertEqual(self.request("/api/agents",token=old)[0],401)
        status,result=self.request("/api/login",
            {"user_id":"user.v4","password":"local-test-password-123"})
        self.assertEqual(status,200)
        self.assertEqual(self.request("/api/agents",token=result["session_token"])[1]["agents"][0]["agent_id"],
                         "agent.v4")

    def test_redeem_logout_then_login_same_password(self):
        invitation=self.store.invite("user.daniel")
        password="test-login-passphrase-123"
        status,registration=self.request("/api/redeem",
            {"invitation":invitation,"agent_id":"agent.daniel","password":password})
        self.assertEqual(status,201)
        old=registration["session_token"]
        self.assertEqual(self.request("/api/agents",token=old)[0],200)
        # Logout is POST with no body; use a direct connection to simulate UI.
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        try:
            conn.request("POST","/api/logout",headers={"Authorization":"Bearer "+old})
            response=conn.getresponse()
            self.assertEqual(response.status,200)
            response.read()
        finally:
            conn.close()
        self.assertEqual(self.request("/api/agents",token=old)[0],401)
        status,logged_in=self.request("/api/login",
            {"user_id":"user.daniel","password":password})
        self.assertEqual(status,200,logged_in)
        fresh=logged_in["session_token"]
        self.assertNotEqual(fresh,old)
        status,agents=self.request("/api/agents",token=fresh)
        self.assertEqual(status,200)
        self.assertEqual(agents["agents"][0]["agent_id"],"agent.daniel")

    def test_wrong_password_and_missing_account_denied(self):
        invite=self.store.invite("user.v4")
        self.assertEqual(self.request("/api/redeem",
            {"invitation":invite,"agent_id":"agent.v4",
             "password":"local-test-password-123"})[0],201)
        self.assertEqual(self.request("/api/login",
            {"user_id":"user.v4","password":"incorrect-password-12"})[0],401)
        self.assertEqual(self.request("/api/login",
            {"user_id":"user.missing","password":"incorrect-password-12"})[0],401)

    def test_legacy_password_migration_requires_live_session(self):
        session=self.store.redeem(self.store.invite("user.old"),agent_id="agent.old")
        self.assertEqual(self.request("/api/password/set",
            {"password":"local-test-password-123"})[0],403)
        self.assertEqual(self.request("/api/password/set",
            {"password":"local-test-password-123"},token=session)[0],200)
        self.now+=901
        self.assertEqual(self.request("/api/login",
            {"user_id":"user.old","password":"local-test-password-123"})[0],200)

if __name__=="__main__":
    unittest.main()
