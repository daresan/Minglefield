"""Local HTTP lifecycle: account, owned agents, external commissioned agents."""
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

class DelegationHTTPTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store=AlphaAuthStore(Path(tmp.name)/"alpha.db",clock=lambda:10000)
        self.http=ThreadingHTTPServer(("127.0.0.1",0),handler_for(self.store))
        t=threading.Thread(target=self.http.serve_forever,daemon=True)
        t.start()
        self.addCleanup(t.join,2)
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def call(self,method,path,payload=None,token=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.http.server_port,timeout=3)
        headers={}
        if token is not None:headers["Authorization"]="Bearer "+token
        if payload is not None:headers["Content-Type"]="application/json"
        try:
            conn.request(method,path,
                         body=json.dumps(payload) if payload is not None else None,
                         headers=headers)
            res=conn.getresponse()
            return res.status,json.loads(res.read())
        finally:
            conn.close()

    def test_register_then_two_owned_agents_then_external_delegate(self):
        owner_invite=self.store.invite("user.owner")
        friend_invite=self.store.invite("user.friend")
        owner_response=self.call("POST","/api/redeem",{
            "invitation":owner_invite,"password":"local-test-password-123"})
        self.assertEqual(owner_response[0],201)
        owner=owner_response[1]["session_token"]
        friend_response=self.call("POST","/api/redeem",{
            "invitation":friend_invite,"password":"local-test-password-123"})
        self.assertEqual(friend_response[0],201)
        friend=friend_response[1]["session_token"]
        self.assertEqual(self.call("GET","/api/agents",token=owner)[1]["agents"],[])
        for name in ("agent.owned1","agent.owned2"):
            self.assertEqual(self.call("POST","/api/agents",{
                "agent_id":name},token=owner)[0],201)
        self.assertEqual(self.call("GET","/api/agents",token=friend)[1]["agents"],[])
        self.assertEqual(self.call("POST","/api/jobs",{
            "agent_id":"agent.owned1","action":"demo.echo",
            "idempotency_key":"before-grant"},token=friend)[0],403)
        self.assertEqual(self.call("POST","/api/grants",{
            "agent_id":"agent.owned1","grantee_user_id":"user.friend",
            "revoke":False},token=friend)[0],403)
        self.assertEqual(self.call("POST","/api/grants",{
            "agent_id":"agent.owned1","grantee_user_id":"user.friend",
            "revoke":False},token=owner)[0],200)
        delegated=self.call("GET","/api/agents",token=friend)[1]["agents"]
        self.assertEqual(delegated[0]["relationship"],"delegated")
        self.assertEqual(delegated[0]["owner"],"user.owner")
        self.assertEqual(self.call("POST","/api/jobs",{
            "agent_id":"agent.owned1","action":"demo.echo",
            "idempotency_key":"after-grant"},token=friend)[0],201)
        self.assertEqual(self.call("POST","/api/grants",{
            "agent_id":"agent.owned1","grantee_user_id":"user.friend",
            "revoke":True},token=owner)[0],200)
        self.assertEqual(self.call("POST","/api/jobs",{
            "agent_id":"agent.owned1","action":"demo.echo",
            "idempotency_key":"after-revoke"},token=friend)[0],403)

if __name__=="__main__":
    unittest.main()
