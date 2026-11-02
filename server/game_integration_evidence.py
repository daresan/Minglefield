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


def recheck_installed_files(project_root, installed_files):
    """Read-only recheck of trusted installer file hashes; never read hashes from a lock.

    This checks file contents only. It does not establish artifact provenance,
    authorized source or release identity; those are separate evidence gates.
    """
    import hashlib
    from pathlib import Path

    if not isinstance(installed_files, dict) or not installed_files:
        return {"state":"unknown","reason":"missing_trusted_file_evidence"}
    root=Path(project_root)
    if not root.is_dir() or root.is_symlink():
        return {"state":"invalid","reason":"unsafe_installation_root"}
    root=root.resolve()
    for name, digest in installed_files.items():
        if not isinstance(name,str) or not name or not isinstance(digest,str) or not _SHA.fullmatch(digest):
            return {"state":"invalid","reason":"invalid_file_evidence"}
        relative=Path(name)
        if relative.is_absolute() or ".." in relative.parts or relative==Path("."):
            return {"state":"invalid","reason":"unsafe_installed_path"}
        target=root/relative
        if not target.resolve().is_relative_to(root) or target.is_symlink():
            return {"state":"invalid","reason":"unsafe_installed_path"}
        if not target.is_file():
            return {"state":"invalid","reason":"missing_installed_file"}
        try:
            h=hashlib.sha256()
            with target.open("rb") as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b""):
                    h.update(chunk)
        except OSError:
            return {"state":"invalid","reason":"installed_file_unreadable"}
        if h.hexdigest()!=digest:
            return {"state":"invalid","reason":"installed_file_changed"}
    return {"state":"installation_files_match","reason":"trusted_file_hashes_match"}
