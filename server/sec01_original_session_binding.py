"""SEC-01 trusted internal original-session binding check, read-only.

The opaque reference is HMAC-derived with an issuer-held key. It is NOT a
bearer token, authentication proof, or authorization to execute an effect.
Never disclose the reference or secret to untrusted callers.
"""
import hashlib
import hmac
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass

from sec01_b2_intent_projection import CommittedIntent, project_committed_intent


@dataclass(frozen=True)
class OriginalSessionBinding:
    valid: bool
    reason: str


def _reference(secret, job_id, token_hash):
    message = b"sec01-original-session-v1\x00" + job_id.encode("utf-8") + b"\x00" + token_hash.encode("ascii")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def original_session_reference(database, *, intent, issuer_secret, now):
    """Trusted issuer-side lookup; never returns the stored token hash.

    Returns a job-scoped opaque reference, or raises ValueError. The lookup is
    read-only and cannot establish atomic post-lookup authorization.
    """
    if (type(intent) is not CommittedIntent or type(issuer_secret) is not bytes
            or len(issuer_secret) < 32 or type(now) not in (int, float)
            or not math.isfinite(now)):
        raise ValueError("invalid trusted context")
    with closing(sqlite3.connect(str(database), timeout=10)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        row = db.execute("""SELECT j.session_token_hash,j.user_id,j.agent_id,
            j.delegation_id,s.user_id,s.agent_id,s.delegation_id,
            s.expires_at,s.revoked,p.disabled
            FROM action_jobs j
            LEFT JOIN auth_sessions s ON s.token_hash=j.session_token_hash
            LEFT JOIN auth_principals p ON p.user_id=s.user_id
            WHERE j.job_id=? AND j.state='dispatch_committed'""",
            (intent.job_id,)).fetchone()
        if not row:
            raise ValueError("unavailable original session")
        token_hash = row[0]
        if (type(token_hash) is not str or len(token_hash) != 64
                or any(c not in "0123456789abcdef" for c in token_hash)
                or row[1:4] != (intent.user_id, intent.agent_id, intent.delegation_id)
                or row[4:7] != (intent.user_id, intent.agent_id, intent.delegation_id)
                or type(row[7]) not in (int, float) or not math.isfinite(row[7])
                or now >= row[7] or row[8] != 0 or row[9] != 0):
            raise ValueError("invalid original session")
        # Match the full B2 projection against current trusted job data.
        projected = project_committed_intent(database, job_id=intent.job_id)
        if projected != intent:
            raise ValueError("intent changed")
        return _reference(issuer_secret, intent.job_id, token_hash)


def verify_original_session_reference(database, *, intent, issuer_secret,
                                      expected_reference, now):
    """Compare issuer-side opaque reference with the current original session."""
    if (type(expected_reference) is not str or len(expected_reference) != 64
            or any(c not in "0123456789abcdef" for c in expected_reference)):
        return OriginalSessionBinding(False, "invalid_session_reference")
    try:
        current = original_session_reference(
            database, intent=intent, issuer_secret=issuer_secret, now=now)
    except (ValueError, sqlite3.Error):
        return OriginalSessionBinding(False, "original_session_unavailable")
    if not hmac.compare_digest(current, expected_reference):
        return OriginalSessionBinding(False, "original_session_mismatch")
    return OriginalSessionBinding(True, "original_session_bound_not_authenticated")
