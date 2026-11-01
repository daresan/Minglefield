"""Read-only SEC-01 projection of committed B2 intent; NOT a capability.

No authorization, executor authentication, effect admission or external calls.
Do not expose the projected effect key to untrusted callers.
"""
import hashlib
import hmac
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass

from action_service import _canonical
from b2_validation import valid_request


@dataclass(frozen=True)
class CommittedIntent:
    contract_version: int
    job_id: str
    user_id: str
    agent_id: str
    delegation_id: str
    action_type: str
    scope: str
    target_id: str
    request_fingerprint: str
    policy_revision: int
    adapter_id: str
    adapter_version: str
    effect_idempotency_key: str


def project_committed_intent(database, *, job_id):
    """Return a frozen internal snapshot or None if job is not committed.

    Raises ValueError for a malformed committed record. No live policy is
    evaluated; this projection is NOT permission to invoke any effect.
    """
    if type(job_id) is not str or not 1 <= len(job_id) <= 128:
        raise ValueError("invalid job id")
    with closing(sqlite3.connect(str(database), timeout=10)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        version = db.execute(
            "SELECT version FROM action_schema WHERE singleton=1").fetchone()
        if version != (4,):
            raise ValueError("projection requires action schema v4")
        row = db.execute("""SELECT job_id,user_id,agent_id,delegation_id,
            request_json,fingerprint,dispatch_fingerprint,policy_revision,
            adapter_id,adapter_version,effect_idempotency_key,state
            FROM action_jobs WHERE job_id=?""", (job_id,)).fetchone()
        if row is None or row[11] != "dispatch_committed":
            return None
        (jid, user, agent, grant, raw, fingerprint, dispatched, revision,
         adapter_id, adapter_version, effect_key, _) = row
        try:
            request = json.loads(raw)
            if not valid_request(request):
                raise ValueError("malformed request")
            canonical = _canonical(request)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if (canonical != raw
                    or type(fingerprint) is not str or len(fingerprint) != 64
                    or type(dispatched) is not str or len(dispatched) != 64
                    or not hmac.compare_digest(fingerprint, digest)
                    or not hmac.compare_digest(dispatched, digest)
                    or (request["user_id"], request["agent_id"],
                        request["delegation_id"]) != (user, agent, grant)
                    or type(revision) is not int or revision < 0
                    or any(type(v) is not str or not 1 <= len(v) <= 128
                           for v in (adapter_id, adapter_version))
                    or type(effect_key) is not str
                    or not effect_key.startswith("effect.")
                    or len(effect_key) != 71
                    or any(c not in "0123456789abcdef" for c in effect_key[7:])):
                raise ValueError("invalid committed binding")
        except (TypeError, KeyError, ValueError, OverflowError, RecursionError) as exc:
            raise ValueError("invalid committed intent") from exc
        return CommittedIntent(
            contract_version=1, job_id=jid, user_id=user, agent_id=agent,
            delegation_id=grant, action_type=request["action_type"],
            scope=request["scope"], target_id=request["target_id"],
            request_fingerprint=digest, policy_revision=revision,
            adapter_id=adapter_id, adapter_version=adapter_version,
            effect_idempotency_key=effect_key)
