"""Local-only Minglefield Private Alpha gateway, simulation ONLY.

No B2 effect invocation, no ComfyUI, no password enrollment and no external
listener. Static tokens are TEST FIXTURES, not production authentication.
Do NOT expose this prototype via Tailscale Serve to invited users yet.
"""
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import time
from threading import Lock
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

MAX_BODY = 4096
MAX_JOBS_PER_USER = 5

PAGE = """<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Minglefield — Local Alpha / Private Alpha (lokal)</title>
<style>body{font:16px system-ui;margin:2rem auto;max-width:42rem;padding:0 1rem}
input,button{font:inherit;padding:.5rem;margin:.3rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}
fieldset{margin:1rem 0}button{cursor:pointer}</style>
<h1>Minglefield Private Alpha</h1>
<p>Nur lokale Simulation. Kein Tailscale Serve und keine echten Effekte.</p>
<fieldset><legend>1. Einladung einlösen (nur Auth-v2-Test)</legend>
<label>Einladungscode <input id="invite" type="password" autocomplete="off"></label>
<label>Gewünschte Agenten-ID <input id="agent" placeholder="agent.alice"></label>
<button id="redeem">Einladung einlösen</button>
<p><small>Der Betreiber erstellt Einladungscodes weiterhin lokal per PowerShell.
Der erzeugte Session-Token bleibt nur in diesem Browsertab gespeichert.</small></p></fieldset>
<fieldset><legend>2. Anmelden</legend>
<label>Session-Token (kein Einladungscode) <input id="token" type="password" autocomplete="off"></label>
<button id="connect">Connect</button><button id="logout">Logout</button></fieldset>
<fieldset><legend>3. Simulieren</legend>
<button id="create">Simulate action</button><button id="refresh">Jobs aktualisieren</button></fieldset>
<p id="sessionStatus" role="status" aria-live="polite">Keine aktive Session.</p>
<pre id="output" aria-live="polite">Einladung einlösen oder gültigen Session-Token eingeben.</pre>
<script>
let credential="";
let expiresAt=0;
const out=document.getElementById("output");
const statusLine=document.getElementById("sessionStatus");
const updateStatus=()=>{
  if(!credential){statusLine.textContent="Keine aktive Session.";return;}
  if(!expiresAt){statusLine.textContent="Session-Token im Tab aktiv (Ablaufzeit nicht bekannt).";return;}
  const seconds=Math.max(0,Math.ceil((expiresAt-Date.now())/1000));
  statusLine.textContent=seconds>0?
    "Session im Tab aktiv. Verbleibend bei letzter Aktualisierung: "+seconds+" Sekunden.":
    "Session vermutlich abgelaufen – bitte neu anmelden.";
};
async function request(path,options={}){
  const headers={...(options.headers||{})};
  if(credential)headers.Authorization="Bearer "+credential;
  const response=await fetch(path,{...options,headers,cache:"no-store"});
  return {status:response.status,data:await response.json()};
}
const show=v=>out.textContent=JSON.stringify(v,null,2);
const handleUnauthorized=(reply)=>{
  if(reply.status===401){credential="";expiresAt=0;updateStatus();
    statusLine.textContent="Session ungültig, widerrufen oder abgelaufen. Erneut anmelden.";}
};
const api=async(path,body)=>request(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
const refresh=async()=>{
  if(!credential){show({message:"Bitte zuerst anmelden."});return;}
  const agents=await request("/api/agents");
  const jobs=await request("/api/jobs");
  handleUnauthorized(agents);
  handleUnauthorized(jobs);
  updateStatus();
  show({agents,jobs});
};
document.getElementById("redeem").onclick=async()=>{
  const secret=document.getElementById("invite").value;
  const agent_id=document.getElementById("agent").value;
  document.getElementById("invite").value="";
  const result=await api("/api/redeem",{invitation:secret,agent_id});
  if(result.status===201){
    credential=result.data.session_token;
    expiresAt=Date.now()+result.data.expires_in*1000;
    updateStatus();
    show({status:201,message:"Session aktiviert. Connect zeigt Benutzer und Agent getrennt."});
  }
  else show(result);
};
document.getElementById("connect").onclick=async()=>{
  const supplied=document.getElementById("token").value;
  if(supplied){credential=supplied;expiresAt=0;updateStatus();}
  document.getElementById("token").value="";
  await refresh();
};
document.getElementById("refresh").onclick=refresh;
document.getElementById("create").onclick=async()=>{
  if(!credential){show({message:"Bitte zuerst anmelden."});return;}
  const result=await api("/api/jobs",{action:"demo.echo",idempotency_key:crypto.randomUUID()});
  handleUnauthorized(result);
  show(result);
};
document.getElementById("logout").onclick=async()=>{
  const result=credential?await request("/api/logout",{method:"POST"}):{status:401};
  credential="";expiresAt=0;updateStatus();
  show(result);
};
</script></html>"""


