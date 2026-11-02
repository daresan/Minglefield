"""Classify independent evidence. Caller must establish provenance; never pass lockfile claims as checks."""
import re

_SHA=re.compile(r"^[a-f0-9]{64}$")


def evaluate_evidence(*, declared=False, source_authorized=None,
                      release_identity_valid=None, expected_digest=None,
                      observed_digest=None, installation_matches=None):
    if any(x is False for x in (source_authorized,release_identity_valid,installation_matches)):
        return {"state":"invalid","reason":"verification_conflict"}
    for digest in (expected_digest,observed_digest):
        if digest is not None and (not isinstance(digest,str) or not _SHA.fullmatch(digest)):
            return {"state":"invalid","reason":"invalid_digest"}
    if expected_digest is not None and observed_digest is not None and expected_digest!=observed_digest:
        return {"state":"invalid","reason":"digest_mismatch"}
    if (source_authorized is True and release_identity_valid is True
            and expected_digest is not None and observed_digest is not None):
        return {"state":"installation_verified" if installation_matches is True
                else "integrity_verified","reason":"independent_checks_passed"}
    return {"state":"declared" if declared else "unknown","reason":"insufficient_evidence"}
