"""Isolated installer byte staging (P1.4f.4).

Writes only under a dedicated installation_staging_root. Does not modify game
repositories, host job attachments, journal state, or existing operation dirs.
Not an installation executor or authorization boundary.
"""
import hashlib
import os
import re
import shutil
from pathlib import Path

from game_integration_install_paths import inspect_installation_paths
from game_integration_install_staging import validate_staging_manifest

_OPERATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


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
    if not root.is_dir() or root.is_symlink():
        return blocked("unsafe_installation_staging_root")
    root = root.resolve(strict=True)
    repository = Path(repository_root)
    if not repository.is_dir() or repository.is_symlink():
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
    operation = root / operation_id
    try:
        operation.mkdir(mode=0o700)
    except FileExistsError:
        return blocked("operation_staging_already_exists")
    except OSError:
        return blocked("staging_directory_unavailable")
    try:
        for relative, data in verified:
            target = operation.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
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
        # Only remove the directory exclusively created by this call.
        shutil.rmtree(operation)
        return blocked("staging_write_failed")
