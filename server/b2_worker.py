"""Trusted B2.1 claim-only worker. No effect execution or start transition."""
import hashlib
import json
import math
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from b2_schema import migrate_b2
from action_service import _time, MAX_INT


@dataclass(frozen=True)
class Claim:
    state: str
    reason: str
    job_id: str | None = None
    claim_token: str | None = None


class ClaimWorker:
    def __init__(self, service):
        self.service = service
        with service._transaction() as db:
            version = db.execute(
                "SELECT version FROM action_schema WHERE singleton=1").fetchone()
        if version == (1,):
            migrate_b2(service.database)
        elif version not in ((2,), (3,), (4,)):
            raise ValueError("claim worker requires action schema v1, v2, v3 or v4")

    def claim_next(self, worker_id):
        if not isinstance(worker_id, str) or not 1 <= len(worker_id) <= 128:
            raise ValueError("invalid trusted worker id")
        with self.service._transaction() as db:
            now = self.service.clock()
            if not isinstance(now, (int, float)) or not math.isfinite(now):
                raise ValueError("invalid server clock")
            version = db.execute("SELECT version FROM action_schema WHERE singleton=1").fetchone()
            if version not in ((2,), (3,), (4,)):
                raise ValueError("worker requires schema v2, v3 or v4")
            job = db.execute("""SELECT job_id,user_id,agent_id,delegation_id,request_json,
                session_token_hash,cost_minor FROM action_jobs WHERE state='queued'
                ORDER BY created_at,job_id LIMIT 1""").fetchone()
            if not job:
                return Claim("empty", "no_queued_jobs")
            job_id, user_id, agent_id, delegation_id, request_json, session_hash, cost = job
            reason = self._check(db, now, job)
            if reason:
                db.execute("UPDATE action_jobs SET state='denied' WHERE job_id=? AND state='queued'",
                           (job_id,))
                db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                           ("event." + uuid.uuid4().hex, job_id, user_id, "job.denied", now))
                return Claim("denied", reason, job_id)
            token = secrets.token_urlsafe(32)
            db.execute("""UPDATE action_jobs SET state='claimed',claimed_by=?,claim_token_hash=?
                WHERE job_id=? AND state='queued'""",
                (worker_id, hashlib.sha256(token.encode()).hexdigest(), job_id))
            db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                       ("event." + uuid.uuid4().hex, job_id, user_id, "job.claimed", now))
            return Claim("claimed", "claimed", job_id, token)

    def _check(self, db, now, job):
        job_id, user_id, agent_id, delegation_id, raw, session_hash, cost = job
        if not session_hash:
            return "missing_original_session"
        session = db.execute("""SELECT s.user_id,s.agent_id,s.delegation_id,
            s.expires_at,s.revoked,p.disabled FROM auth_sessions s
            JOIN auth_principals p ON p.user_id=s.user_id WHERE s.token_hash=?""",
            (session_hash,)).fetchone()
        if (not session or session[4] or session[5]
                or type(session[3]) not in (int, float)
                or not math.isfinite(session[3]) or now >= session[3]
                or session[:3] != (user_id, agent_id, delegation_id)):
            return "invalid_original_session"
        row = db.execute("""SELECT g.agent_id,g.grant_json,g.revoked,
            a.descriptor,a.suspended FROM grants g JOIN agents a ON a.agent_id=g.agent_id
            WHERE g.delegation_id=?""", (delegation_id,)).fetchone()
        if not row or row[0] != agent_id:
            return "agent_delegation_mismatch"
        if row[2]:
            return "grant_revoked"
        if row[4]:
            return "agent_suspended"
        try:
            request = json.loads(raw)
            if type(request) is not dict:
                return "invalid_policy"
            if (type(request.get("version")) is not int or request["version"] != 1
                    or type(request.get("parameters")) is not dict):
                return "invalid_policy"
            grant = json.loads(row[1])
            agent = json.loads(row[3])
            rule = self.service.actions.get(request["action_type"])
            if (request["user_id"], request["agent_id"], request["delegation_id"]) != (
                    user_id, agent_id, delegation_id):
                return "request_binding_mismatch"
            if (type(grant) is not dict or type(agent) is not dict
                    or grant.get("agent_id") != agent_id
                    or agent.get("agent_id") != agent_id
                    or grant.get("delegation_id") != delegation_id):
                return "invalid_policy"
            revision = agent.get("revision")
            if type(revision) is not int or not 0 <= revision <= MAX_INT:
                return "invalid_policy"
            if grant.get("status") != "active" or grant.get("requester_user_id") != user_id:
                return "grant_inactive"
            if rule is None or rule.scope != request["scope"]:
                return "action_rule_changed"
            policy = agent.get("policy")
            scopes = grant.get("scopes")
            allowed = policy.get("allowed_scopes") if type(policy) is dict else None
            if (type(scopes) is not list or type(allowed) is not list
                    or any(type(scope) is not str or not scope for scope in scopes)
                    or any(type(scope) is not str or not scope for scope in allowed)):
                return "invalid_policy"
            for limit in (grant.get("max_spend_minor"), policy.get("max_spend_minor")):
                if limit is not None and (type(limit) is not int or not 0 <= limit <= MAX_INT):
                    return "invalid_policy"
            if rule.scope not in scopes or rule.scope not in allowed:
                return "scope_denied"
            if grant.get("target_id") != request["target_id"]:
                return "target_denied"
            at = datetime.fromtimestamp(now, timezone.utc)
            issued_at, expires_at = grant.get("issued_at"), grant.get("expires_at")
            if type(issued_at) is not str or type(expires_at) is not str:
                return "invalid_policy"
            issued, expires = _time(issued_at), _time(expires_at)
            if issued >= expires or not issued <= at < expires:
                return "outside_validity"
            if type(cost) is not int or cost < 0:
                return "invalid_cost"
        except (KeyError, TypeError, ValueError, OverflowError):
            return "invalid_policy"
        return None
