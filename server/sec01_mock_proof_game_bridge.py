"""SEC-01 simulated proof-to-game boundary.

The proof is an authenticated *mock format*, NOT an authoritative admission
receipt. Game-owned fixture admission remains required independently.
No B2 calls, networks, ComfyUI execution or real side effects.
"""
from dataclasses import dataclass

from sec01_mock_admission_proof import verify_mock_proof
from sec01_mock_game_adapter import MockTransactionalGame


@dataclass(frozen=True)
class ProofGameDecision:
    state: str
    reason: str


def apply_mock_proof(game, proof, *, verifier_secret, issuer, audience,
                     executor, job_id, fingerprint, effect_key, now):
    if type(game) is not MockTransactionalGame:
        raise ValueError("invalid trusted game context")
    verified = verify_mock_proof(
        proof, verifier_secret=verifier_secret, issuer=issuer,
        audience=audience, executor=executor, intent_job=job_id,
        fingerprint=fingerprint, effect_key=effect_key, now=now)
    if not verified.valid:
        return ProofGameDecision("denied", verified.reason)
    # IMPORTANT: Merely holding a proof must NOT create an admission.
    # The game fixture must already contain the independently authorized
    # effect-key binding. This is not a production admission protocol.
    result = game.apply(effect_key=effect_key, binding=fingerprint,
                        audience=audience)
    return ProofGameDecision(result.state, result.reason)
