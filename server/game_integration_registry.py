"""Offline validation for the curated Minglefield integration registry.

Shape validation uses the repository JSON Schema; this module checks cross-entry
invariants. It performs no network, filesystem mutation, or code execution.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA = _ROOT / "schemas" / "integrations" / "registry-v0.1.schema.json"
_REGISTRY = _ROOT / "integrations" / "registry.json"


def validate_registry(data, *, schema_path=_SCHEMA):
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: str(e.path))
    if errors:
        raise ValueError("invalid_registry_schema: " + errors[0].message)
    seen = set()
    for entry in data["integrations"]:
        integration_id = entry["integration_id"]
        if integration_id in seen:
            raise ValueError("duplicate_integration_id: " + integration_id)
        seen.add(integration_id)
        tier = entry["trust_tier"]
        if tier == "official" and not integration_id.startswith("minglefield."):
            raise ValueError("official_namespace_required: " + integration_id)
        if tier == "community" and not integration_id.startswith("community."):
            raise ValueError("community_namespace_required: " + integration_id)
        if tier == "community" and len(integration_id.split(".")) < 3:
            raise ValueError("community_publisher_namespace_required: " + integration_id)
        if tier == "community" and integration_id.split(".")[1] != entry["publisher"]:
            raise ValueError("community_publisher_mismatch: " + integration_id)
    return data


def load_registry(path=_REGISTRY):
    return validate_registry(json.loads(Path(path).read_text(encoding="utf-8")))
