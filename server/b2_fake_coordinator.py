"""Explicit B2.3c in-process simulation coordinator; no real adapters or retries."""
from dataclasses import dataclass

from b2_dispatch import DispatchGate
from b2_fake_adapter import DeterministicFakeAdapter, FakeOutcome, FakeOutcomeRecorder


@dataclass(frozen=True)
class SimulationResult:
    state: str
    reason: str
    job_id: str | None = None


class FakeSimulationCoordinator:
    """One-shot synchronous fake; never scans/replays persisted dispatch intents."""

    def __init__(self, service):
        self.service = service
        self.gate = DispatchGate(service, adapters={
            "game.feedback": ("fake.test", "1")})
        self.recorder = FakeOutcomeRecorder(service)

    def run_once(self, *, job_id, worker_id, claim_token, scenario,
                 crash_at=None):
        if scenario not in ("success", "no_effect", "ambiguous", "timeout"):
            return SimulationResult("rejected", "invalid_fake_scenario", job_id)
        if crash_at not in (None, "before_commit", "after_commit", "after_call"):
            return SimulationResult("rejected", "invalid_crash_point", job_id)
        if crash_at == "before_commit":
            raise RuntimeError("simulated crash before intent")
        intent = self.gate.commit_intent(job_id=job_id, worker_id=worker_id,
                                         claim_token=claim_token)
        if intent.state != "dispatch_committed":
            return SimulationResult(intent.state, intent.reason, intent.job_id)
        # Only the winner of the durable intent transition can reach invoke().
        if crash_at == "after_commit":
            raise RuntimeError("simulated crash after intent, before fake call")
        # Fetch the server-generated key, never accept it from an untrusted caller.
        with self.service._transaction() as db:
            row = db.execute("""SELECT effect_idempotency_key,adapter_id,adapter_version
                FROM action_jobs WHERE job_id=? AND state='dispatch_committed'""",
                (job_id,)).fetchone()
            if not row or row[1:] != ("fake.test", "1"):
                raise RuntimeError("invalid committed fake adapter binding")
            key = row[0]
        try:
            outcome = DeterministicFakeAdapter().invoke(scenario=scenario)
        except TimeoutError:
            outcome = FakeOutcome("outcome_unknown")
        if crash_at == "after_call":
            raise RuntimeError("simulated crash after fake call, before outcome")
        result = self.recorder.record(job_id=job_id, effect_idempotency_key=key,
                                      outcome=outcome)
        return SimulationResult(result.state, result.reason, result.job_id)
