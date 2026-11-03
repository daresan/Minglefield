"""P1.4f.4 immutable staging manifest validation; no writes or installation.

The manifest is generated from server-verified bytes, never trusted as proof
merely because a caller supplied a digest.
"""
import hashlib
import json
import re
from game_integration_install_paths import _valid_relative_path

_SHA = re.compile(r"^[0-9a-f]{64}$")


def validate_staging_manifest(entries):
    """Normalize a bounded plan and calculate its deterministic SHA-256 identity."""
    def denied(reason):
        return {"state": "blocked", "reason": reason, "mutation_performed": False}
    if type(entries) is not list or not 1 <= len(entries) <= 1000:
        return denied("invalid_staging_entries")
    normalized = []
    for entry in entries:
        if type(entry) is not dict or set(entry) != {"path", "sha256", "size"}:
            return denied("invalid_staging_entry")
        path, digest, size = entry["path"], entry["sha256"], entry["size"]
        if (not _valid_relative_path(path) or type(digest) is not str
                or not _SHA.fullmatch(digest) or type(size) is not int
                or not 0 <= size <= 1024 * 1024 * 1024):
            return denied("invalid_staging_entry")
        normalized.append({"path": path, "sha256": digest, "size": size})
    keys = [entry["path"].casefold() for entry in normalized]
    if len(set(keys)) != len(keys):
        return denied("duplicate_destination_path")
    ordered = sorted(keys)
    if any(b.startswith(a + "/") for a, b in zip(ordered, ordered[1:])):
        return denied("overlapping_destination_paths")
    normalized.sort(key=lambda item: item["path"])
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"state": "valid", "plan_sha256": hashlib.sha256(canonical).hexdigest(),
            "files": normalized, "mutation_performed": False}


def verify_staged_bytes(manifest, byte_loader):
    """Compare actual staged bytes against expected sizes and hashes.

    byte_loader is an internal server-side reader, not a client-controlled
    callback. This is a snapshot check; the executor must recheck under lock.
    """
    if not isinstance(manifest, dict) or manifest.get("state") != "valid":
        return {"state": "blocked", "reason": "invalid_staging_manifest"}
    if not callable(byte_loader):
        return {"state": "blocked", "reason": "missing_staging_reader"}
    for entry in manifest["files"]:
        try:
            raw = byte_loader(entry["path"])
        except (OSError, ValueError, KeyError):
            return {"state": "blocked", "reason": "staged_file_unavailable",
                    "path": entry["path"]}
        if (type(raw) is not bytes or len(raw) != entry["size"] or
                hashlib.sha256(raw).hexdigest() != entry["sha256"]):
            return {"state": "blocked", "reason": "staged_bytes_mismatch",
                    "path": entry["path"]}
    return {"state": "verified_snapshot", "plan_sha256": manifest["plan_sha256"],
            "installation_allowed": False}
