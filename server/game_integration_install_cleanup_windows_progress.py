"""Pure, fail-closed state planning for experimental Windows staging cleanup.

No filesystem calls, deletion, journal writes, or HTTP capabilities. Progress
is recomputed from a fresh, authorized operation in the caller. The input is
an exact listing of safe regular-file names, not a reusable authorization.
"""
import re

_BLOB = re.compile(r"blob-[0-9]{6}\Z")
_MANIFEST = "manifest.json"


def plan_windows_cleanup_progress(expected_files, observed_files):
    """Classify remaining files and choose at most one safe next deletion.

    Expected blob names must be contiguous from blob-000000; manifest must
    remain until after all blobs. Unknown names always fail closed.
    """
    def response(state, reason, **extra):
        return {"state": state, "reason": reason,
                "cleanup_allowed": False, "deletion_performed": False, **extra}

    if (type(expected_files) not in (list, tuple) or not expected_files
            or len(expected_files) > 1001
            or any(type(name) is not str for name in expected_files)):
        return response("blocked", "invalid_expected_files")
    expected = set(expected_files)
    blobs = [f"blob-{i:06d}" for i in range(len(expected_files) - 1)]
    if (len(expected) != len(expected_files)
            or expected != set(blobs) | {_MANIFEST}):
        return response("blocked", "invalid_expected_files")
    if (type(observed_files) not in (list, tuple)
            or any(type(name) is not str for name in observed_files)
            or len(set(observed_files)) != len(observed_files)):
        return response("blocked", "invalid_observed_files")
    observed = set(observed_files)
    if observed - expected:
        return response("blocked", "unexpected_staging_entries")
    remaining_blobs = [name for name in blobs if name in observed]
    if remaining_blobs and _MANIFEST not in observed:
        return response("blocked", "manifest_missing_before_blob_cleanup")
    if len(remaining_blobs) != len(blobs):
        # Do not mistake an incomplete staging operation for an authorized
        # cleanup continuation. The caller must persist or independently
        # establish previous removals before using this plan for deletion.
        return response("partial", "progress_requires_durable_evidence",
                        remaining_files=sorted(observed))
    if remaining_blobs:
        return response("candidate", "first_blob_candidate",
                        next_file=remaining_blobs[0],
                        remaining_files=sorted(observed))
    if observed == {_MANIFEST}:
        return response("partial", "progress_requires_durable_evidence",
                        remaining_files=[_MANIFEST])
    return response("partial", "progress_requires_durable_evidence",
                    remaining_files=[])
