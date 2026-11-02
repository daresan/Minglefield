"""SEC-01: isolated HMAC admission-proof format simulation, NOT issuance authority.

HMAC requires a single shared secret and is insufficient for untrusted,
independently operated third-party adapters. No wire endpoint or real effect.
"""
import hashlib
import hmac
import json
import math
from dataclasses import dataclass

FIELDS = frozenset(("version","issuer","audience","job_id","request_fingerprint",
                    "effect_key","executor","issued_at","expires_at","nonce"))
def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")

@dataclass(frozen=True)
class ProofCheck:
    valid: bool
    reason: str

def _valid(payload):
    return (type(payload) is dict and set(payload)==FIELDS
            and type(payload["version"]) is int and payload["version"]==1
            and all(type(payload[k]) is str and 1<=len(payload[k])<=128
                    for k in FIELDS-{"version","issued_at","expires_at"})
            and type(payload["issued_at"]) is int
            and type(payload["expires_at"]) is int
            and 0<=payload["issued_at"]<payload["expires_at"])

def issue_mock_proof(payload, *, issuer_secret):
    """TEST-ONLY: payload is assumed already admitted by an external fixture."""
    if type(issuer_secret) is not bytes or len(issuer_secret)<32 or not _valid(payload):
        raise ValueError("invalid mock proof context")
    mac=hmac.new(issuer_secret,b"sec01-mock-proof-v1\x00"+canonical(payload),
                 hashlib.sha256).hexdigest()
    return {"payload":dict(payload),"mac":mac}

def verify_mock_proof(proof, *, verifier_secret, issuer, audience, executor,
                      intent_job, fingerprint, effect_key, now):
    if (type(verifier_secret) is not bytes or len(verifier_secret)<32
            or type(now) not in (int,float) or not math.isfinite(now)):
        raise ValueError("invalid trusted verification context")
    if (type(proof) is not dict or set(proof)!={"payload","mac"}
            or not _valid(proof["payload"])
            or type(proof["mac"]) is not str or len(proof["mac"])!=64
            or any(ch not in "0123456789abcdef" for ch in proof["mac"])):
        return ProofCheck(False,"invalid_shape")
    payload=proof["payload"]
    if (payload["issuer"],payload["audience"],payload["executor"],
        payload["job_id"],payload["request_fingerprint"],payload["effect_key"])!=(
            issuer,audience,executor,intent_job,fingerprint,effect_key):
        return ProofCheck(False,"binding_mismatch")
    if not payload["issued_at"]<=now<payload["expires_at"]:
        return ProofCheck(False,"expired")
    expected=hmac.new(verifier_secret,b"sec01-mock-proof-v1\x00"+canonical(payload),
                      hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,proof["mac"]):
        return ProofCheck(False,"invalid_mac")
    return ProofCheck(True,"mock_proof_valid_not_effect_authorization")
