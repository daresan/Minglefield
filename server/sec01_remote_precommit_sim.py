"""SEC-01 LOCAL proof issuer and online executor recheck -- simulation ONLY.

Proof issuance is contingent on a NEW integrated Alpha admission. The mock
HMAC proof is not transferable trust for real independent executors. At the
executor boundary online recheck is mandatory; failed authority connection
denies. NO effect, game receipt or ComfyUI execution is performed.

The gap between an online recheck and a future remote game commit is NOT
atomic. Therefore this component deliberately cannot trigger any effect.
"""
import json
import sqlite3
from dataclasses import dataclass

from private_alpha_auth import ident
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_mock_admission_proof import issue_mock_proof, verify_mock_proof


@dataclass(frozen=True)
class RemoteCheck:
    allowed: bool
    reason: str


class LocalProofIssuer:
    def __init__(self, authority, *, issuer_secret, issuer="alpha.local"):
        if type(authority) is not IntegratedAlphaAdmission:
            raise TypeError("requires integrated Alpha authority")
        if type(issuer_secret) is not bytes or len(issuer_secret)<32 or not ident(issuer):
            raise ValueError("invalid fixture key or issuer")
        self.authority=authority
        self.secret=issuer_secret
        self.issuer=issuer

    def issue(self, authorization, *, effect_key, job_id, fingerprint,
              agent_id, owner_id, executor_id, host_id, now, ttl=30):
        if (type(now) is not int or type(ttl) is not int or not 1<=ttl<=60
                or now<0 or not all(ident(v) for v in
                    (effect_key,job_id,fingerprint,agent_id,owner_id,executor_id,host_id))):
            return None
        accepted=self.authority.admit(authorization,effect_key=effect_key,
            job_id=job_id,fingerprint=fingerprint,agent_id=agent_id,
            owner_id=owner_id,executor_id=executor_id,host_id=host_id)
        if not accepted.accepted or accepted.reason!="admitted_once_no_effect":
            return None
        payload=dict(version=1,issuer=self.issuer,audience=host_id,
                     job_id=job_id,request_fingerprint=fingerprint,
                     effect_key=effect_key,executor=executor_id,
                     issued_at=now,expires_at=now+ttl,nonce=effect_key)
        return issue_mock_proof(payload,issuer_secret=self.secret)


def online_precommit_check(authority, proof, *, verifier_secret, issuer,
                           requester_id, agent_id, owner_id, executor_id,
                           host_id, job_id, fingerprint, effect_key, now):
    """Fail closed on authority outage. Returns PRECHECK ONLY, never execution."""
    if (type(verifier_secret) is not bytes or len(verifier_secret)<32
            or type(now) is not int or not all(ident(v) for v in
                (issuer,requester_id,agent_id,owner_id,executor_id,host_id,
                 job_id,fingerprint,effect_key))):
        return RemoteCheck(False,"invalid_verification_context")
    check=verify_mock_proof(proof,verifier_secret=verifier_secret,
        issuer=issuer,audience=host_id,executor=executor_id,
        intent_job=job_id,fingerprint=fingerprint,effect_key=effect_key,now=now)
    if not check.valid:
        return RemoteCheck(False,check.reason)
    if type(authority) is not IntegratedAlphaAdmission:
        return RemoteCheck(False,"authority_unavailable")
    try:
        with authority.store._tx() as db:
            encoded=json.dumps([job_id,fingerprint,requester_id,agent_id,
                                owner_id,executor_id,host_id,"demo.echo"],
                               separators=(",",":"),ensure_ascii=True)
            admitted=db.execute("""SELECT binding FROM alpha_sec01_admissions
                WHERE effect_key=?""",(effect_key,)).fetchone()
            if admitted is None or admitted[0]!=encoded:
                return RemoteCheck(False,"admission_not_found_or_mismatched")
            agent=db.execute("""SELECT a.user_id,a.disabled,u.disabled
                FROM alpha_agents a JOIN alpha_users u ON u.user_id=a.user_id
                WHERE a.agent_id=?""",(agent_id,)).fetchone()
            if agent!=(owner_id,0,0):
                return RemoteCheck(False,"agent_or_owner_revoked")
            requester=db.execute("""SELECT disabled FROM alpha_users
                WHERE user_id=?""",(requester_id,)).fetchone()
            if requester!=(0,):
                return RemoteCheck(False,"requester_revoked")
            if requester_id!=owner_id:
                grant=db.execute("""SELECT revoked FROM alpha_agent_grants
                    WHERE agent_id=? AND grantee_user_id=? AND action='demo.echo'""",
                    (agent_id,requester_id)).fetchone()
                if grant!=(0,):
                    return RemoteCheck(False,"grant_revoked")
            host=db.execute("""SELECT operator_id,active FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()
            if host!=(executor_id,1):
                return RemoteCheck(False,"host_revoked_or_mismatched")
            assigned=db.execute("""SELECT enabled FROM alpha_agent_host_assignments
                WHERE agent_id=? AND host_id=?""",(agent_id,host_id)).fetchone()
            if assigned!=(1,):
                return RemoteCheck(False,"host_assignment_revoked")
            return RemoteCheck(True,"online_precheck_only_no_effect")
    except (OSError, sqlite3.Error):
        # Intentionally fail closed, never disclose DB error details.
        return RemoteCheck(False,"authority_unavailable")
