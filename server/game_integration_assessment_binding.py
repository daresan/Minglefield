"""Read-only release identity binding for P1.4f.3 assessment declarations.

Schema validity and exact identity matching are NOT provenance authentication.
The expected identity must come from the already authorized server-side context.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas" / "integrations"
_SCHEMAS = {
    "compatibility": "game-update-compatibility-v0.1.schema.json",
    "migration": "game-update-migration-v0.1.schema.json",
}


def validate_assessment_binding(kind, document, *, expected_integration_id,
                                authorized_source, from_version, to_version):
    """Fail closed without network, filesystem writes, or trust promotion."""
    if kind not in _SCHEMAS:
        return {"state": "invalid", "reason": "unsupported_assessment_kind"}
    if not isinstance(document, dict):
        return {"state": "invalid", "reason": "invalid_assessment_document"}
    try:
        schema = json.loads((_SCHEMA_DIR / _SCHEMAS[kind]).read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(document)
    except Exception:
        # Do not leak untrusted document contents in diagnostics.
        return {"state": "invalid", "reason": "assessment_schema_invalid"}
    if not isinstance(expected_integration_id, str) or not expected_integration_id:
        return {"state": "unknown", "reason": "missing_authorized_identity"}
    if not isinstance(authorized_source, dict) or not all(
        isinstance(v, str) and v for v in (from_version, to_version)
    ):
        return {"state": "unknown", "reason": "missing_authorized_identity"}
    if (document["integration_id"] != expected_integration_id
            or document["release_source"] != authorized_source
            or document["from_version"] != from_version
            or document["to_version"] != to_version):
        return {"state": "invalid", "reason": "assessment_release_identity_mismatch"}
    return {"state": "matched", "reason": "schema_and_release_identity_match",
            "provenance_verified": False, "installation_allowed": False}
