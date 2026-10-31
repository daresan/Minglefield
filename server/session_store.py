"""MAP v0.3 local credential/session prototype.

Not a production identity provider. Registration is a privileged bootstrap action;
never expose enroll() to unauthenticated callers. Bearer tokens are secrets.
"""
import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Session:
    user_id: str
    agent_id: str
    delegation_id: str | None
    expires_at: int


class SessionStore:
    def __init__(self, database, *, clock=None):
        self.database = str(database)
        self.clock = clock if clock is not None else time.time
        with self._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS auth_principals (
                user_id TEXT PRIMARY KEY, credential_hash TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0)""")
            db.execute("""CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL, delegation_id TEXT,
                expires_at INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES auth_principals(user_id))""")
            db.execute("CREATE INDEX IF NOT EXISTS auth_sessions_user ON auth_sessions(user_id)")

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def enroll(self, user_id):
        """Privileged bootstrap only: returns one-time credential to secure caller."""
        if not isinstance(user_id, str) or not user_id or len(user_id) > 128:
            raise ValueError("invalid user_id")
        credential = secrets.token_urlsafe(32)
        with self._transaction() as db:
            db.execute("INSERT INTO auth_principals(user_id,credential_hash) VALUES(?,?)",
                       (user_id, _digest(credential)))
        return credential

    def issue(self, *, user_id, credential, agent_id, delegation_id=None, ttl_seconds=900):
        """Authenticate enrolled user before issuing a short-lived bearer session.

        Agent/delegation association is only a binding claim; caller MUST validate
        authorization against the Policy Engine before executing any action.
        """
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 3600:
            raise ValueError("ttl_seconds must be 1..3600")
        if not isinstance(agent_id, str) or not agent_id or len(agent_id) > 128:
            raise ValueError("invalid agent_id")
        if delegation_id is not None and (not isinstance(delegation_id, str) or not delegation_id):
            raise ValueError("invalid delegation_id")
        with self._transaction() as db:
            row = db.execute("SELECT credential_hash,disabled FROM auth_principals WHERE user_id=?",
                             (user_id,)).fetchone()
            if not row or row[1] or not isinstance(credential, str) or not hmac.compare_digest(
                    row[0], _digest(credential)):
                return None
            token = secrets.token_urlsafe(32)
            db.execute("""INSERT INTO auth_sessions
                (token_hash,user_id,agent_id,delegation_id,expires_at)
                VALUES(?,?,?,?,?)""",
                (_digest(token),user_id,agent_id,delegation_id,int(self.clock())+ttl_seconds))
            return token

    def verify(self, token, *, agent_id=None, delegation_id=None):
        if not isinstance(token, str) or not token:
            return None
        with self._transaction() as db:
            row = db.execute("""SELECT s.user_id,s.agent_id,s.delegation_id,
                                       s.expires_at,s.revoked,p.disabled
                                FROM auth_sessions s JOIN auth_principals p
                                ON p.user_id=s.user_id WHERE s.token_hash=?""",
                             (_digest(token),)).fetchone()
            if not row or row[4] or row[5] or int(self.clock()) >= row[3]:
                return None
            if agent_id is not None and row[1] != agent_id:
                return None
            if delegation_id is not None and row[2] != delegation_id:
                return None
            return Session(row[0],row[1],row[2],row[3])

    def revoke(self, token, *, credential, user_id):
        """Require both authenticated owner credential and target token."""
        if not isinstance(token, str) or not token or not isinstance(credential, str):
            return False
        with self._transaction() as db:
            row = db.execute("SELECT credential_hash,disabled FROM auth_principals WHERE user_id=?",
                             (user_id,)).fetchone()
            if not row or row[1] or not hmac.compare_digest(row[0], _digest(credential)):
                return False
            result = db.execute("UPDATE auth_sessions SET revoked=1 WHERE token_hash=? AND user_id=?",
                                (_digest(token),user_id))
            return result.rowcount == 1

    def disable_user(self, user_id, *, credential):
        """Prototype self-disable; administrative recovery not implemented."""
        if not isinstance(credential, str):
            return False
        with self._transaction() as db:
            row = db.execute("SELECT credential_hash,disabled FROM auth_principals WHERE user_id=?",
                             (user_id,)).fetchone()
            if not row or row[1] or not hmac.compare_digest(row[0], _digest(credential)):
                return False
            db.execute("UPDATE auth_principals SET disabled=1 WHERE user_id=?", (user_id,))
            db.execute("UPDATE auth_sessions SET revoked=1 WHERE user_id=?", (user_id,))
            return True
