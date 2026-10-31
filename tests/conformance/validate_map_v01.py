#!/usr/bin/env python3
"""MAP v0.1 draft schema and negotiation conformance smoke tests.

Requires Python 3.11+ and jsonschema>=4.18. Uses only local schemas; no network.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas" / "map" / "v0.1"
EXAMPLES = ROOT / "examples" / "map" / "v0.1"
TYPES = {
    "action.submit": "action-submit.schema.json",
    "action.ack": "action-ack.schema.json",
    "event.push": "event-push.schema.json",
    "observation.push": "observation-push.schema.json",
    "protocol.error": "error.schema.json",
}
SCHEMA_FILES = [
    "envelope.schema.json",
    *TYPES.values(),
    "game-manifest.schema.json",
    "capability-offer.schema.json",
    "negotiation-result.schema.json",
    "agent-descriptor.schema.json",
    "delegation-grant.schema.json",
    "delegation-revocation.schema.json",
    "agent-suspension.schema.json",
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def negotiate(manifest: dict, offer: dict) -> dict:
    """Illustrative JSON-only negotiation. Does NOT authenticate participants."""
    common_versions = set(manifest["map_versions"]) & set(offer["map_versions"])
    if not common_versions:
        return {"status": "incompatible", "reason": "no_common_version"}
    version = max(common_versions, key=lambda v: tuple(map(int, v.split("."))))
    profiles = set(offer["interaction_profiles"])
    profile = next((p for p in manifest["interaction_profiles"] if p in profiles), None)
    if profile is None:
        return {"status": "incompatible", "reason": "no_common_profile"}
    common_codecs = set(manifest["codecs"]) & set(offer["codecs"])
    if not common_codecs:
        return {"status": "incompatible", "reason": "no_common_codec"}
    # Only the JSON reference codec is implemented in this draft.
    if "json" not in common_codecs:
        return {"status": "incompatible", "reason": "no_common_codec"}
    required = set(manifest["capabilities"]["required"])
    offered = set(offer["capabilities"])
    if not required <= offered:
        return {"status": "incompatible", "reason": "missing_required_capability"}
    optional = set(manifest["capabilities"]["optional"]) & offered
    return {
        "status": "compatible",
        "map_version": version,
        "interaction_profile": profile,
        "codec": "json",
        "capabilities": sorted(required | optional),
    }


def main() -> None:
    schemas = {name: read_json(SCHEMAS / name) for name in SCHEMA_FILES}
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    validators = {}
    for name, schema in schemas.items():
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(
            schema, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER
        )

    def check(name: str, value, label: str) -> None:
        errors = list(validators[name].iter_errors(value))
        if errors:
            raise AssertionError(f"{label}: {errors[0].message}")

    trace = read_json(EXAMPLES / "async-action-trace.json")
    if not isinstance(trace, list) or not trace:
        raise AssertionError("empty action trace")
    for index, msg in enumerate(trace):
        check(TYPES[msg["type"]], msg, f"trace[{index}]")
    invalid = dict(trace[0])
    invalid.pop("idempotency_key")
    if validators[TYPES["action.submit"]].is_valid(invalid):
        raise AssertionError("negative action test unexpectedly passed")

    manifest = read_json(EXAMPLES / "game-manifest.json")
    offer = read_json(EXAMPLES / "capability-offer.json")
    check("game-manifest.schema.json", manifest, "manifest")
    check("capability-offer.schema.json", offer, "offer")
    cases = read_json(EXAMPLES / "negotiation-cases.json")
    for case in cases:
        check("capability-offer.schema.json", case["offer"], case["name"] + " offer")
        actual = negotiate(manifest, case["offer"])
        check("negotiation-result.schema.json", actual, case["name"] + " result")
        if actual != case["expected"]:
            raise AssertionError(f"{case['name']}: expected {case['expected']}, got {actual}")

    # Negative controls for required manifest fields and invalid negotiation result.
    bad_manifest = dict(manifest)
    bad_manifest.pop("game_id")
    if validators["game-manifest.schema.json"].is_valid(bad_manifest):
        raise AssertionError("missing game_id incorrectly accepted")
    if validators["negotiation-result.schema.json"].is_valid(
        {"status": "compatible", "reason": "no_common_version"}
    ):
        raise AssertionError("inconsistent negotiation result incorrectly accepted")


    # Draft shared-agent examples and stateful authorization controls.
    agent = read_json(EXAMPLES / "shared-agent.json")
    grant = read_json(EXAMPLES / "delegation-grant.json")
    revocation = read_json(EXAMPLES / "delegation-revocation.json")
    suspension = read_json(EXAMPLES / "agent-suspension.json")
    for name, value in [
        ("agent-descriptor.schema.json", agent),
        ("delegation-grant.schema.json", grant),
        ("delegation-revocation.schema.json", revocation),
        ("agent-suspension.schema.json", suspension),
    ]:
        check(name, value, name)
    operators = {
        operator["user_id"]: set(operator["roles"])
        for operator in agent["operators"]
    }

    def authorize(requester, scope, at, revoked=False, suspended=False):
        from datetime import datetime
        def dt(value):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (
            not suspended
            and not revoked
            and agent["state"] == "active"
            and grant["status"] == "active"
            and grant["agent_id"] == agent["agent_id"]
            and requester == grant["requester_user_id"]
            and scope in grant["scopes"]
            and scope in agent["policy"]["allowed_scopes"]
            and dt(grant["issued_at"]) <= dt(at) < dt(grant["expires_at"])
        )

    assert "approver" in operators[grant["issuer_user_id"]]
    assert revocation["delegation_id"] == grant["delegation_id"]
    assert suspension["agent_id"] == agent["agent_id"]
    assert authorize("user.charlie", "game.test_feedback", "2026-10-31T12:15:00Z")
    assert not authorize("user.other", "game.test_feedback", "2026-10-31T12:15:00Z")
    assert not authorize("user.charlie", "game.develop", "2026-10-31T12:15:00Z")
    assert not authorize("user.charlie", "game.test_feedback", "2026-10-31T15:00:00Z")
    assert not authorize("user.charlie", "game.test_feedback", "2026-10-31T12:35:00Z", revoked=True)
    assert not authorize("user.charlie", "game.test_feedback", "2026-10-31T12:35:00Z", suspended=True)
    invalid_agent = dict(agent)
    invalid_agent["operators"] = []
    assert not validators["agent-descriptor.schema.json"].is_valid(invalid_agent)

    print(
        f"PASS: {len(schemas)} schemas, {len(trace)} action trace messages, "
        f"{len(cases)} negotiation cases, 3 baseline negative controls, shared-agent authorization checks"
    )


if __name__ == "__main__":
    main()
