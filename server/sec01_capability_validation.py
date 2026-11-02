"""SEC-01 structural capability-envelope validator; not authentication or admission.

The input is untrusted. Even a valid result NEVER authorizes a real effect.
No signing, issuing, B2 state changes, network access, or adapter invocation.
"""
import math
from dataclasses import asdict, dataclass, fields

from sec01_b2_intent_projection import CommittedIntent
from sec01_authority_fencing_sqlite import AuthoritySnapshot, SQLiteAuthorityFence, MAX_EPOCH

INTENT_FIELDS = tuple(f.name for f in fields(CommittedIntent))
EXTRA_FIELDS = ("version", "issuer", "audience", "executor_identity",
                "issued_at", "expires_at", "authority_identities", "authority_epochs")
EXPECTED_FIELDS = frozenset(INTENT_FIELDS + EXTRA_FIELDS)


@dataclass(frozen=True)
class CapabilityValidation:
    valid: bool
    reason: str


def validate_capability_shape(candidate, *, intent, authority, now,
                              expected_issuer, expected_audience,
                              expected_executor):
    """Validate exact structure, trusted intent binding and current SIMULATED epochs.

    `authority.snapshot` is a separate read, not atomic with any effect
    acceptance. Callers MUST NOT interpret `valid=True` as effect permission.
    """
    if (type(intent) is not CommittedIntent
            or type(authority) is not SQLiteAuthorityFence
            or type(now) not in (int, float) or not math.isfinite(now)
            or any(type(v) is not str or not v for v in
                   (expected_issuer, expected_audience, expected_executor))):
        raise ValueError("invalid trusted validation context")
    if type(candidate) is not dict or set(candidate) != EXPECTED_FIELDS:
        return CapabilityValidation(False, "invalid_shape")
    if type(candidate["version"]) is not int or candidate["version"] != 1:
        return CapabilityValidation(False, "unsupported_version")
    if any(type(candidate[k]) is not type(v) or candidate[k] != v
           for k, v in asdict(intent).items()):
        return CapabilityValidation(False, "intent_binding_mismatch")
    for key, expected in (("issuer", expected_issuer),
                          ("audience", expected_audience),
                          ("executor_identity", expected_executor)):
        if type(candidate[key]) is not str or candidate[key] != expected:
            return CapabilityValidation(False, "context_binding_mismatch")
    issued, expires = candidate["issued_at"], candidate["expires_at"]
    if (type(issued) is not int or type(expires) is not int
            or issued < 0 or issued >= expires or not issued <= now < expires):
        return CapabilityValidation(False, "invalid_lifetime")
    identities = candidate["authority_identities"]
    epochs = candidate["authority_epochs"]
    if (type(identities) is not tuple or not authority._identities(identities)
            or type(epochs) is not tuple or len(epochs) != 4
            or any(type(v) is not int or not 0 <= v <= MAX_EPOCH for v in epochs)):
        return CapabilityValidation(False, "invalid_authority_shape")
    # The order is fixed: session, grant, agent, principal.
    if (identities[1] != intent.delegation_id
            or identities[2] != intent.agent_id
            or identities[3] != intent.user_id):
        return CapabilityValidation(False, "authority_identity_mismatch")
    try:
        current = authority.snapshot(identities)
    except ValueError:
        return CapabilityValidation(False, "authority_unavailable")
    if type(current) is not AuthoritySnapshot or current.epochs != epochs:
        return CapabilityValidation(False, "authority_epoch_changed")
    return CapabilityValidation(True, "shape_valid_not_authenticated")
