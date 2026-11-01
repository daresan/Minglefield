"""SEC-01 internal simulation-only composite validation; NOT effect authorization.

Combines the structural envelope check with an issuer-side original-session
reference check. Both reads are separate from any effect-side atomic admission.
"""
from dataclasses import dataclass

from sec01_capability_validation import validate_capability_shape
from sec01_original_session_binding import verify_original_session_reference


@dataclass(frozen=True)
class CompositeValidation:
    valid: bool
    reason: str


def validate_bound_capability(candidate, *, intent, authority, database,
                              issuer_secret, now, expected_issuer,
                              expected_audience, expected_executor):
    """Check a prototype envelope with an additional opaque session reference.

    Never sign, issue, authenticate, admit, invoke or mutate B2 jobs.
    """
    if type(candidate) is not dict:
        return CompositeValidation(False, "invalid_shape")
    if set(candidate) != (
            __import__("sec01_capability_validation",
                       fromlist=["EXPECTED_FIELDS"]).EXPECTED_FIELDS
            | {"original_session_reference"}):
        return CompositeValidation(False, "invalid_shape")
    reference = candidate["original_session_reference"]
    envelope = {k: v for k, v in candidate.items()
                if k != "original_session_reference"}
    structural = validate_capability_shape(
        envelope, intent=intent, authority=authority, now=now,
        expected_issuer=expected_issuer, expected_audience=expected_audience,
        expected_executor=expected_executor)
    if not structural.valid:
        return CompositeValidation(False, structural.reason)
    session = verify_original_session_reference(
        database, intent=intent, issuer_secret=issuer_secret,
        expected_reference=reference, now=now)
    if not session.valid:
        return CompositeValidation(False, session.reason)
    return CompositeValidation(True, "bound_shape_not_authenticated_or_admitted")
