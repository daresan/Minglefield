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


def evaluate_trusted_installer_record(record, *, trusted_origin=False, independent_checks=None,
                                      expected_host_id, expected_project_id,
                                      expected_integration_id, authorized_source,
                                      project_root):
    """Validate scope and recheck files without trusting claims inside a journal row.

    trusted_origin must be established by the calling runtime's protected
    installer transaction, not inferred from record fields or lockfiles.
    Independent release identity and artifact digest checks must be passed by\n    the trusted caller, never copied from the journal record.
    """
    if trusted_origin is not True:
        return {"state":"unknown","reason":"installer_origin_not_authenticated"}
    if not isinstance(record,dict):
        return {"state":"invalid","reason":"invalid_installer_record"}
    scope=(("host_id",expected_host_id),("project_id",expected_project_id),
           ("integration_id",expected_integration_id),
           ("release_source",authorized_source))
    if any(record.get(key)!=expected for key,expected in scope):
        return {"state":"invalid","reason":"installer_scope_or_source_mismatch"}
    checks=independent_checks
    if not isinstance(checks,dict):
        return {"state":"unknown","reason":"missing_independent_checks"}
    file_result=recheck_installed_files(project_root,record.get("installed_files"))
    if file_result["state"]!="installation_files_match":
        return file_result
    result=evaluate_evidence(
        source_authorized=checks.get("source_authorized"),
        release_identity_valid=checks.get("release_identity_valid"),
        expected_digest=checks.get("expected_digest"),
        observed_digest=checks.get("observed_digest"),
        installation_matches=True)
    return result


def verify_artifact_bytes(artifact_path, *, authorized_source, selected_source,
                          release_identity_verified=False, expected_digest=None):
    """Read-only artifact preflight; independent digest supplied by trusted caller.

    Does not download, extract, install, or authenticate the caller. The caller
    must establish release identity and obtain the digest independently.
    """
    import hashlib
    from pathlib import Path

    if authorized_source != selected_source or not isinstance(authorized_source,dict):
        return {"state":"invalid","reason":"unauthorized_release_source"}
    if release_identity_verified is not True:
        return {"state":"unknown","reason":"release_identity_not_verified"}
    if not isinstance(expected_digest,str) or not _SHA.fullmatch(expected_digest):
        return {"state":"unknown","reason":"missing_independent_artifact_digest"}
    artifact=Path(artifact_path)
    if artifact.is_symlink() or not artifact.is_file():
        return {"state":"invalid","reason":"missing_or_unsafe_artifact"}
    try:
        digest=hashlib.sha256()
        with artifact.open("rb") as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b""):
                digest.update(chunk)
    except OSError:
        return {"state":"invalid","reason":"artifact_unreadable"}
    result=evaluate_evidence(
        source_authorized=True,release_identity_valid=True,
        expected_digest=expected_digest,observed_digest=digest.hexdigest())
    return {**result,"observed_sha256":digest.hexdigest()}