@dataclass(frozen=True)
class TestPrincipal:
    user_id: str
    agent_id: str


class AlphaSimulation:
    def __init__(self, tokens):
        """Caller supplies generated test-only bearer tokens."""
        if (type(tokens) is not dict or not tokens
                or any(type(t) is not str or len(t) < 32
                       or type(p) is not TestPrincipal or not p.user_id or not p.agent_id
                       for t, p in tokens.items())):
            raise ValueError("invalid test-only identities")
        if len(set(tokens)) != len(tokens):
            raise ValueError("duplicate token")
        self._digests = {hashlib.sha256(t.encode()).digest(): p for t, p in tokens.items()}
        self._jobs = {}
        from threading import Lock
        self._lock = Lock()

    def principal(self, authorization):
        if type(authorization) is not str or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:]
        if not token or len(token) > 256:
            return None
        digest = hashlib.sha256(token.encode()).digest()
        for known, principal in self._digests.items():
            if hmac.compare_digest(digest, known):
                return principal
        return None

    def agents(self, principal):
        return [{"agent_id": principal.agent_id, "owner": principal.user_id,
                 "allowed_actions": ["demo.echo"]}]

    def jobs(self, principal):
        with self._lock:
            return [dict(value) for (user, _), value in self._jobs.items()
                    if user == principal.user_id]

    def submit(self, principal, payload):
        if (type(payload) is not dict or set(payload) != {"action", "idempotency_key"}
                or payload["action"] != "demo.echo"
                or type(payload["idempotency_key"]) is not str
                or not 1 <= len(payload["idempotency_key"]) <= 128):
            return 400, {"error": "invalid_simulated_action"}
        with self._lock:
            key = (principal.user_id, payload["idempotency_key"])
            if key in self._jobs:
                return 200, dict(self._jobs[key])
            if sum(u == principal.user_id for u, _ in self._jobs) >= MAX_JOBS_PER_USER:
                return 429, {"error": "simulation_quota_exceeded"}
            record = {"job_id": "sim." + secrets.token_hex(12),
                      "user_id": principal.user_id, "agent_id": principal.agent_id,
                      "action": "demo.echo", "state": "simulated_no_effect"}
            self._jobs[key] = record
            return 201, dict(record)


