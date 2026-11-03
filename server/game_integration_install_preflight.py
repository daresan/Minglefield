"""P1.4f.4: pure, fail-closed installation preflight. No filesystem mutation.

A host-local source approval is permission to discover, NOT artifact integrity,
installed-byte attestation, or permission to install.
"""
import re

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def installation_preflight(*, source_approved, release_binding_verified,
                           artifact_sha256, observed_artifact_sha256,
                           installed_bytes_verified, expected_project_revision,
                           current_project_revision, conflicting_paths,
                           owner_confirmed=False):
    """Return a structured decision; never perform an installation.

    All evidence is supplied by server-side trusted code. Do not expose this
    function as a client-controlled authorization endpoint.
    """
    def blocked(reason):
        return {"state": "blocked", "reason": reason,
                "installation_allowed": False, "mutation_performed": False}
    if source_approved is not True:
        return blocked("source_not_trusted_by_host")
    if release_binding_verified is not True:
        return blocked("release_binding_not_verified")
    if (not isinstance(artifact_sha256, str) or
            not _SHA256.fullmatch(artifact_sha256) or
            not isinstance(observed_artifact_sha256, str) or
            not _SHA256.fullmatch(observed_artifact_sha256) or
            artifact_sha256 != observed_artifact_sha256):
        return blocked("artifact_integrity_not_verified")
    if installed_bytes_verified is not True:
        return blocked("installed_bytes_not_verified")
    if (type(expected_project_revision) is not int or
            type(current_project_revision) is not int or
            expected_project_revision < 1 or
            current_project_revision != expected_project_revision):
        return blocked("project_revision_conflict")
    if (type(conflicting_paths) is not list or
            any(type(path) is not str or not path for path in conflicting_paths)):
        return blocked("conflict_analysis_missing")
    if conflicting_paths:
        return {
            **blocked("filesystem_conflicts"),
            "conflicting_paths": list(conflicting_paths)}
    if owner_confirmed is not True:
        return blocked("explicit_owner_confirmation_required")
    return {"state": "ready_for_transaction", "reason": "preflight_satisfied",
            "installation_allowed": False, "mutation_performed": False,
            "note": "No transactional installer or recovery journal is connected yet."}
