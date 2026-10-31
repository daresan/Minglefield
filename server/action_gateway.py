"""MAP v0.3 experimental authenticated action gateway.

Only delegates identity from a verified bearer session; policy decision remains
in SQLitePolicyEngine. Not a network server or atomic cross-store dispatcher.
"""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class GatewayDecision:
    allowed: bool
    reason: str


class ActionGateway:
    def __init__(self, sessions, policy, *, clock=None):
        self.sessions = sessions
        self.policy = policy
        self.clock = clock if clock is not None else sessions.clock

    def authorize(self, *, token, delegation_id, agent_id, scope, target_id,
                  cost_minor=0, operation_id=None):
        session = self.sessions.verify(token, agent_id=agent_id,
                                       delegation_id=delegation_id)
        if session is None or session.delegation_id is None:
            return GatewayDecision(False, "invalid_session")
        at = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()
        result = self.policy.authorize(
            verified_requester=session.user_id,
            expected_agent_id=session.agent_id,
            delegation_id=delegation_id,
            scope=scope, target_id=target_id, at=at,
            cost_minor=cost_minor, operation_id=operation_id)
        return GatewayDecision(result.allowed, result.reason)
