"""SEC-01 isolated executor admission model: NO network, real execution or B2.

This fixture keeps owner, requester, agent, executor and host authorization
in ONE SQLite transaction domain. It is not a remote admission protocol:
trusted fixture methods are not authenticated endpoints. No effects occur.
"""
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

def valid(value):
    return type(value) is str and 1 <= len(value) <= 128 and all(
        x.isascii() and (x.isalnum() or x in "._-") for x in value)

@dataclass(frozen=True)
class AdmissionResult:
    accepted: bool
    reason: str

class MockExecutorAuthority:
    def __init__(self, database):
        self.database=str(Path(database))
        with closing(sqlite3.connect(self.database,timeout=10)) as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS exe_agents(
                agent_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, active INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS exe_hosts(
                host_id TEXT PRIMARY KEY, operator_id TEXT NOT NULL, active INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS exe_assignments(
                agent_id TEXT NOT NULL, host_id TEXT NOT NULL, enabled INTEGER NOT NULL,
                PRIMARY KEY(agent_id,host_id));
            CREATE TABLE IF NOT EXISTS exe_grants(
                agent_id TEXT NOT NULL, requester_id TEXT NOT NULL,
                action TEXT NOT NULL, enabled INTEGER NOT NULL,
                PRIMARY KEY(agent_id,requester_id,action));
            CREATE TABLE IF NOT EXISTS exe_admissions(
                effect_key TEXT PRIMARY KEY, binding TEXT NOT NULL);""")

    def _tx(self):
        return _Tx(self.database)

    def add_agent(self, agent_id, owner_id):
        if not valid(agent_id) or not valid(owner_id):
            raise ValueError("invalid agent fixture")
        with self._tx() as db:
            db.execute("INSERT INTO exe_agents VALUES(?,?,1)",(agent_id,owner_id))

    def add_host(self, host_id, operator_id):
        if not valid(host_id) or not valid(operator_id):
            raise ValueError("invalid host fixture")
        with self._tx() as db:
            db.execute("INSERT INTO exe_hosts VALUES(?,?,1)",(host_id,operator_id))

    def assign_host(self, agent_id, host_id, *, enabled=True):
        """Trusted fixture: host placement is NOT a requester entitlement."""
        if not valid(agent_id) or not valid(host_id) or type(enabled) is not bool:
            raise ValueError("invalid assignment")
        with self._tx() as db:
            if not db.execute("SELECT 1 FROM exe_agents WHERE agent_id=?",(agent_id,)).fetchone():
                raise ValueError("unknown agent")
            if not db.execute("SELECT 1 FROM exe_hosts WHERE host_id=?",(host_id,)).fetchone():
                raise ValueError("unknown host")
            db.execute("""INSERT INTO exe_assignments VALUES(?,?,?)
                ON CONFLICT(agent_id,host_id) DO UPDATE SET enabled=excluded.enabled""",
                (agent_id,host_id,int(enabled)))

    def grant(self, agent_id, requester_id, *, enabled=True):
        """Trusted fixture models owner-approved demo.echo delegation."""
        if not valid(agent_id) or not valid(requester_id) or type(enabled) is not bool:
            raise ValueError("invalid grant")
        with self._tx() as db:
            agent=db.execute("SELECT owner_id FROM exe_agents WHERE agent_id=?",
                             (agent_id,)).fetchone()
            if agent is None or agent[0]==requester_id:
                raise ValueError("invalid foreign grant")
            db.execute("""INSERT INTO exe_grants VALUES (?,?,'demo.echo',?)
                ON CONFLICT(agent_id,requester_id,action)
                DO UPDATE SET enabled=excluded.enabled""",
                (agent_id,requester_id,int(enabled)))

    def set_active(self, kind, identity, active):
        if kind not in ("agent","host") or not valid(identity) or type(active) is not bool:
            raise ValueError("invalid actor")
        table,col=("exe_agents","agent_id") if kind=="agent" else ("exe_hosts","host_id")
        with self._tx() as db:
            if db.execute(f"UPDATE {table} SET active=? WHERE {col}=?",
                          (int(active),identity)).rowcount!=1:
                raise ValueError("unknown actor")

    def admit(self, *, effect_key, job_id, fingerprint, requester_id,
              agent_id, owner_id, executor_id, host_id, action="demo.echo"):
        fields=(effect_key,job_id,fingerprint,requester_id,
                agent_id,owner_id,executor_id,host_id)
        if not all(valid(v) for v in fields) or action!="demo.echo":
            return AdmissionResult(False,"invalid_intent")
        binding=json.dumps([job_id,fingerprint,requester_id,agent_id,
                            owner_id,executor_id,host_id,action],
                           separators=(",",":"),ensure_ascii=True)
        with self._tx() as db:
            prior=db.execute("SELECT binding FROM exe_admissions WHERE effect_key=?",
                             (effect_key,)).fetchone()
            if prior:
                if prior[0]!=binding:
                    return AdmissionResult(False,"idempotency_binding_mismatch")
                return AdmissionResult(True,"already_admitted_no_new_effect")
            agent=db.execute("SELECT owner_id,active FROM exe_agents WHERE agent_id=?",
                             (agent_id,)).fetchone()
            if agent!=(owner_id,1):
                return AdmissionResult(False,"agent_owner_or_state_mismatch")
            host=db.execute("SELECT operator_id,active FROM exe_hosts WHERE host_id=?",
                            (host_id,)).fetchone()
            if host is None or host[1]!=1:
                return AdmissionResult(False,"host_unavailable")
            # The trusted executor identity is its host operator in this fixture.
            if host[0]!=executor_id:
                return AdmissionResult(False,"executor_host_mismatch")
            assignment=db.execute("""SELECT enabled FROM exe_assignments
                WHERE agent_id=? AND host_id=?""",(agent_id,host_id)).fetchone()
            if assignment!=(1,):
                return AdmissionResult(False,"host_not_authorized_for_agent")
            if requester_id!=owner_id:
                grant=db.execute("""SELECT enabled FROM exe_grants
                    WHERE agent_id=? AND requester_id=? AND action=?""",
                    (agent_id,requester_id,action)).fetchone()
                if grant!=(1,):
                    return AdmissionResult(False,"requester_not_delegated")
            db.execute("INSERT INTO exe_admissions VALUES(?,?)",(effect_key,binding))
            return AdmissionResult(True,"admitted_once_no_effect")

    def admission_count(self):
        with closing(sqlite3.connect(self.database,timeout=10)) as db:
            return db.execute("SELECT count(*) FROM exe_admissions").fetchone()[0]

class _Tx:
    def __init__(self,database):
        self.database=database
    def __enter__(self):
        self.db=sqlite3.connect(self.database,timeout=10,isolation_level=None)
        self.db.execute("BEGIN IMMEDIATE")
        return self.db
    def __exit__(self,typ,value,tb):
        try:
            self.db.rollback() if typ else self.db.commit()
        finally:
            self.db.close()
