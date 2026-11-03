"""Fail-closed, read-only preflight for explicit staging cleanup.

This module deliberately does NOT delete: on Windows a path-based unlink
sequence cannot guarantee safety against concurrent directory replacement.
A future executor must bind a trusted journal decision and exclusive handles.
"""
import os
import re
from pathlib import Path

from game_integration_install_path_safety import has_redirecting_component, is_redirecting_path
from game_integration_install_staging import validate_staging_manifest
from game_integration_install_recovery import inspect_staged_installation

_OPERATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TERMINAL = frozenset({"cancelled", "rolled_back"})


def inspect_staging_cleanup(installation_staging_root, operation_id, entries,
                            *, journal_operation_id=None, journal_plan_sha256=None,
                            journal_state=None, owner_authorized=False):
    """Return an eligible snapshot, never a deletion permission or capability.

    Inputs describing the journal MUST come from trusted server-side storage,
    not from an HTTP request. No destructive operation is implemented here.
    """
    def result(state, reason, **extra):
        return {"state": state, "reason": reason, "deletion_performed": False,
                "cleanup_allowed": False, "installation_allowed": False, **extra}
    plan = validate_staging_manifest(entries)
    if plan["state"] != "valid":
        return result("blocked", plan["reason"])
    if (type(operation_id) is not str or not _OPERATION.fullmatch(operation_id)
            or operation_id in (".", "..")):
        return result("blocked", "invalid_operation_id")
    if owner_authorized is not True:
        return result("blocked", "owner_authorization_required")
    if (journal_operation_id != operation_id
            or journal_plan_sha256 != plan["plan_sha256"]
            or journal_state not in _TERMINAL):
        return result("blocked", "journal_cleanup_not_authorized")
    root = Path(installation_staging_root)
    if not root.is_dir() or has_redirecting_component(root):
        return result("blocked", "unsafe_installation_staging_root")
    operation = root / operation_id
    if is_redirecting_path(operation):
        return result("blocked", "unsafe_operation_path")
    snapshot = inspect_staged_installation(root, operation_id, entries)
    if snapshot["state"] == "absent":
        return result("absent", "operation_not_found")
    if snapshot["state"] == "blocked":
        return result("blocked", snapshot["reason"])
    if snapshot["state"] not in ("incomplete", "damaged", "complete_snapshot"):
        return result("blocked", "unrecognized_staging_state")
    try:
        if not operation.is_dir() or has_redirecting_component(operation):
            return result("blocked", "unsafe_operation_path")
        children = list(operation.iterdir())
        expected = {f"blob-{i:06d}" for i in range(len(plan["files"]))}
        expected.add("manifest.json")
        if (len(children) != len({p.name for p in children})
                or any(p.name not in expected or is_redirecting_path(p)
                       or not p.is_file() for p in children)):
            return result("blocked", "unexpected_or_unsafe_staging_entry")
        identity = operation.stat(follow_symlinks=False)
        return result("eligible_snapshot", "cleanup_preflight_checked",
                      "operation_identity": [identity.st_dev, identity.st_ino],
                      "observed_files": sorted(p.name for p in children),
                      "staging_state": snapshot["state"])
    except OSError:
        return result("blocked", "staging_unreadable")
