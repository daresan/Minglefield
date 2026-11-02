"""Read-only validation of draft game integration installation lock records."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator

_SCHEMA = Path(__file__).resolve().parents[1] / "schemas/integrations/installed-lock-v0.1.schema.json"


def validate_integration_lock(data, *, project_id=None):
    schema=json.loads(_SCHEMA.read_text(encoding="utf-8"))
    errors=sorted(Draft202012Validator(schema).iter_errors(data),key=lambda e:str(e.path))
    if errors:
        raise ValueError("invalid_integration_lock: "+errors[0].message)
    if project_id is not None and data["project_id"]!=project_id:
        raise ValueError("project_mismatch")
    seen=set()
    for entry in data["integrations"]:
        integration_id=entry["integration_id"]
        if integration_id in seen:
            raise ValueError("duplicate_integration_id: "+integration_id)
        seen.add(integration_id)
    return data
