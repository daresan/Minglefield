"""SQLite-backed MAP v0.2 experimental policy decision point.

The caller MUST authenticate actor identities and validate all JSON records.
SQLite persistence is local, not a distributed authorization or runtime kill switch.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from policy_engine import Decision


def _time(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)


class SQLitePolicyEngine:
    def __init__(self, database, *, busy_timeout_ms=10000):
        self.database = str(Path(database))
        with self._tx() as db:
            db.executescript_initial = None  # schema created without executescript implicit commit
            db.execute("""CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY, descriptor TEXT NOT NULL,
                suspended INTEGER NOT NULL CHECK(suspended IN (0,1)))""")
            db.execute("""CREATE TABLE IF NOT EXISTS grants (
                delegation_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
                grant_json TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
                spent_minor INTEGER NOT NULL DEFAULT 0 CHECK(spent_minor>=0),
                FOREIGN KEY(agent_id) REFERENCES agents(agent_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS operations (
                delegation_id TEXT NOT NULL, operation_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL, PRIMARY KEY(delegation_id,operation_id),
                FOREIGN KEY(delegation_id) REFERENCES grants(delegation_id))""")
        self.busy_timeout_ms = busy_timeout_ms

    @contextmanager
    def _tx(self):
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

    @staticmethod
    def _roles(agent, actor):
        return {role for op in agent["operators"] if op["user_id"] == actor
                for role in op["roles"]}

    def register_agent(self, agent):
        with self._tx() as db:
            if db.execute("SELECT 1 FROM agents WHERE agent_id=?", (agent["agent_id"],)).fetchone():
                return Decision(False, "agent_exists")
            db.execute("INSERT INTO agents VALUES(?,?,?)",
                       (agent["agent_id"], json.dumps(agent), int(agent["state"] != "active")))
            return Decision(True, "agent_registered")

    def add_grant(self, grant, *, verified_actor):
        with self._tx() as db:
            row = db.execute("SELECT descriptor,suspended FROM agents WHERE agent_id=?",
                             (grant["agent_id"],)).fetchone()
            if row is None:
                return Decision(False, "unknown_agent")
            agent = json.loads(row[0])
            if row[1]:
                return Decision(False, "agent_suspended")
            if grant["issuer_user_id"] != verified_actor or "approver" not in self._roles(agent, verified_actor):
                return Decision(False, "not_authorized_approver")
            if grant["status"] != "active" or _time(grant["issued_at"]) >= _time(grant["expires_at"]):
                return Decision(False, "invalid_grant")
            if not set(grant["scopes"]) <= set(agent.get("policy", {}).get("allowed_scopes", [])):
                return Decision(False, "scope_exceeds_policy")
            if db.execute("SELECT 1 FROM grants WHERE delegation_id=?", (grant["delegation_id"],)).fetchone():
                return Decision(False, "duplicate_grant")
            db.execute("INSERT INTO grants(delegation_id,agent_id,grant_json) VALUES(?,?,?)",
                       (grant["delegation_id"], grant["agent_id"], json.dumps(grant)))
            return Decision(True, "grant_added")

    def authorize(self, *, verified_requester, delegation_id, scope, target_id, at,
                  cost_minor=0, operation_id=None):
        with self._tx() as db:
            row = db.execute("""SELECT g.grant_json,g.revoked,g.spent_minor,
                                       a.descriptor,a.suspended
                                FROM grants g JOIN agents a ON g.agent_id=a.agent_id
                                WHERE g.delegation_id=?""", (delegation_id,)).fetchone()
            if row is None:
                return Decision(False, "unknown_grant")
            grant, revoked, spent, agent, suspended = json.loads(row[0]), row[1], row[2], json.loads(row[3]), row[4]
            if suspended:
                return Decision(False, "agent_suspended")
            if revoked:
                return Decision(False, "grant_revoked")
            if grant["status"] != "active" or grant["requester_user_id"] != verified_requester:
                return Decision(False, "requester_or_grant_mismatch")
            if scope not in grant["scopes"] or scope not in agent.get("policy", {}).get("allowed_scopes", []):
                return Decision(False, "scope_denied")
            if grant.get("target_id") != target_id:
                return Decision(False, "target_denied")
            if not _time(grant["issued_at"]) <= _time(at) < _time(grant["expires_at"]):
                return Decision(False, "outside_validity")
            if type(cost_minor) is not int or cost_minor < 0:
                return Decision(False, "invalid_cost")
            if cost_minor and not operation_id:
                return Decision(False, "operation_id_required")
            fingerprint = json.dumps([verified_requester,scope,target_id,cost_minor], separators=(",",":"))
            if operation_id is not None:
                previous = db.execute("SELECT fingerprint FROM operations WHERE delegation_id=? AND operation_id=?",
                                      (delegation_id,operation_id)).fetchone()
                if previous is not None:
                    return Decision(previous[0] == fingerprint,
                                    "already_allowed" if previous[0] == fingerprint else "operation_id_conflict")
            limits = [v for v in (grant.get("max_spend_minor"),
                       agent.get("policy", {}).get("max_spend_minor")) if v is not None]
            if limits and spent + cost_minor > min(limits):
                return Decision(False, "budget_exceeded")
            db.execute("UPDATE grants SET spent_minor=spent_minor+? WHERE delegation_id=?",
                       (cost_minor,delegation_id))
            if operation_id is not None:
                db.execute("INSERT INTO operations VALUES(?,?,?)",
                           (delegation_id,operation_id,fingerprint))
            return Decision(True, "allowed")

    def revoke(self, *, delegation_id, verified_actor):
        with self._tx() as db:
            row = db.execute("""SELECT g.grant_json,a.descriptor FROM grants g
                                JOIN agents a ON g.agent_id=a.agent_id
                                WHERE g.delegation_id=?""", (delegation_id,)).fetchone()
            if row is None:
                return Decision(False, "unknown_grant")
            grant, agent = json.loads(row[0]), json.loads(row[1])
            if verified_actor != grant["requester_user_id"] and not (
                    self._roles(agent, verified_actor) & {"admin","approver"}):
                return Decision(False, "not_authorized")
            db.execute("UPDATE grants SET revoked=1 WHERE delegation_id=?", (delegation_id,))
            return Decision(True, "revoked")

    def set_suspended(self, *, agent_id, verified_actor, suspended):
        with self._tx() as db:
            row = db.execute("SELECT descriptor FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
            if row is None:
                return Decision(False, "unknown_agent")
            roles = self._roles(json.loads(row[0]), verified_actor)
            if (suspended and not roles & {"admin","approver"}) or (not suspended and "admin" not in roles):
                return Decision(False, "not_authorized")
            db.execute("UPDATE agents SET suspended=? WHERE agent_id=?",
                       (int(suspended),agent_id))
            return Decision(True, "suspended" if suspended else "resumed")
