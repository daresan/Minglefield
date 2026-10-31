"""Structural checks for persisted B2 records; no external schema dependency.

This checks record shape, not operator authority, session validity or budget state.
Those remain transactional checks in the caller.
"""
import re

from action_service import MAX_INT

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SCOPE = re.compile(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_-]*)+\Z")
_ROLES = {"admin", "approver", "runtime_operator", "billing", "auditor"}


def _id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _integer(value):
    return type(value) is int and 0 <= value <= MAX_INT


def _unique_strings(values, predicate):
    return (type(values) is list and bool(values)
            and all(predicate(value) for value in values)
            and len(values) == len(set(values)))


def valid_request(value):
    return (type(value) is dict
            and set(value) == {"version", "user_id", "agent_id", "delegation_id",
                               "target_id", "action_type", "scope", "parameters"}
            and type(value["version"]) is int and value["version"] == 1
            and all(_id(value[key]) for key in
                    ("user_id", "agent_id", "delegation_id", "target_id"))
            and type(value["action_type"]) is str and bool(value["action_type"])
            and len(value["action_type"]) <= 128
            and type(value["scope"]) is str and bool(value["scope"])
            and type(value["parameters"]) is dict)


def valid_grant(value):
    required = {"delegation_id", "agent_id", "issuer_user_id", "requester_user_id",
                "scopes", "issued_at", "expires_at", "status"}
    optional = {"target_id", "max_spend_minor", "approval_ref"}
    return (type(value) is dict and required <= set(value)
            and set(value) <= required | optional
            and all(_id(value[key]) for key in
                    ("delegation_id", "agent_id", "issuer_user_id", "requester_user_id"))
            and all(_id(value[key]) for key in ("target_id", "approval_ref") if key in value)
            and _unique_strings(value["scopes"], lambda scope: type(scope) is str
                                and _SCOPE.fullmatch(scope) is not None)
            and all(type(value[key]) is str for key in ("issued_at", "expires_at"))
            and value["status"] in ("active", "revoked", "expired")
            and ("max_spend_minor" not in value or _integer(value["max_spend_minor"])))


def valid_agent(value):
    required = {"agent_id", "operators", "accountable_party_id", "state", "revision"}
    optional = {"runtime", "policy"}
    if (type(value) is not dict or not required <= set(value)
            or not set(value) <= required | optional
            or not _id(value["agent_id"]) or not _id(value["accountable_party_id"])
            or value["state"] not in ("active", "suspended")
            or not _integer(value["revision"])
            or ("runtime" in value and value["runtime"] not in
                ("self_hosted", "third_party_cloud", "minglefield_managed"))):
        return False
    operators = value["operators"]
    if type(operators) is not list or not operators:
        return False
    seen = set()
    for operator in operators:
        if (type(operator) is not dict or set(operator) != {"user_id", "roles"}
                or not _id(operator["user_id"])
                or operator["user_id"] in seen
                or not _unique_strings(operator["roles"],
                                       lambda role: type(role) is str and role in _ROLES)):
            return False
        seen.add(operator["user_id"])
    if "policy" in value:
        policy = value["policy"]
        if type(policy) is not dict or not set(policy) <= {
                "max_spend_minor", "max_concurrent_tasks", "allowed_scopes"}:
            return False
        if any(not _integer(policy[key]) for key in
               ("max_spend_minor", "max_concurrent_tasks") if key in policy):
            return False
        if ("allowed_scopes" in policy and
                not (type(policy["allowed_scopes"]) is list
                     and all(type(scope) is str and bool(scope) for scope in policy["allowed_scopes"])
                     and len(policy["allowed_scopes"]) == len(set(policy["allowed_scopes"])))):
            return False
    return True
