"""Platform capability gate for future destructive staging cleanup.

This gate is intentionally conservative. A successful capability probe is NOT
authorization and must not be treated as proof against adversarial races.
Windows requires a native handle-relative implementation before enabling
deletion; path-based unlink/rmdir is explicitly insufficient.
"""
import os


def inspect_cleanup_backend_capabilities():
    """Report whether Python exposes the minimum POSIX dir-fd primitives.

    No file is created, opened, renamed or deleted by this probe.
    """
    def result(state, reason, backend):
        return {"state": state, "reason": reason, "backend": backend,
                "cleanup_allowed": False, "deletion_performed": False}
    if os.name == "nt":
        return result("unavailable", "windows_native_handle_backend_required", "windows")
    required = (os.open, os.stat, os.unlink, os.rmdir)
    if not all(fn in os.supports_dir_fd for fn in required):
        return result("unavailable", "dir_fd_operations_unavailable", "posix")
    if not isinstance(getattr(os, "O_DIRECTORY", None), int) or not isinstance(getattr(os, "O_NOFOLLOW", None), int):
        return result("unavailable", "nofollow_directory_handles_unavailable", "posix")
    if os.stat not in os.supports_follow_symlinks:
        return result("unavailable", "nofollow_stat_unavailable", "posix")
    return result("candidate", "posix_dir_fd_primitives_present", "posix")
