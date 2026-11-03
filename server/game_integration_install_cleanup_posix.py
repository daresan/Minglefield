"""POSIX handle-relative cleanup primitive for isolated installer staging.

Internal primitive only: caller MUST bind owner, operation, plan and terminal
journal state in trusted storage. Never expose this function to HTTP directly.
Windows is deliberately unsupported until a native handle backend exists.
"""
import os
import stat
from pathlib import Path

from game_integration_install_cleanup_backend import inspect_cleanup_backend_capabilities
from game_integration_install_cleanup import inspect_staging_cleanup
from game_integration_install_path_safety import has_redirecting_component


def cleanup_staged_operation_posix(root, operation_id, entries, *,
                                   journal_operation_id=None,
                                   journal_plan_sha256=None,
                                   journal_state=None,
                                   owner_authorized=False):
    def result(state, reason, deleted=False):
        return {"state": state, "reason": reason, "deletion_performed": deleted,
                "installation_allowed": False}
    if inspect_cleanup_backend_capabilities()["state"] != "candidate":
        return result("blocked", "secure_cleanup_backend_unavailable")
    # This snapshot is only an eligibility check, never an authorization token.
    check = inspect_staging_cleanup(
        root, operation_id, entries, journal_operation_id=journal_operation_id,
        journal_plan_sha256=journal_plan_sha256, journal_state=journal_state,
        owner_authorized=owner_authorized)
    if check["state"] != "eligible_snapshot":
        return result("blocked", check["reason"])
    if has_redirecting_component(root):
        return result("blocked", "unsafe_installation_staging_root")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = op_fd = None
    removed = False
    try:
        root_fd = os.open(root, flags)
        root_stat = os.fstat(root_fd)
        if not stat.S_ISDIR(root_stat.st_mode):
            return result("blocked", "unsafe_installation_staging_root")
        # Reject shared-writable roots and verify the opened root identity.
        # Same-UID writers still require exclusive runtime coordination.
        if root_stat.st_mode & 0o022:
            return result("blocked", "insecure_staging_root_permissions")
        if root_stat.st_uid != os.geteuid():
            return result("blocked", "staging_root_owner_mismatch")
        root_path_stat = Path(root).stat(follow_symlinks=False)
        if (root_path_stat.st_dev, root_path_stat.st_ino) != (
                root_stat.st_dev, root_stat.st_ino):
            return result("blocked", "staging_root_identity_changed")
        before = os.stat(operation_id, dir_fd=root_fd, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            return result("blocked", "unsafe_operation_path")
        op_fd = os.open(operation_id, flags, dir_fd=root_fd)
        op_stat = os.fstat(op_fd)
        if op_stat.st_mode & 0o022:
            return result("blocked", "insecure_operation_permissions")
        if op_stat.st_uid != os.geteuid():
            return result("blocked", "operation_owner_mismatch")
        if (op_stat.st_dev, op_stat.st_ino) != tuple(check["operation_identity"]):
            return result("blocked", "operation_identity_changed")
        if (before.st_dev, before.st_ino) != (op_stat.st_dev, op_stat.st_ino):
            return result("blocked", "operation_identity_changed")
        expected = set(check["observed_files"])
        # Do not follow symlinks, and reject any unknown or newly created entry.
        current = set(os.listdir(op_fd))
        if current != expected:
            return result("blocked", "operation_contents_changed")
        for name in sorted(expected):
            info = os.stat(name, dir_fd=op_fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                return result("blocked", "unsafe_staging_entry")
            if info.st_uid != os.geteuid():
                return result("blocked", "staging_entry_owner_mismatch")
        # The caller must ensure no concurrent untrusted filesystem writer
        # can rename/replace this operation. dir_fd protects child traversal,
        # but POSIX cannot atomically compare identity and rmdir by name.
        for name in sorted(expected):
            current = os.stat(name, dir_fd=op_fd, follow_symlinks=False)
            if (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
                    or current.st_uid != os.geteuid()):
                return result("partial", "staging_entry_changed", removed)
            os.unlink(name, dir_fd=op_fd)
            removed = True
            # A replaced operation path must never cause the next iteration
            # to act on a different directory. The open handle stays bound
            # to the original inode; check its parent binding after each
            # mutation to stop as early as possible.
            binding = os.stat(operation_id, dir_fd=root_fd,
                              follow_symlinks=False)
            if (binding.st_dev, binding.st_ino) != (
                    op_stat.st_dev, op_stat.st_ino):
                return result("partial", "operation_identity_changed", removed)
        # Recheck both ends of the root -> operation binding. These checks
        # narrow the window but cannot make name-based rmdir atomic.
        root_binding = Path(root).stat(follow_symlinks=False)
        if (root_binding.st_dev, root_binding.st_ino) != (
                root_stat.st_dev, root_stat.st_ino):
            return result("partial", "staging_root_identity_changed", removed)
        again = os.stat(operation_id, dir_fd=root_fd, follow_symlinks=False)
        if (again.st_dev, again.st_ino) != (op_stat.st_dev, op_stat.st_ino):
            return result("partial", "operation_identity_changed", removed)
        os.rmdir(operation_id, dir_fd=root_fd)
        return result("removed", "staging_operation_removed", True)
    except OSError:
        return result("partial" if removed else "blocked", "cleanup_filesystem_error", removed)
    finally:
        if op_fd is not None:
            os.close(op_fd)
        if root_fd is not None:
            os.close(root_fd)
