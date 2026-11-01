"""Private Alpha Auth v1: isolated SQLite invite/session/agent simulation.

Not a public identity provider: local trusted CLI provisions and redeems
invites. No user-submitted workflow executes. Never expose this prototype yet.
"""
import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass

def digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def ident(value):
    return type(value) is str and 1 <= len(value) <= 128 and all(
        c.isascii() and (c.isalnum() or c in "._-") for c in value)

@dataclass(frozen=True)
class AlphaPrincipal:
    user_id: str
    agent_id: str

class AlphaAuthStore:
    def __init__(self, database, *, clock=None):
        self.database = str(database)
        self.clock = clock or time.time
        with self._tx() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS alpha_invites(
                invitation_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE,
                expires_at INTEGER NOT NULL, redeemed INTEGER NOT NULL DEFAULT 0,
                revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS alpha_users(
                user_id TEXT PRIMARY KEY, disabled INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS alpha_agents(
                agent_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS alpha_sessions(
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS alpha_jobs(
                job_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, agent_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL, action TEXT NOT NULL,
                UNIQUE(user_id,idempotency_key));""")

    def _tx(self):
        # Separate context manager implemented below; IMMEDIATE serializes
        # invite redemption, session revocation, and job decisions.
        return _Transaction(self.database)

    def invite(self, user_id, *, ttl=3600):
        if not ident(user_id) or type(ttl) is not int or not 1 <= ttl <= 86400:
            raise ValueError("invalid invitation")
        token = secrets.token_urlsafe(36)
        with self._tx() as db:
            db.execute("INSERT INTO alpha_invites VALUES(?,?,?,0,0)",
                       (digest(token),user_id,int(self.clock())+ttl))
        return token

    def redeem(self, token, *, agent_id, session_ttl=900):
        if (type(token) is not str or not token or not ident(agent_id)
                or type(session_ttl) is not int or not 1 <= session_ttl <= 3600):
            return None
        session = secrets.token_urlsafe(36)
        with self._tx() as db:
            row = db.execute("""SELECT user_id,expires_at,redeemed,revoked
                FROM alpha_invites WHERE invitation_hash=?""", (digest(token),)).fetchone()
            if not row or row[1] <= self.clock() or row[2] or row[3]:
                return None
            user = row[0]
            if db.execute("SELECT 1 FROM alpha_agents WHERE agent_id=?",
                          (agent_id,)).fetchone():
                return None
            db.execute("UPDATE alpha_invites SET redeemed=1 WHERE invitation_hash=?",
                       (digest(token),))
            db.execute("INSERT INTO alpha_users(user_id) VALUES(?)", (user,))
            db.execute("INSERT INTO alpha_agents(agent_id,user_id) VALUES(?,?)",
                       (agent_id,user))
            db.execute("INSERT INTO alpha_sessions VALUES(?,?,?,0)",
                       (digest(session),user,int(self.clock())+session_ttl))
        return session

    def principal(self, authorization):
        if (type(authorization) is not str or not authorization.startswith("Bearer ")
                or not 1 <= len(authorization[7:]) <= 256):
            return None
        with self._tx() as db:
            row = db.execute("""SELECT s.user_id,a.agent_id FROM alpha_sessions s
                JOIN alpha_users u ON u.user_id=s.user_id
                JOIN alpha_agents a ON a.user_id=s.user_id
                WHERE s.token_hash=? AND s.revoked=0 AND s.expires_at>?
                  AND u.disabled=0 AND a.disabled=0
                ORDER BY a.agent_id LIMIT 1""",
                (digest(authorization[7:]),self.clock())).fetchone()
            return AlphaPrincipal(*row) if row else None

    def revoke_session(self, authorization):
        if (type(authorization) is not str or not authorization.startswith("Bearer ")
                or not 1 <= len(authorization[7:]) <= 256):
            return False
        with self._tx() as db:
            result = db.execute("UPDATE alpha_sessions SET revoked=1 WHERE token_hash=? AND revoked=0",
                                (digest(authorization[7:]),))
            return result.rowcount == 1

    def disable_user(self, user_id):
        if not ident(user_id):
            raise ValueError("invalid user")
        with self._tx() as db:
            changed = db.execute("UPDATE alpha_users SET disabled=1 WHERE user_id=?",
                                 (user_id,)).rowcount
            db.execute("UPDATE alpha_sessions SET revoked=1 WHERE user_id=?",
                       (user_id,))
        return changed == 1

    def agents(self, principal):
        with self._tx() as db:
            rows = db.execute("""SELECT agent_id FROM alpha_agents
                WHERE user_id=? AND disabled=0 ORDER BY agent_id""",
                (principal.user_id,)).fetchall()
            return [{"agent_id": agent, "owner":principal.user_id,
                     "allowed_actions":["demo.echo"]} for (agent,) in rows]

    def jobs(self, principal):
        with self._tx() as db:
            rows = db.execute("""SELECT job_id,user_id,agent_id,action
                FROM alpha_jobs WHERE user_id=? ORDER BY rowid""",
                (principal.user_id,)).fetchall()
        return [{"job_id":job,"user_id":user,"agent_id":agent,"action":action,
                 "state":"simulated_no_effect"} for job,user,agent,action in rows]

    def submit(self, principal, payload):
        if (type(payload) is not dict or set(payload) != {"action","idempotency_key"}
                or payload["action"] != "demo.echo" or not ident(payload["idempotency_key"])):
            return 400, {"error":"invalid_simulated_action"}
        with self._tx() as db:
            active = db.execute("""SELECT 1 FROM alpha_users u
                JOIN alpha_agents a ON a.user_id=u.user_id
                WHERE u.user_id=? AND u.disabled=0 AND a.agent_id=? AND a.disabled=0""",
                (principal.user_id,principal.agent_id)).fetchone()
            if not active:
                return 403, {"error":"agent_disabled"}
            existing = db.execute("""SELECT job_id,agent_id,action FROM alpha_jobs
                WHERE user_id=? AND idempotency_key=?""",
                (principal.user_id,payload["idempotency_key"])).fetchone()
            if existing:
                if existing[1:] != (principal.agent_id,payload["action"]):
                    return 409, {"error":"idempotency_conflict"}
                job = existing[0]
                status = 200
            else:
                count = db.execute("SELECT count(*) FROM alpha_jobs WHERE user_id=?",
                                   (principal.user_id,)).fetchone()[0]
                if count >= 5:
                    return 429, {"error":"simulation_quota_exceeded"}
                job = "sim." + secrets.token_hex(12)
                db.execute("INSERT INTO alpha_jobs VALUES(?,?,?,?,?)",
                           (job,principal.user_id,principal.agent_id,
                            payload["idempotency_key"],payload["action"]))
                status = 201
            return status, {"job_id":job,"user_id":principal.user_id,
                            "agent_id":principal.agent_id,"action":"demo.echo",
                            "state":"simulated_no_effect"}

class _Transaction:
    def __init__(self, database):
        self.database = database
    def __enter__(self):
        self.db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        try:
            self.db.execute("PRAGMA busy_timeout=10000")
            self.db.execute("BEGIN IMMEDIATE")
            return self.db
        except BaseException:
            self.db.close()
            raise
    def __exit__(self, kind, error, tb):
        try:
            if kind is None:
                self.db.commit()
            else:
                self.db.rollback()
        finally:
            self.db.close()
