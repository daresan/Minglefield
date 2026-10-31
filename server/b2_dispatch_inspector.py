"""Read-only B2.3c dispatch diagnostics; no state changes, replay, or secrets."""
import math
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class DispatchDiagnostic:
    job_id: str
    state: str
    classification: str
    adapter_id: str | None
    adapter_version: str | None
    dispatched_at: float | None
    audit_events: tuple[str, ...]


class DispatchInspector:
    """Trusted operator-side read API. Do not expose without access control."""

    def __init__(self, database):
        self.database = str(database)

    def inspect(self, *, job_id):
        if not isinstance(job_id, str) or not 1 <= len(job_id) <= 128:
            raise ValueError("invalid job id")
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        try:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            version = db.execute(
                "SELECT version FROM action_schema WHERE singleton=1").fetchone()
            if version != (4,):
                raise ValueError("dispatch inspector requires schema v4")
            row = db.execute("""SELECT state,adapter_id,adapter_version,dispatched_at
                FROM action_jobs WHERE job_id=?""", (job_id,)).fetchone()
            if row is None:
                return None
            state, adapter_id, adapter_version, dispatched_at = row
            if state not in ("queued", "claimed", "ready", "denied",
                             "dispatch_committed", "succeeded", "failed",
                             "outcome_unknown"):
                raise ValueError("invalid stored job state")
            events = tuple(event[0] for event in db.execute(
                """SELECT event_type FROM action_audit WHERE job_id=?
                   ORDER BY CASE event_type
                     WHEN 'job.queued' THEN 0
                     WHEN 'job.claimed' THEN 1
                     WHEN 'job.ready' THEN 2
                     WHEN 'job.denied' THEN 3
                     WHEN 'job.dispatch_committed' THEN 4
                     WHEN 'job.succeeded' THEN 5
                     WHEN 'job.failed' THEN 5
                     WHEN 'job.outcome_unknown' THEN 5
                     ELSE 6 END, created_at,event_id""", (job_id,)))
            if state == "dispatch_committed":
                classification = "unresolved_intent_manual_review"
            elif state == "outcome_unknown":
                classification = "ambiguous_outcome_manual_review"
            elif state in ("succeeded", "failed"):
                classification = "recorded_terminal_outcome"
            else:
                classification = "no_dispatch_intent"
            if dispatched_at is not None and (
                    type(dispatched_at) not in (int, float)
                    or not math.isfinite(dispatched_at)):
                raise ValueError("invalid dispatch timestamp")
            return DispatchDiagnostic(job_id, state, classification, adapter_id,
                                      adapter_version, dispatched_at, events)
        finally:
            db.close()
