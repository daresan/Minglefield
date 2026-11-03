"""Read-only operator-provisioned assessment approval manifest.

This parser does not grant approval: the operator must provision the file
through a trusted deployment/configuration channel outside user-controlled
uploads, lockfiles, release metadata and the public fixture registry.
Missing or malformed configuration fails closed.
"""
import json
from pathlib import Path

from game_integration_assessment_resolver import make_assessment_resolver

_MAX_MANIFEST_BYTES = 1024 * 1024


def read_operator_approvals(path):
    """Read an explicitly configured local manifest, never a default repo path."""
    if not isinstance(path, (str, Path)) or not str(path):
        raise ValueError("operator_manifest_not_configured")
    candidate = Path(path)
    if not candidate.is_absolute() or candidate.is_symlink() or not candidate.is_file():
        raise ValueError("invalid_operator_manifest_path")
    if candidate.stat().st_size > _MAX_MANIFEST_BYTES:
        raise ValueError("operator_manifest_too_large")
    with candidate.open("rb") as stream:
        raw = stream.read(_MAX_MANIFEST_BYTES + 1)
    if len(raw) > _MAX_MANIFEST_BYTES:
        raise ValueError("operator_manifest_too_large")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid_operator_manifest") from exc
    if not isinstance(data, dict) or set(data) != {"format_version", "approvals"}:
        raise ValueError("invalid_operator_manifest")
    if data["format_version"] != "0.1" or not isinstance(data["approvals"], list):
        raise ValueError("invalid_operator_manifest")
    records = {}
    for row in data["approvals"]:
        if not isinstance(row, dict) or set(row) != {
            "kind", "integration_id", "repository", "from_version",
            "to_version", "commit", "sha256"
        }:
            raise ValueError("invalid_operator_approval")
        key = (row["kind"], row["integration_id"], row["repository"],
               row["from_version"], row["to_version"])
        try:
            if key in records:
                raise ValueError("duplicate_operator_approval")
            records[key] = {"commit": row["commit"], "sha256": row["sha256"]}
        except TypeError as exc:
            raise ValueError("invalid_operator_approval") from exc
    # Delegate digest/commit/identity format validation to the resolver.
    make_assessment_resolver(records, byte_loader=lambda *args: None)
    return records


def make_operator_assessment_resolver(path, *, byte_loader):
    """Build resolver only from a separately provisioned operator manifest."""
    return make_assessment_resolver(read_operator_approvals(path),
                                    byte_loader=byte_loader)
