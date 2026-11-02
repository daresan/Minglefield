"""MAP v0.3 experimental authenticated action gateway.

Only delegates identity from a verified bearer session; policy decision remains
in SQLitePolicyEngine. Not a network server or atomic cross-store dispatcher.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from session_store import _digest


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
        # The earlier verification is only a compatibility check. The authoritative
        # session check and budget reservation must share one SQLite writer lock.
        if self.sessions.database != self.policy.database:
            return GatewayDecision(False, "invalid_session")
        with self.policy._tx() as db:
            row = db.execute("""SELECT s.user_id,s.agent_id,s.delegation_id,
                s.expires_at,s.revoked,p.disabled FROM auth_sessions s
                JOIN auth_principals p ON p.user_id=s.user_id
                WHERE s.token_hash=?""", (_digest(token),)).fetchone()
            if (not row or row[4] or row[5] or row[0] != session.user_id
                    or row[1] != agent_id or row[2] != delegation_id
                    or int(self.sessions.clock()) >= row[3]):
                return GatewayDecision(False, "invalid_session")
            at = datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()
            result = self.policy.authorize(
                verified_requester=row[0],
                expected_agent_id=row[1],
                delegation_id=delegation_id,
                scope=scope, target_id=target_id, at=at,
                cost_minor=cost_minor, operation_id=operation_id, _db=db)
        return GatewayDecision(result.allowed, result.reason)
