"""Read-only inspection of isolated flat-v1 installation staging operations.

Inspection is a snapshot, not authorization to install, resume, or delete.
No filesystem mutations are performed.
"""
import hashlib
import json
import os
import re
from pathlib import Path

from game_integration_install_path_safety import has_redirecting_component, is_redirecting_path
from game_integration_install_staging import validate_staging_manifest

_OPERATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_BLOB = re.compile(r"blob-[0-9]{6}")


def inspect_staged_installation(installation_staging_root, operation_id, entries):
    """Classify an operation against a trusted, independently supplied plan."""
    def result(state, reason):
        return {"state": state, "reason": reason,
                "installation_allowed": False, "mutation_performed": False}
    plan = validate_staging_manifest(entries)
    if plan["state"] != "valid":
        return result("blocked", plan["reason"])
    if (type(operation_id) is not str or not _OPERATION.fullmatch(operation_id)
            or operation_id in (".", "..")):
        return result("blocked", "invalid_operation_id")
    root = Path(installation_staging_root)
    if not root.is_dir() or has_redirecting_component(root):
        return result("blocked", "unsafe_installation_staging_root")
    operation = root / operation_id
    if is_redirecting_path(operation):
        return result("blocked", "unsafe_operation_path")
    if not operation.exists():
        return result("absent", "operation_not_found")
    if not operation.is_dir():
        return result("blocked", "operation_not_directory")
    if has_redirecting_component(operation):
        return result("blocked", "unsafe_operation_path")
    try:
        children = list(operation.iterdir())
        if any(is_redirecting_path(child) or not child.is_file() for child in children):
            return result("blocked", "unsafe_staging_entry")
        names = {child.name for child in children}
        if len(names) != len(children):
            return result("damaged", "duplicate_staging_entry")
        expected_blobs = {f"blob-{i:06d}" for i in range(len(plan["files"]))}
        if names - (expected_blobs | {"manifest.json"}):
            return result("damaged", "unexpected_staging_entry")
        if "manifest.json" not in names:
            return result("incomplete", "missing_manifest")
        raw = (operation / "manifest.json").read_bytes()
        if len(raw) > 1024 * 1024:
            return result("damaged", "invalid_manifest")
        mapping = json.loads(raw.decode("utf-8"))
        expected_mapping = {
            "plan_sha256": plan["plan_sha256"],
            "files": [
                {"path": entry["path"], "blob": f"blob-{i:06d}",
                 "size": entry["size"], "sha256": entry["sha256"]}
                for i, entry in enumerate(plan["files"])
            ],
        }
        if mapping != expected_mapping:
            return result("damaged", "manifest_mismatch")
        if names != expected_blobs | {"manifest.json"}:
            return result("incomplete", "missing_blob")
        for i, entry in enumerate(plan["files"]):
            blob = operation / f"blob-{i:06d}"
            if is_redirecting_path(blob):
                return result("blocked", "unsafe_staging_entry")
            digest = hashlib.sha256()
            size = 0
            with blob.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > entry["size"]:
                        return result("damaged", "blob_mismatch")
                    digest.update(chunk)
            if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
                return result("damaged", "blob_mismatch")
        return result("complete_snapshot", "staged_bytes_verified")
    except (OSError, ValueError, UnicodeError, TypeError, OverflowError):
        return result("damaged", "staging_unreadable")
