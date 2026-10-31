"""B2.3c simulation-only fake outcomes and atomic terminal recording.

This module NEVER invokes a real adapter, network, subprocess, or game.
The trusted caller must independently control invocation and crash recovery.
"""
import math
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class FakeOutcome:
    kind: str


class DeterministicFakeAdapter:
    """Pure in-process fake. No external effects or mutable state."""

    adapter_id = "fake.test"
    adapter_version = "1"

    def invoke(self, *, scenario):
        if scenario == "success":
            return FakeOutcome("succeeded")
        if scenario == "no_effect":
            return FakeOutcome("failed")
        if scenario == "ambiguous":
            return FakeOutcome("outcome_unknown")
        if scenario == "timeout":
            raise TimeoutError("simulated timeout")
        raise ValueError("unsupported fake scenario")


@dataclass(frozen=True)
class OutcomeResult:
    state: str
    reason: str
    job_id: str | None = None


class FakeOutcomeRecorder:
    """Trusted test-only terminal recorder. Not an external callback endpoint."""

    def __init__(self, service):
        self.service = service

    def record(self, *, job_id, effect_idempotency_key, outcome):
        if (not isinstance(job_id, str) or not 1 <= len(job_id) <= 128
                or not isinstance(effect_idempotency_key, str)
                or not effect_idempotency_key.startswith("effect.")
                or len(effect_idempotency_key) != 71):
            return OutcomeResult("rejected", "invalid_intent")
        if type(outcome) is not FakeOutcome or outcome.kind not in (
                "succeeded", "failed", "outcome_unknown"):
            return OutcomeResult("rejected", "invalid_outcome")
        with self.service._transaction() as db:
            version = db.execute("SELECT version FROM action_schema WHERE singleton=1").fetchone()
            if version != (4,):
                raise ValueError("fake outcome recorder requires schema v4")
            row = db.execute("""SELECT user_id,state,effect_idempotency_key,
                adapter_id,adapter_version,dispatch_fingerprint,fingerprint
                FROM action_jobs WHERE job_id=?""", (job_id,)).fetchone()
            if (not row or row[1] != "dispatch_committed"
                    or row[2] != effect_idempotency_key
                    or row[3:5] != ("fake.test", "1")
                    or not isinstance(row[5], str) or row[5] != row[6]):
                return OutcomeResult("rejected", "invalid_intent", job_id)
            now = self.service.clock()
            if type(now) not in (int, float) or not math.isfinite(now):
                raise ValueError("invalid server clock")
            cursor = db.execute("""UPDATE action_jobs SET state=?
                WHERE job_id=? AND state='dispatch_committed'""", (outcome.kind, job_id))
            if cursor.rowcount != 1:
                raise RuntimeError("terminal transition race")
            db.execute("INSERT INTO action_audit VALUES(?,?,?,?,?)",
                       ("event." + uuid.uuid4().hex, job_id, row[0],
                        "job." + outcome.kind, now))
            return OutcomeResult(outcome.kind, "recorded_fake_outcome", job_id)
