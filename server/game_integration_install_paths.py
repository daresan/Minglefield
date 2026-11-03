"""P1.4f.4: validate destination paths without writing to the game repository.

The plan is advisory only. Artifact identity and approval are separate gates.
"""
import os
import re
from pathlib import Path, PurePosixPath

_DRIVE = re.compile(r"^[A-Za-z]:")
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                     *(f"LPT{i}" for i in range(1, 10))}


def _valid_relative_path(value):
    if not isinstance(value, str) or not value or len(value) > 1024:
        return False
    if (value.startswith("/") or "\\" in value or "\x00" in value or
            _DRIVE.match(value) or "//" in value):
        return False
    parts = value.split("/")
    if any(p in ("", ".", "..") or p.endswith((" ", ".")) or
           ":" in p or any(ord(c) < 32 for c in p) or
           p.split(".")[0].upper() in _WINDOWS_RESERVED for p in parts):
        return False
    return str(PurePosixPath(value)) == value


def inspect_installation_paths(repository_root, destinations):
    """Fail closed on path escape, collisions, existing files and symlink traversal.

    Does not trust the proposed paths or write to disk. Existing destinations
    are conflicts until a separate replacement/backup policy is implemented.
    """
    def denied(reason, **extra):
        return {"state": "blocked", "reason": reason, "paths": [], **extra}
    if (not isinstance(repository_root, (str, os.PathLike)) or
            type(destinations) is not list or len(destinations) > 10000):
        return denied("invalid_installation_plan")
    root = Path(repository_root)
    if not root.is_dir() or root.is_symlink():
        return denied("unsafe_repository_root")
    if not destinations or any(not _valid_relative_path(p) for p in destinations):
        return denied("invalid_destination_path")
    normalized = [p.casefold() for p in destinations]
    if len(set(normalized)) != len(normalized):
        return denied("duplicate_destination_path")
    ordered = sorted(normalized)
    if any(b.startswith(a + "/") for a, b in zip(ordered, ordered[1:])):
        return denied("overlapping_destination_paths")
    root_resolved = root.resolve(strict=True)
    conflicts = []
    for relative in destinations:
        current = root
        for part in relative.split("/"):
            current = current / part
            if current.is_symlink():
                return denied("symlink_in_destination", path=relative)
        if not current.resolve(strict=False).is_relative_to(root_resolved):
            return denied("destination_outside_repository", path=relative)
        if current.exists():
            conflicts.append(relative)
    if conflicts:
        return denied("existing_destination_conflicts", conflicting_paths=conflicts)
    return {"state": "ready_for_staging", "reason": "paths_checked",
            "paths": list(destinations), "mutation_performed": False}
