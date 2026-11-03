"""Isolated installer byte staging (P1.4f.4).

Writes only under a dedicated installation_staging_root. Does not modify game
repositories, host job attachments, journal state, or existing operation dirs.
Not an installation executor or authorization boundary. Path identity checks\nreduce accidental replacement risks but cannot eliminate adversarial TOCTOU\nwithout platform-specific handle-relative operations and exclusive locking.
"""
import hashlib
import os
import re
from pathlib import Path

from game_integration_install_paths import inspect_installation_paths
from game_integration_install_path_safety import has_redirecting_component, is_redirecting_path
from game_integration_install_staging import validate_staging_manifest

_OPERATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _same_directory(path, identity):
    """Detect directory replacement; not an atomic cross-platform lock."""
    try:
        stat = path.stat(follow_symlinks=False)
        return (not is_redirecting_path(path) and path.is_dir()
                and (stat.st_dev, stat.st_ino) == identity)
    except OSError:
        return False


def stage_installation_bytes(installation_staging_root, operation_id,
                             repository_root, entries, byte_loader):
    """Stage verified bytes in a new, exclusively owned operation directory.

    Caller must have performed trusted owner/source/release authorization.
    The destination repository is inspected but never changed.
    """
    def blocked(reason):
        return {"state": "blocked", "reason": reason,
                "installation_allowed": False}
    plan = validate_staging_manifest(entries)
    if plan["state"] != "valid":
        return blocked(plan["reason"])
    if type(operation_id) is not str or not _OPERATION.fullmatch(operation_id) or operation_id in (".", ".."):
        return blocked("invalid_operation_id")
    if not callable(byte_loader):
        return blocked("missing_staging_reader")
    root = Path(installation_staging_root)
    if not root.is_dir() or has_redirecting_component(root):
        return blocked("unsafe_installation_staging_root")
    root = root.resolve(strict=True)
    repository = Path(repository_root)
    if not repository.is_dir() or has_redirecting_component(repository):
        return blocked("unsafe_repository_root")
    repository = repository.resolve(strict=True)
    if root == repository or root.is_relative_to(repository) or repository.is_relative_to(root):
        return blocked("staging_repository_overlap")
    inspection = inspect_installation_paths(repository, [f["path"] for f in plan["files"]])
    if inspection["state"] != "ready_for_staging":
        return blocked(inspection["reason"])
    # Verify all bytes before creating any staging directory.
    verified = []
    for item in plan["files"]:
        try:
            data = byte_loader(item["path"])
        except (OSError, ValueError, KeyError):
            return blocked("staged_file_unavailable")
        if (type(data) is not bytes or len(data) != item["size"]
                or hashlib.sha256(data).hexdigest() != item["sha256"]):
            return blocked("staged_bytes_mismatch")
        verified.append((item["path"], data))
    root_identity = (root.stat().st_dev, root.stat().st_ino)
    if not _same_directory(root, root_identity):
        return blocked("staging_root_changed")
    operation = root / operation_id
    try:
        operation.mkdir(mode=0o700)
    except FileExistsError:
        return blocked("operation_staging_already_exists")
    except OSError:
        return blocked("staging_directory_unavailable")
    operation_identity = (operation.stat().st_dev, operation.stat().st_ino)
    try:
        for relative, data in verified:
            if not _same_directory(root, root_identity) or not _same_directory(operation, operation_identity):
                return blocked("staging_directory_changed")
            target = operation.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            if (has_redirecting_component(target.parent)
                    or not _same_directory(root, root_identity)
                    or not _same_directory(operation, operation_identity)):
                return blocked("unsafe_staging_path")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(target, flags, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        return {"state": "staged", "operation_id": operation_id,
                "plan_sha256": plan["plan_sha256"],
                "files_staged": len(verified),
                "installation_allowed": False}
    except OSError:
        # Preserve partial operation for explicit inspection. Never recursively
        # delete a path that an attacker might have replaced during staging.
        return blocked("staging_write_failed")
