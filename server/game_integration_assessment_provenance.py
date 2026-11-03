"""Read-only assessment byte verification; authority is established outside this module.

The expected digest MUST come from an independently authenticated trust channel,
not from the assessment document, release notes, lockfile, or fetched asset.
"""
import hashlib
import json
import re

from game_integration_assessment_binding import validate_assessment_binding

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_MAX_BYTES = 1024 * 1024


def verify_assessment_document_bytes(kind, raw_bytes, *, expected_sha256=None,
                                     independent_digest_authenticated=False,
                                     expected_integration_id, authorized_source,
                                     from_version, to_version):
    """No IO, downloads, or trust promotion from document-supplied metadata."""
    blocked = {"provenance_verified": False, "installation_allowed": False}
    if not isinstance(raw_bytes, bytes) or not raw_bytes or len(raw_bytes) > _MAX_BYTES:
        return {**blocked, "state": "invalid", "reason": "invalid_assessment_bytes"}
    if independent_digest_authenticated is not True:
        return {**blocked, "state": "unknown", "reason": "independent_digest_not_authenticated"}
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        return {**blocked, "state": "unknown", "reason": "missing_independent_assessment_digest"}
    observed = hashlib.sha256(raw_bytes).hexdigest()
    if observed != expected_sha256:
        return {**blocked, "state": "invalid", "reason": "assessment_digest_mismatch",
                "observed_sha256": observed}
    try:
        document = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeError, ValueError):
        return {**blocked, "state": "invalid", "reason": "invalid_assessment_json"}
    binding = validate_assessment_binding(
        kind, document, expected_integration_id=expected_integration_id,
        authorized_source=authorized_source, from_version=from_version,
        to_version=to_version)
    if binding["state"] != "matched":
        return {**blocked, "state": binding["state"], "reason": binding["reason"]}
    return {"state": "verified", "reason": "independent_digest_and_release_binding_match",
            "provenance_verified": True, "installation_allowed": False,
            "observed_sha256": observed}
