"""Integrated LOCAL SEC-01 admission fixture using the Private Alpha SQLite DB.

No network endpoint, executable capabilities, real effects, ComfyUI or Serve.
A single BEGIN IMMEDIATE transaction reads the actual Private Alpha sessions,
owners, agents and grants alongside host placement and the admission ledger.
The authenticated caller is identified only by its Alpha session bearer.
Host fixture administration is trusted local setup, never exposed to users.
"""
import json
import sqlite3
from dataclasses import dataclass

from private_alpha_auth import AlphaAuthStore, ident


@dataclass(frozen=True)
class LocalAdmission:
    accepted: bool
    reason: str


class IntegratedAlphaAdmission:
    def __init__(self, store):
        if type(store) is not AlphaAuthStore:
            raise TypeError("requires private alpha auth store")
        self.store = store
        with store._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS alpha_executor_hosts(
                host_id TEXT PRIMARY KEY, operator_id TEXT NOT NULL,
                active INTEGER NOT NULL CHECK(active IN (0,1)))""")
            db.execute("""CREATE TABLE IF NOT EXISTS alpha_agent_host_assignments(
                agent_id TEXT NOT NULL, host_id TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                PRIMARY KEY(agent_id,host_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS alpha_sec01_admissions(
                effect_key TEXT PRIMARY KEY, binding TEXT NOT NULL)""")

    def provision_host(self, host_id, operator_id):
        """Trusted local fixture; cannot be called by an alpha requester API."""
        if not ident(host_id) or not ident(operator_id):
            raise ValueError("invalid host fixture")
        with self.store._tx() as db:
            db.execute("INSERT INTO alpha_executor_hosts VALUES(?,?,1)",
                       (host_id,operator_id))

    def assign_agent(self, agent_id, host_id, *, enabled=True):
        """Trusted fixture models separately approved agent-to-host placement."""
        if not ident(agent_id) or not ident(host_id) or type(enabled) is not bool:
            raise ValueError("invalid assignment fixture")
        with self.store._tx() as db:
            if not db.execute("SELECT 1 FROM alpha_agents WHERE agent_id=?",
                              (agent_id,)).fetchone():
                raise ValueError("unknown agent")
            if not db.execute("SELECT 1 FROM alpha_executor_hosts WHERE host_id=?",
                              (host_id,)).fetchone():
                raise ValueError("unknown host")
            db.execute("""INSERT INTO alpha_agent_host_assignments
                VALUES(?,?,?) ON CONFLICT(agent_id,host_id)
                DO UPDATE SET enabled=excluded.enabled""",
                (agent_id,host_id,int(enabled)))

    def set_host_active(self, host_id, active):
        if not ident(host_id) or type(active) is not bool:
            raise ValueError("invalid host state")
        with self.store._tx() as db:
            changed=db.execute("""UPDATE alpha_executor_hosts SET active=?
                WHERE host_id=?""",(int(active),host_id)).rowcount
            if changed!=1:
                raise ValueError("unknown host")

    def admit(self, authorization, *, effect_key, job_id, fingerprint,
              agent_id, owner_id, executor_id, host_id, action="demo.echo"):
        """Check all authorities and record ONE decision in a single transaction.

        A result is only a historical simulated admission, NOT permission to
        invoke an external effect. A repeated key cannot create a new effect.
        """
        fields=(effect_key,job_id,fingerprint,agent_id,owner_id,executor_id,host_id)
        if not all(ident(x) for x in fields) or action!="demo.echo":
            return LocalAdmission(False,"invalid_intent")
        with self.store._tx() as db:
            requester=self.store._active_user(db,authorization)
            if requester is None:
                return LocalAdmission(False,"session_invalid")
            binding=json.dumps([job_id,fingerprint,requester,agent_id,owner_id,
                                executor_id,host_id,action],
                               separators=(",",":"),ensure_ascii=True)
            previous=db.execute("""SELECT binding FROM alpha_sec01_admissions
                WHERE effect_key=?""",(effect_key,)).fetchone()
            if previous is not None:
                return (LocalAdmission(True,"already_admitted_no_new_effect")
                        if previous[0]==binding else
                        LocalAdmission(False,"idempotency_binding_mismatch"))
            agent=db.execute("""SELECT a.user_id FROM alpha_agents a
                JOIN alpha_users u ON u.user_id=a.user_id AND u.disabled=0
                WHERE a.agent_id=? AND a.disabled=0""",
                (agent_id,)).fetchone()
            if agent is None or agent[0]!=owner_id:
                return LocalAdmission(False,"agent_owner_or_state_mismatch")
            if requester!=owner_id:
                grant=db.execute("""SELECT 1 FROM alpha_agent_grants
                    WHERE agent_id=? AND grantee_user_id=? AND action='demo.echo'
                      AND revoked=0""",(agent_id,requester)).fetchone()
                if grant is None:
                    return LocalAdmission(False,"requester_not_delegated")
            host=db.execute("""SELECT operator_id,active
                FROM alpha_executor_hosts WHERE host_id=?""",(host_id,)).fetchone()
            if host is None or host[1]!=1:
                return LocalAdmission(False,"host_unavailable")
            if host[0]!=executor_id:
                return LocalAdmission(False,"executor_host_mismatch")
            assigned=db.execute("""SELECT enabled
                FROM alpha_agent_host_assignments
                WHERE agent_id=? AND host_id=?""",(agent_id,host_id)).fetchone()
            if assigned!=(1,):
                return LocalAdmission(False,"host_not_authorized_for_agent")
            db.execute("INSERT INTO alpha_sec01_admissions VALUES (?,?)",
                       (effect_key,binding))
            return LocalAdmission(True,"admitted_once_no_effect")

    def admission_count(self):
        with self.store._tx() as db:
            return db.execute("SELECT COUNT(*) FROM alpha_sec01_admissions").fetchone()[0]
