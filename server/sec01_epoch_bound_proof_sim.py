"""SEC-01 local epoch-bound proof envelope (simulation, no effects).

SQLite triggers track authorization mutations atomically even when legacy
AlphaAuthStore methods write directly. An envelope binds the issuing session
and authority generations to a mock proof. This does NOT authorize execution.
"""
import hashlib
import hmac
import json
import sqlite3

from private_alpha_auth import digest
from sec01_remote_precommit_sim import LocalProofIssuer, online_precommit_check

TRACKED = {
    "alpha_agent_grants": ("agent_id","grantee_user_id","action"),
    "alpha_agents": ("agent_id",),
    "alpha_users": ("user_id",),
    "alpha_sessions": ("token_hash",),
    "alpha_executor_hosts": ("host_id",),
    "alpha_agent_host_assignments": ("agent_id","host_id"),
}

def _key(table, values):
    return json.dumps([table,*values],separators=(",",":"))

class EpochBoundProofs:
    def __init__(self, issuer):
        if type(issuer) is not LocalProofIssuer:
            raise TypeError("requires local proof issuer")
        self.issuer=issuer
        self.authority=issuer.authority
        with self.authority.store._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS alpha_sec01_epochs(
                identity TEXT PRIMARY KEY, generation INTEGER NOT NULL
                CHECK(generation>=1))""")
            for table,columns in TRACKED.items():
                # AFTER triggers execute in the same SQLite transaction as
                # revoke, regrant, disable and host placement changes.
                for op,alias in (("INSERT","NEW"),("UPDATE","NEW"),
                                 ("DELETE","OLD")):
                    trigger="sec01_epoch_"+table+"_"+op.lower()
                    vals=",".join(alias+"."+col for col in columns)
                    keyexpr="'"+table+":'||json_array("+vals+")"
                    db.execute(f"""CREATE TRIGGER IF NOT EXISTS {trigger}
                        AFTER {op} ON {table} BEGIN
                        INSERT INTO alpha_sec01_epochs(identity,generation)
                        VALUES({keyexpr},1)
                        ON CONFLICT(identity) DO UPDATE SET
                        generation=generation+1;
                        END""")

    def _snapshot(self, db, *, authorization, agent_id, owner_id,
                  requester_id, host_id):
        if (type(authorization) is not str or not authorization.startswith("Bearer ")
                or not 1<=len(authorization[7:])<=256):
            return None
        token_hash=digest(authorization[7:])
        keys=[
            ("alpha_sessions",(token_hash,)),
            ("alpha_users",(requester_id,)),
            ("alpha_users",(owner_id,)),
            ("alpha_agents",(agent_id,)),
            ("alpha_agent_grants",(agent_id,requester_id,"demo.echo")),
            ("alpha_executor_hosts",(host_id,)),
            ("alpha_agent_host_assignments",(agent_id,host_id)),
        ]
        result={}
        for table,parts in keys:
            k=table+":"+json.dumps(list(parts),separators=(",",":"))
            row=db.execute("SELECT generation FROM alpha_sec01_epochs WHERE identity=?",
                           (k,)).fetchone()
            result[k]=row[0] if row else 0
        return result

    def issue(self, authorization, *, effect_key, job_id, fingerprint,
              agent_id, owner_id, executor_id, host_id, now, ttl=30):
        requester=self.authority.store.principal(authorization)
        if requester is None:
            return None
        kw=dict(authorization=authorization,agent_id=agent_id,
                owner_id=owner_id,requester_id=requester.user_id,host_id=host_id)
        with self.authority.store._tx() as db:
            before=self._snapshot(db,**kw)
        proof=self.issuer.issue(authorization,effect_key=effect_key,job_id=job_id,
            fingerprint=fingerprint,agent_id=agent_id,owner_id=owner_id,
            executor_id=executor_id,host_id=host_id,now=now,ttl=ttl)
        if proof is None:
            return None
        with self.authority.store._tx() as db:
            after=self._snapshot(db,**kw)
            if before!=after or self.authority.store._active_user(db,authorization)!=requester.user_id:
                return None
        payload=dict(proof=proof,requester_id=requester.user_id,
                     session_hash=digest(authorization[7:]),epochs=before)
        mac=hmac.new(self.issuer.secret,b"sec01-epoch-envelope-v1\x00"+
                     json.dumps(payload,sort_keys=True,separators=(",",":")).encode(),
                     hashlib.sha256).hexdigest()
        return dict(payload=payload,mac=mac)

    def check(self, envelope, *, requester_id, agent_id, owner_id,
              executor_id, host_id, job_id, fingerprint, effect_key, now):
        if (type(envelope) is not dict or set(envelope)!={"payload","mac"}
                or type(envelope["payload"]) is not dict
                or type(envelope["mac"]) is not str
                or len(envelope["mac"])!=64):
            return False,"invalid_envelope"
        payload=envelope["payload"]
        if set(payload)!={"proof","requester_id","session_hash","epochs"}:
            return False,"invalid_envelope"
        if payload["requester_id"]!=requester_id or type(payload["epochs"]) is not dict:
            return False,"requester_mismatch"
        try:
            expected=hmac.new(self.issuer.secret,b"sec01-epoch-envelope-v1\x00"+
                json.dumps(payload,sort_keys=True,separators=(",",":")).encode(),
                hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,envelope["mac"]):
                return False,"invalid_envelope_mac"
            with self.authority.store._tx() as db:
                session=db.execute("""SELECT s.user_id,s.revoked,s.expires_at,u.disabled
                    FROM alpha_sessions s JOIN alpha_users u ON u.user_id=s.user_id
                    WHERE s.token_hash=?""",(payload["session_hash"],)).fetchone()
                if (session is None or session[0]!=requester_id or session[1]!=0
                        or session[2]<=self.authority.store.clock() or session[3]!=0):
                    return False,"issuing_session_revoked"
                # Snapshot and authority state are checked under one lock.
                keys=payload["epochs"]
                for k,generation in keys.items():
                    if type(k) is not str or type(generation) is not int:
                        return False,"invalid_epochs"
                    row=db.execute("SELECT generation FROM alpha_sec01_epochs WHERE identity=?",
                                   (k,)).fetchone()
                    if (row[0] if row else 0)!=generation:
                        return False,"authority_epoch_changed"
            # This is a precheck, not a commit. The gap remains unsafe for effects.
            checked=online_precommit_check(self.authority,payload["proof"],
                verifier_secret=self.issuer.secret,issuer=self.issuer.issuer,
                requester_id=requester_id,agent_id=agent_id,owner_id=owner_id,
                executor_id=executor_id,host_id=host_id,job_id=job_id,
                fingerprint=fingerprint,effect_key=effect_key,now=now)
            return checked.allowed,checked.reason
        except (TypeError,ValueError,KeyError,sqlite3.Error,OverflowError):
            return False,"invalid_or_unavailable_authority"
