"""Offline validation of the proposed unified game package lock (no filesystem writes)."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator

_SCHEMA=Path(__file__).resolve().parents[1]/"schemas/integrations/unified-package-lock-v0.1.schema.json"


def validate_package_lock(data, *, project_id=None):
    schema=json.loads(_SCHEMA.read_text(encoding="utf-8"))
    errors=sorted(Draft202012Validator(schema).iter_errors(data),key=lambda e:str(e.path))
    if errors:
        raise ValueError("invalid_package_lock: "+errors[0].message)
    if project_id is not None and data["project_id"]!=project_id:
        raise ValueError("project_mismatch")
    seen=set()
    for package in data["packages"]:
        package_id=package["package_id"]
        if package_id in seen:
            raise ValueError("duplicate_package_id: "+package_id)
        seen.add(package_id)
    return data


def lock_source_state(*, alpha_exists, root_exists):
    """Format selection only; callers must separately reject symlinks and malformed files."""
    if alpha_exists and root_exists:
        return "conflicting_lock_sources"
    if root_exists:
        return "unified_lock_declared"
    if alpha_exists:
        return "legacy_alpha_lock"
    return "installation_unknown"
