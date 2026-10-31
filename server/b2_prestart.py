"""Trusted B2.2 pre-start gate: durable ready/denied only, never executes effects."""
import hashlib
import hmac
import math
import uuid
from dataclasses import dataclass

from b2_worker import ClaimWorker


@dataclass(frozen=True)
class PrestartResult:
    state: str
    reason: str
    job_id: str | None = None


class PrestartGate:
    def __init__(self, service):
        self.service = service

    def authorize(self, *, job_id, worker_id, claim_token):
        if (not isinstance(job_id, str) or not 1 <= len(job_id) <= 128
                or not isinstance(worker_id, str) or not 1 <= len(worker_id) <= 128
                or not isinstance(claim_token, str) or not claim_token
                or len(claim_token) > 512):
            return PrestartResult("rejected", "invalid_claim")
        with self.service._transaction() as db:
            version = db.execute("SELECT version FROM action_schema WHERE singleton=1").fetchone()
            if version != (3,):
                raise ValueError("pre-start gate requires schema v3")
            row = db.execute("""SELECT job_id,user_id,agent_id,delegation_id,request_json,
                session_token_hash,cost_minor,claimed_by,claim_token_hash,state
                FROM action_jobs WHERE job_id=?""", (job_id,)).fetchone()
            if not row or row[9] != "claimed" or row[7] != worker_id or not row[8]:
                return PrestartResult("rejected", "invalid_claim", job_id)
            try:
                digest = hashlib.sha256(claim_token.encode("utf-8")).hexdigest()
            except UnicodeEncodeError:
                return PrestartResult("rejected", "invalid_claim", job_id)
            stored = row[8]
            if (not isinstance(stored, str) or len(stored) != 64
                    or any(c not in "0123456789abcdef" for c in stored)
                    or not hmac.compare_digest(digest, stored)):
                return PrestartResult("rejected", "invalid_claim", job_id)
            now = self.service.clock()
            if not isinstance(now, (int, float)) or not math.isfinite(now):
                raise ValueError("invalid server clock")
            reason = ClaimWorker._check(self, db, now, row[:7])
            state = "denied" if reason else "ready"
            db.execute("UPDATE action_jobs SET state=? WHERE job_id=? AND state='claimed'",
                       (state, job_id))
            db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                       ("event." + uuid.uuid4().hex, job_id, row[1], "job." + state, now))
            return PrestartResult(state, reason or "authorized_no_effect", job_id)