def handler_for(service):
    # In-memory abuse throttle for the LOCAL browser onboarding prototype.
    attempts = {}
    throttle = Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Never log Authorization or request bodies.
            return

        def reply(self, status, payload):
            body = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                page = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
                self.end_headers()
                self.wfile.write(page)
                return
            if path == "/health":
                self.reply(200, {"status": "simulation_only"})
                return
            principal = service.principal(self.headers.get("Authorization"))
            if not principal:
                self.reply(401, {"error": "unauthorized"})
                return
            if path == "/api/agents":
                self.reply(200, {"agents": service.agents(principal)})
            elif path == "/api/jobs":
                self.reply(200, {"jobs": service.jobs(principal)})
            else:
                self.reply(404, {"error": "not_found"})

        def do_POST(self):
            path = urlsplit(self.path).path
            if path not in ("/api/jobs", "/api/logout", "/api/redeem"):
                self.reply(404, {"error": "not_found"})
                return
            if path == "/api/redeem":
                # Deliberately loopback-only. Not a remote enrollment API.
                if not hasattr(service, "redeem") or self.client_address[0] not in ("127.0.0.1", "::1"):
                    self.reply(404, {"error": "unavailable"})
                    return
                origin = self.headers.get("Origin")
                host = self.headers.get("Host", "")
                if (host not in ("127.0.0.1:" + str(self.server.server_port),
                                 "localhost:" + str(self.server.server_port))
                        or (origin is not None and origin not in (
                            "http://127.0.0.1:" + str(self.server.server_port),
                            "http://localhost:" + str(self.server.server_port)))):
                    self.reply(403, {"error": "local_origin_required"})
                    return
                with throttle:
                    now = time.monotonic()
                    recent = [t for t in attempts.get("local", []) if now - t < 60]
                    if len(recent) >= 5:
                        attempts["local"] = recent
                        self.reply(429, {"error": "try_again_later"})
                        return
                    recent.append(now)
                    attempts["local"] = recent
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "json_required"})
                    return
                raw_length = self.headers.get("Content-Length", "")
                if not raw_length.isdecimal() or int(raw_length) > MAX_BODY:
                    self.reply(413, {"error": "invalid_body_length"})
                    return
                try:
                    data = json.loads(self.rfile.read(int(raw_length)))
                except (UnicodeDecodeError, ValueError):
                    self.reply(400, {"error": "invalid_json"})
                    return
                if type(data) is not dict or set(data) != {"invitation", "agent_id"}:
                    self.reply(400, {"error": "invalid_registration"})
                    return
                session = service.redeem(data["invitation"], agent_id=data["agent_id"])
                if session is None:
                    self.reply(400, {"error": "invitation_invalid_or_used"})
                    return
                self.reply(201, {"session_token": session, "expires_in": 900})
                return
            principal = service.principal(self.headers.get("Authorization"))
            if not principal:
                self.reply(401, {"error": "unauthorized"})
                return
            if path == "/api/logout":
                revoke = getattr(service, "revoke_session", None)
                if revoke is None:
                    self.reply(404, {"error": "unavailable"})
                else:
                    revoke(self.headers.get("Authorization"))
                    self.reply(200, {"status": "session_revoked"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self.reply(415, {"error": "json_required"})
                return
            length = self.headers.get("Content-Length", "")
            if not length.isdecimal() or int(length) > MAX_BODY:
                self.reply(413, {"error": "invalid_body_length"})
                return
            try:
                body = json.loads(self.rfile.read(int(length)))
            except (UnicodeDecodeError, ValueError):
                self.reply(400, {"error": "invalid_json"})
                return
            status, result = service.submit(principal, body)
            self.reply(status, result)
    return Handler


def run_local():
    parser = argparse.ArgumentParser(description="LOCAL simulation only; NEVER publish as-is")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--auth-db", help="local-only SQLite test identity store")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024..65535")
    if args.auth_db:
        from private_alpha_auth import AlphaAuthStore
        service = AlphaAuthStore(args.auth_db)
        token = None
    else:
        token = secrets.token_urlsafe(36)
        service = AlphaSimulation({token: TestPrincipal("demo.local", "agent.demo")})
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(service))
    print("LOCAL-ONLY simulation, no real effects. DO NOT EXPOSE VIA SERVE YET.")
    if token:
        print("Local test token (do not share):", token, flush=True)
    else:
        print("Auth v1 SQLite mode: provision users using private_alpha_admin.py.", flush=True)
    print("URL: http://127.0.0.1:" + str(args.port), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    run_local()
