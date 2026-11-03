"""Read-only assessment orchestration for an authorized server-side release context.

The resolver is a server-owned trust service, never request JSON. It returns
already authenticated bytes/digest evidence or None. No fixture trust store is
imported here; a production resolver is not yet implemented.
"""
import json

from game_integration_assessment_provenance import verify_assessment_document_bytes
from game_integration_assessment import assess_compatibility, assess_migration


def preview_release_assessments(*, integration_id, release_source,
                                from_version, to_version, resolver=None):
    """Fail closed until a trusted resolver is supplied by the server."""
    result = {
        "compatibility": assess_compatibility(),
        "migration": assess_migration(),
        "installation_allowed": False,
    }
    if resolver is None:
        return result
    if not callable(resolver):
        return result
    for kind in ("compatibility", "migration"):
        try:
            evidence = resolver(kind=kind, integration_id=integration_id,
                                release_source=release_source,
                                from_version=from_version, to_version=to_version)
        except Exception:
            continue
        if not isinstance(evidence, dict):
            continue
        raw = evidence.get("raw_bytes")
        digest = evidence.get("expected_sha256")
        # A resolver is part of the trusted server boundary, not a user-selected
        # callback. Its explicit authenticated result is still checked bytewise.
        checked = verify_assessment_document_bytes(
            kind, raw, expected_sha256=digest,
            independent_digest_authenticated=evidence.get("authenticated") is True,
            expected_integration_id=integration_id,
            authorized_source=release_source,
            from_version=from_version, to_version=to_version)
        if checked["state"] != "verified":
            result[kind] = {"state": "unknown" if checked["state"] == "unknown" else "invalid",
                            "reason": checked["reason"], "requires_manual_review": True}
            continue
        try:
            document = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            continue
        if kind == "compatibility":
            # Verified document alone cannot prove the target satisfies it.
            result[kind] = assess_compatibility(
                document, trusted_contract=True, release_bound=True)
        else:
            # Verified plan alone cannot prove prerequisites or recovery.
            result[kind] = assess_migration(
                document, trusted_plan=True, release_bound=True)
        result[kind]["document_provenance"] = "verified"
    return result
