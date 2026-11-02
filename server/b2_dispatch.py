"""B2.3b simulation-only durable dispatch intent. Never invokes an adapter."""
import hashlib
import hmac
import math
import secrets
import uuid
from dataclasses import dataclass
from types import MappingProxyType

from b2_worker import ClaimWorker


@dataclass(frozen=True)
class DispatchResult:
    state: str
    reason: str
    job_id: str | None = None


class DispatchGate:
    """Trusted internal coordinator boundary; caller must be authenticated separately."""

    def __init__(self, service, *, adapters):
        self.service = service
        # Trusted configuration, never sourced from request JSON.
        if not isinstance(adapters, dict):
            raise ValueError("invalid adapter configuration")
        validated = {}
        for action, identity in adapters.items():
            if (not isinstance(action, str) or not action
                    or not isinstance(identity, tuple) or len(identity) != 2
                    or any(not isinstance(v, str) or not 1 <= len(v) <= 128
                           for v in identity)):
                raise ValueError("invalid adapter configuration")
            validated[action] = identity
        self.adapters = MappingProxyType(validated)

    def commit_intent(self, *, job_id, worker_id, claim_token):
        if (not isinstance(job_id, str) or not 1 <= len(job_id) <= 128
                or not isinstance(worker_id, str) or not 1 <= len(worker_id) <= 128
                or not isinstance(claim_token, str) or not 1 <= len(claim_token) <= 512):
            return DispatchResult("rejected", "invalid_claim")
        try:
            digest = hashlib.sha256(claim_token.encode("utf-8")).hexdigest()
        except UnicodeEncodeError:
            return DispatchResult("rejected", "invalid_claim")
        with self.service._transaction() as db:
            version = db.execute("SELECT version FROM action_schema WHERE singleton=1").fetchone()
            if version != (4,):
                raise ValueError("dispatch gate requires schema v4")
            row = db.execute("""SELECT job_id,user_id,agent_id,delegation_id,request_json,
                session_token_hash,cost_minor,policy_revision,claimed_by,claim_token_hash,state,
                fingerprint FROM action_jobs WHERE job_id=?""", (job_id,)).fetchone()
            if (not row or row[10] != "ready" or row[8] != worker_id
                    or not isinstance(row[9], str) or len(row[9]) != 64
                    or any(c not in "0123456789abcdef" for c in row[9])
                    or not hmac.compare_digest(digest, row[9])):
                return DispatchResult("rejected", "invalid_claim", job_id)
            now = self.service.clock()
            if not isinstance(now, (int, float)) or not math.isfinite(now):
                raise ValueError("invalid server clock")
            reason = ClaimWorker._check(self, db, now, row[:8])
            if reason:
                db.execute("UPDATE action_jobs SET state='denied' WHERE job_id=? AND state='ready'",
                           (job_id,))
                db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                           ("event." + uuid.uuid4().hex, job_id, row[1], "job.denied", now))
                return DispatchResult("denied", reason, job_id)
            # Request integrity and trusted action-to-adapter binding are checked again.
            try:
                import json
                from action_service import _canonical
                request = json.loads(row[4])
                if not isinstance(request, dict):
                    raise ValueError("invalid request")
                action = request["action_type"]
                adapter = self.adapters.get(action)
                if adapter is None or action not in self.service.actions:
                    raise ValueError("no trusted adapter")
                canonical = _canonical(request)
                fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if (canonical != row[4] or not isinstance(row[11], str)
                        or not hmac.compare_digest(fingerprint, row[11])):
                    raise ValueError("request fingerprint mismatch")
            except (ValueError, TypeError, KeyError, RecursionError):
                db.execute("UPDATE action_jobs SET state='denied' WHERE job_id=? AND state='ready'",
                           (job_id,))
                db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                           ("event." + uuid.uuid4().hex, job_id, row[1], "job.denied", now))
                return DispatchResult("denied", "invalid_dispatch_binding", job_id)
            effect_key = "effect." + secrets.token_hex(32)
            cursor = db.execute("""UPDATE action_jobs SET state='dispatch_committed',
                effect_idempotency_key=?,dispatch_fingerprint=?,adapter_id=?,
                adapter_version=?,dispatched_at=? WHERE job_id=? AND state='ready'""",
                (effect_key, fingerprint, adapter[0], adapter[1], now, job_id))
            if cursor.rowcount != 1:
                raise RuntimeError("dispatch intent state race")
            db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                       ("event." + uuid.uuid4().hex, job_id, row[1],
                        "job.dispatch_committed", now))
            return DispatchResult("dispatch_committed", "intent_only_no_effect", job_id)
