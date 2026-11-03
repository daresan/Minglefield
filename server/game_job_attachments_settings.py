"""Validate canonical job attachment settings; installation staging is separate."""
from pathlib import Path

JOB_KEY = "job_attachments_root"
INSTALL_KEY = "installation_staging_root"


def normalize_job_attachments(settings):
    """Validate new API payloads without touching files or database rows."""
    if type(settings) is not dict:
        return {"state": "blocked", "reason": "invalid_settings"}
    result = dict(settings)
    if "staging_root" in result:
        return {"state": "blocked", "reason": "legacy_staging_root_not_accepted"}
    if JOB_KEY not in result:
        return {"state": "blocked", "reason": "job_attachments_root_missing"}
    chosen = result[JOB_KEY]
    if type(chosen) is not str or len(chosen) > 1024:
        return {"state": "blocked", "reason": "invalid_job_attachments_root"}
    if chosen and not Path(chosen).is_absolute():
        return {"state": "blocked", "reason": "invalid_job_attachments_root"}
    if INSTALL_KEY in result:
        return {"state": "blocked", "reason": "installer_storage_not_part_of_job_settings"}
    return {"state": "normalized", "settings": result, "mutation_performed": False}
