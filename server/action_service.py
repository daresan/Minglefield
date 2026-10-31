"""Experimental B1 submission only: one local SQLite file, no execution.

Provision principals, agents and grants through trusted bootstrap code first.
Action prices/scopes and the clock are trusted server configuration, never request
fields. Legacy authorize() remains a separate reference API, not a submit path.
"""
import hashlib
import json
import math
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType

from session_store import _digest
from sqlite_policy_engine import _time

MAX_INT = 2**63 - 1


@dataclass(frozen=True)
class ActionRule:
    scope: str
    cost_minor: int
    revision: str


@dataclass(frozen=True)
class Submission:
    allowed: bool
    reason: str
    job_id: str | None = None


class _Reject(Exception):
    pass


def _canonical(value):
    """B1 JSON canonical form; object order irrelevant, arrays/type distinctions kept."""
    def validate(item):
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                validate(child)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                validate(child)
            return
        raise ValueError("non-JSON value")
    validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


class ActionService:
    def __init__(self, database, *, actions, clock=None):
        self.database = str(database)
        self.clock = clock if clock is not None else time.time
        configured = dict(actions)
        for name, rule in configured.items():
            if (not isinstance(name, str) or not name or not isinstance(rule, ActionRule)
                    or not isinstance(rule.scope, str) or not rule.scope
                    or not isinstance(rule.revision, str) or not rule.revision
                    or type(rule.cost_minor) is not int or not 0 <= rule.cost_minor <= MAX_INT):
                raise ValueError("invalid trusted action rule")
        self.actions = MappingProxyType(configured)
        self._migrate()

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

    def _migrate(self):
        with self._transaction() as db:
            required = {"agents", "grants", "operations", "auth_principals", "auth_sessions"}
            present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required <= present:
                raise ValueError("initialize the legacy policy/session stores before ActionService")
            db.execute("""CREATE TABLE IF NOT EXISTS action_schema (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)""")
            version = db.execute("SELECT version FROM action_schema WHERE singleton=1").fetchone()
            if version and version[0] != 1:
                raise ValueError("unsupported action schema version")
            db.execute("""CREATE TABLE IF NOT EXISTS action_jobs (
                job_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                agent_id TEXT NOT NULL, delegation_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
                request_json TEXT NOT NULL, cost_minor INTEGER NOT NULL CHECK(cost_minor>=0),
                pricing_revision TEXT NOT NULL, policy_revision INTEGER NOT NULL,
                state TEXT NOT NULL CHECK(state='queued'), created_at REAL NOT NULL,
                UNIQUE(user_id,delegation_id,idempotency_key),
                FOREIGN KEY(user_id) REFERENCES auth_principals(user_id),
                FOREIGN KEY(agent_id) REFERENCES agents(agent_id),
                FOREIGN KEY(delegation_id) REFERENCES grants(delegation_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS action_audit (
                event_id TEXT PRIMARY KEY, job_id TEXT NOT NULL UNIQUE,
                actor_user_id TEXT NOT NULL, event_type TEXT NOT NULL CHECK(event_type='job.queued'),
                created_at REAL NOT NULL,
                FOREIGN KEY(job_id) REFERENCES action_jobs(job_id))""")
            db.execute("CREATE INDEX IF NOT EXISTS grants_agent_budget ON grants(agent_id)")
            db.execute("INSERT OR IGNORE INTO action_schema VALUES(1,1)")

    def submit(self, *, token, agent_id, delegation_id, target_id, action_type,
               parameters, idempotency_key):
        """Return a durable queued job, or deny; storage/configuration errors propagate.

        No caller identity, price or timestamp is accepted. Idempotency is scoped
        to authenticated user + delegation + key, independent of bearer rotation.
        Current authorization is required even for replay of an existing job.
        """
        if not isinstance(token, str) or not token:
            return Submission(False, "invalid_session")
        if any(not isinstance(v, str) or not v or len(v) > 128 for v in
               (agent_id, delegation_id, target_id, action_type, idempotency_key)):
            return Submission(False, "invalid_request")
        rule = self.actions.get(action_type)
        if rule is None:
            return Submission(False, "unknown_action")
        try:
            if type(parameters) is not dict:
                raise ValueError("parameters must be an object")
            # Snapshot caller-owned mutable input before entering the transaction.
            encoded_parameters = _canonical(parameters)
            if len(encoded_parameters) > 65536:
                raise ValueError("parameters too large")
            parameters = json.loads(encoded_parameters)
        except (ValueError, TypeError, RecursionError):
            return Submission(False, "invalid_request")
        try:
            with self._transaction() as db:
                # Sample only after acquiring the writer lock, never before waiting.
                now = self.clock()
                if not math.isfinite(now):
                    raise ValueError("invalid server clock")
                at = datetime.fromtimestamp(now, timezone.utc)
                session = db.execute("""SELECT s.user_id,s.agent_id,s.delegation_id,
                    s.expires_at,s.revoked,p.disabled FROM auth_sessions s
                    JOIN auth_principals p ON p.user_id=s.user_id WHERE s.token_hash=?""",
                                     (_digest(token),)).fetchone()
                if (not session or session[4] or session[5] or now >= session[3]
                        or session[1] != agent_id or session[2] != delegation_id):
                    raise _Reject("invalid_session")
                row = db.execute("""SELECT g.agent_id,g.grant_json,g.revoked,g.spent_minor,
                    a.descriptor,a.suspended FROM grants g JOIN agents a ON a.agent_id=g.agent_id
                    WHERE g.delegation_id=?""", (delegation_id,)).fetchone()
                if not row:
                    raise _Reject("unknown_grant")
                if row[0] != session[1]:
                    raise _Reject("agent_delegation_mismatch")
                grant, agent = json.loads(row[1]), json.loads(row[4])
                if grant["agent_id"] != row[0] or agent["agent_id"] != row[0]:
                    raise _Reject("invalid_policy")
                if row[5]:
                    raise _Reject("agent_suspended")
                if row[2]:
                    raise _Reject("grant_revoked")
                if grant["status"] != "active" or grant["requester_user_id"] != session[0]:
                    raise _Reject("requester_or_grant_mismatch")
                policy = agent.get("policy", {})
                if rule.scope not in grant["scopes"] or rule.scope not in policy.get("allowed_scopes", []):
                    raise _Reject("scope_denied")
                if grant.get("target_id") != target_id:
                    raise _Reject("target_denied")
                if not _time(grant["issued_at"]) <= at < _time(grant["expires_at"]):
                    raise _Reject("outside_validity")
                request_json = _canonical(dict(version=1, user_id=session[0], agent_id=agent_id,
                    delegation_id=delegation_id, target_id=target_id, action_type=action_type,
                    scope=rule.scope, parameters=parameters))
                fingerprint = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
                previous = db.execute("""SELECT job_id,fingerprint,request_json FROM action_jobs
                    WHERE user_id=? AND delegation_id=? AND idempotency_key=?""",
                    (session[0], delegation_id, idempotency_key)).fetchone()
                if previous:
                    if previous[1:] != (fingerprint, request_json):
                        raise _Reject("idempotency_conflict")
                    return Submission(True, "already_queued", previous[0])
                # Never interpret a legacy reservation as permission to create a job.
                if db.execute("SELECT 1 FROM operations WHERE delegation_id=? AND operation_id=?",
                              (delegation_id, idempotency_key)).fetchone():
                    raise _Reject("legacy_operation_conflict")
                cost = rule.cost_minor
                # Sum in Python to fail safely even for legacy totals beyond SQLite SUM range.
                amounts = [r[0] for r in db.execute("SELECT spent_minor FROM grants WHERE agent_id=?",
                                                   (agent_id,))]
                if any(type(v) is not int or v < 0 for v in amounts):
                    raise _Reject("invalid_budget")
                total = sum(amounts)
                for used, limit in ((row[3], grant.get("max_spend_minor")),
                                    (total, policy.get("max_spend_minor"))):
                    if limit is not None:
                        if type(limit) is not int or not 0 <= limit <= MAX_INT:
                            raise _Reject("invalid_budget")
                        if used + cost > limit:
                            raise _Reject("budget_exceeded")
                if row[3] + cost > MAX_INT or total + cost > MAX_INT:
                    raise _Reject("budget_exceeded")
                # The authoritative agent reservation is SUM(grants.spent_minor).
                # Updating the grant reserves both levels under this writer lock.
                db.execute("UPDATE grants SET spent_minor=spent_minor+? WHERE delegation_id=?",
                           (cost, delegation_id))
                job_id = "job." + uuid.uuid4().hex
                db.execute("""INSERT INTO action_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (job_id, session[0], agent_id, delegation_id, idempotency_key, fingerprint,
                     request_json, cost, rule.revision, agent["revision"], "queued", now))
                db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                    ("event." + uuid.uuid4().hex, job_id, session[0], "job.queued", now))
                return Submission(True, "queued", job_id)
        except _Reject as rejected:
            return Submission(False, str(rejected))
