"""SEC-01 isolated, in-memory atomic effect-acceptance simulation.

Not wired to B2, not a real adapter, and not a durable security mechanism.
"""
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class FenceDecision:
    accepted: bool
    reason: str


class SimulatedEffectBoundary:
    """One lock models a single authoritative serialization point."""

    def __init__(self):
        self._lock = Lock()
        self._epoch = 0
        self._revoked = False
        self._accepted = {}

    def capability_epoch(self):
        with self._lock:
            return self._epoch

    def revoke(self):
        with self._lock:
            self._epoch += 1
            self._revoked = True

    def accept(self, *, epoch, effect_key, binding):
        # The tuple represents immutable request, target, adapter and identity
        # bindings. This prototype intentionally does not authenticate them.
        if (type(epoch) is not int or epoch < 0
                or not isinstance(effect_key, str) or not effect_key
                or not isinstance(binding, tuple) or not binding
                or any(not isinstance(v, str) or not v for v in binding)):
            return FenceDecision(False, "invalid_capability")
        with self._lock:
            existing = self._accepted.get(effect_key)
            if existing is not None:
                if existing != binding:
                    return FenceDecision(False, "idempotency_binding_mismatch")
                return FenceDecision(True, "already_accepted_no_new_effect")
            if self._revoked or epoch != self._epoch:
                return FenceDecision(False, "revoked_or_stale_epoch")
            self._accepted[effect_key] = binding
            return FenceDecision(True, "accepted_once")

    def accepted_count(self):
        with self._lock:
            return len(self._accepted)
