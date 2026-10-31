#!/usr/bin/env python3
"""Validate the MAP v0.1 draft JSON schemas and example trace (Python 3.11+)."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas" / "map" / "v0.1"
TRACE = ROOT / "examples" / "map" / "v0.1" / "async-action-trace.json"
TYPES = {
    "action.submit": "action-submit.schema.json",
    "action.ack": "action-ack.schema.json",
    "event.push": "event-push.schema.json",
    "observation.push": "observation-push.schema.json",
    "protocol.error": "error.schema.json",
}


def load(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def main() -> None:
    schemas = {name: load(name) for name in ["envelope.schema.json", *TYPES.values()]}
    for name, schema in schemas.items():
        Draft202012Validator.check_schema(schema)
    store = {}
    for name, schema in schemas.items():
        store[schema["$id"]] = schema
        store[name] = schema
    messages = json.loads(TRACE.read_text(encoding="utf-8"))
    assert isinstance(messages, list) and messages
    for i, message in enumerate(messages):
        kind = message["type"]
        schema = schemas[TYPES[kind]]
        resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
        validator = Draft202012Validator(schema, resolver=resolver, format_checker=Draft202012Validator.FORMAT_CHECKER)
        errors = list(validator.iter_errors(message))
        if errors:
            raise AssertionError(f"trace[{i}] {kind}: {errors[0].message}")
    # Negative control: an action without its required idempotency key must fail.
    invalid = dict(messages[0])
    invalid.pop("idempotency_key")
    schema = schemas[TYPES["action.submit"]]
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    assert not Draft202012Validator(schema, resolver=resolver).is_valid(invalid)
    print(f"PASS: {len(schemas)} schemas, {len(messages)} example messages, 1 negative control")


if __name__ == "__main__":
    main()
