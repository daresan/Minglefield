"""Auth v1 + local HTTP gateway integration tests; no real effects."""
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

class AlphaAuthHTTPTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.now=10000
        self.store=AlphaAuthStore(Path(tmp.name)/"auth.sqlite",clock=lambda:self.now)
        tokens=[]
        for user,agent in (("user.one","agent.one"),("user.two","agent.two")):
            tokens.append(self.store.redeem(self.store.invite(user),agent_id=agent))
        self.tokens=tokens
        self.server=ThreadingHTTPServer(("127.0.0.1",0),handler_for(self.store))
        thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(thread.join,2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self,method,path,token=None,data=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        headers={}
        if token:
            headers["Authorization"]="Bearer "+token
        if data is not None:
            headers["Content-Type"]="application/json"
            data=json.dumps(data)
        try:
            conn.request(method,path,body=data,headers=headers)
            response=conn.getresponse()
            return response.status,json.loads(response.read())
        finally:
            conn.close()

    def test_separate_remote_like_http_identities(self):
        a,b=self.tokens
        status,agent=self.call("GET","/api/agents",a)
        self.assertEqual(status,200)
        self.assertEqual(agent["agents"][0]["agent_id"],"agent.one")
        status,job=self.call("POST","/api/jobs",a,
                             {"action":"demo.echo","idempotency_key":"one"})
        self.assertEqual(status,201)
        self.assertEqual(job["state"],"simulated_no_effect")
        self.assertEqual(self.call("GET","/api/jobs",b)[1]["jobs"],[])
        self.assertEqual(self.call("GET","/api/jobs",a)[1]["jobs"][0]["job_id"],
                         job["job_id"])

    def test_logout_and_user_disable_take_effect(self):
        a,b=self.tokens
        self.assertEqual(self.call("POST","/api/logout",a)[0],200)
        self.assertEqual(self.call("GET","/api/agents",a)[0],401)
        self.assertTrue(self.store.disable_user("user.two"))
        self.assertEqual(self.call("GET","/api/jobs",b)[0],401)

    def test_expired_session_and_unknown_user_denied(self):
        a,b=self.tokens
        self.now+=901
        self.assertEqual(self.call("GET","/api/jobs",a)[0],401)
        self.assertEqual(self.call("POST","/api/jobs",b,
                         {"action":"demo.echo","idempotency_key":"one"})[0],401)

if __name__=="__main__":
    unittest.main()
