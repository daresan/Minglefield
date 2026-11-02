"""MAP v0.1 reference policy decision point (draft, in-memory, stdlib only).
Caller MUST authenticate verified_actor / verified_requester and validate input schemas.
Not a production security boundary or distributed emergency stop.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock


def utc(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


class PolicyEngine:
    def __init__(self, agent):
        self.agent = agent
        self.lock = RLock()
        self.grants = {}
        self.revoked = set()
        self.suspended = agent.get("state") != "active"
        self.spent = {}
        self.seen = {}

    def roles(self, actor):
        return {role for op in self.agent["operators"]
                if op["user_id"] == actor for role in op["roles"]}

    def add_grant(self, grant, *, verified_actor):
        with self.lock:
            if self.suspended:
                return Decision(False, "agent_suspended")
            if grant["agent_id"] != self.agent["agent_id"]:
                return Decision(False, "wrong_agent")
            if grant["issuer_user_id"] != verified_actor or "approver" not in self.roles(verified_actor):
                return Decision(False, "not_authorized_approver")
            if grant["status"] != "active" or utc(grant["issued_at"]) >= utc(grant["expires_at"]):
                return Decision(False, "invalid_grant")
            if not set(grant["scopes"]) <= set(self.agent.get("policy", {}).get("allowed_scopes", [])):
                return Decision(False, "scope_exceeds_policy")
            key = grant["delegation_id"]
            if key in self.grants or key in self.revoked:
                return Decision(False, "duplicate_or_revoked_grant")
            self.grants[key] = dict(grant)
            self.spent[key] = 0
            return Decision(True, "grant_added")

    def authorize(self, *, verified_requester, delegation_id, scope, target_id, at,
                  cost_minor=0, operation_id=None):
        with self.lock:
            if self.suspended:
                return Decision(False, "agent_suspended")
            if delegation_id in self.revoked:
                return Decision(False, "grant_revoked")
            grant = self.grants.get(delegation_id)
            if grant is None:
                return Decision(False, "unknown_grant")
            if grant["status"] != "active" or grant["requester_user_id"] != verified_requester:
                return Decision(False, "requester_or_grant_mismatch")
            if scope not in grant["scopes"] or scope not in self.agent.get("policy", {}).get("allowed_scopes", []):
                return Decision(False, "scope_denied")
            if grant.get("target_id") != target_id:
                return Decision(False, "target_denied")
            if not utc(grant["issued_at"]) <= utc(at) < utc(grant["expires_at"]):
                return Decision(False, "outside_validity")
            if type(cost_minor) is not int or cost_minor < 0:
                return Decision(False, "invalid_cost")
            if cost_minor and not operation_id:
                return Decision(False, "operation_id_required")
            opkey = (delegation_id, operation_id) if operation_id is not None else None
            fingerprint = (verified_requester, scope, target_id, cost_minor)
            if opkey in self.seen:
                previous, decision = self.seen[opkey]
                return decision if previous == fingerprint else Decision(False, "operation_id_conflict")
            grant_limit = grant.get("max_spend_minor")
            agent_limit = self.agent.get("policy", {}).get("max_spend_minor")
            if grant_limit is not None and self.spent[delegation_id] + cost_minor > grant_limit:
                return Decision(False, "budget_exceeded")
            if agent_limit is not None and sum(self.spent.values()) + cost_minor > agent_limit:
                return Decision(False, "budget_exceeded")
            self.spent[delegation_id] += cost_minor
            result = Decision(True, "allowed")
            if opkey is not None:
                self.seen[opkey] = (fingerprint, result)
            return result

    def revoke(self, *, delegation_id, verified_actor):
        with self.lock:
            grant = self.grants.get(delegation_id)
            if grant is None:
                return Decision(False, "unknown_grant")
            if verified_actor != grant["requester_user_id"] and not (
                    self.roles(verified_actor) & {"admin", "approver"}):
                return Decision(False, "not_authorized")
            self.revoked.add(delegation_id)
            return Decision(True, "revoked")

    def suspend(self, *, verified_actor):
        with self.lock:
            if not self.roles(verified_actor) & {"admin", "approver"}:
                return Decision(False, "not_authorized")
            self.suspended = True
            return Decision(True, "suspended")

    def resume(self, *, verified_actor):
        with self.lock:
            if "admin" not in self.roles(verified_actor):
                return Decision(False, "not_authorized")
            self.suspended = False
            return Decision(True, "resumed")
