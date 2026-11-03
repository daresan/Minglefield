"""Normalize legacy workflow staging settings without touching installation staging.

Only use at an explicitly versioned API/storage migration boundary.
Existing staging_root values represent job attachments, never install payloads.
"""
from pathlib import Path

LEGACY_KEY = "staging_root"
JOB_KEY = "job_attachments_root"
INSTALL_KEY = "installation_staging_root"


def normalize_job_attachments(settings):
    """Return a canonical copy or fail closed on ambiguous legacy/new values.

    Accept legacy-only, new-only or identical dual-key payloads. Do not
    silently select a winner when values conflict. Do not create directories.
    """
    if type(settings) is not dict:
        return {"state": "blocked", "reason": "invalid_settings"}
    result = dict(settings)
    old = result.get(LEGACY_KEY)
    new = result.get(JOB_KEY)
    if old is None and new is None:
        return {"state": "blocked", "reason": "job_attachments_root_missing"}
    if old is not None and new is not None and old != new:
        return {"state": "blocked", "reason": "conflicting_job_attachments_roots"}
    chosen = new if new is not None else old
    if type(chosen) is not str or len(chosen) > 1024:
        return {"state": "blocked", "reason": "invalid_job_attachments_root"}
    if chosen and not Path(chosen).is_absolute():
        return {"state": "blocked", "reason": "invalid_job_attachments_root"}
    if INSTALL_KEY in result:
        return {"state": "blocked", "reason": "installer_storage_not_part_of_job_settings"}
    result.pop(LEGACY_KEY, None)
    result[JOB_KEY] = chosen
    return {"state": "normalized", "settings": result, "mutation_performed": False}
