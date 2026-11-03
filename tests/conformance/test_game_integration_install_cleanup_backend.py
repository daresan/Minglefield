"""No destructive cleanup without a safe platform-specific backend."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
import game_integration_install_cleanup_backend as backend


class CleanupBackendCapabilityTests(unittest.TestCase):
    def test_probe_never_authorizes_or_deletes(self):
        result = backend.inspect_cleanup_backend_capabilities()
        self.assertFalse(result["cleanup_allowed"])
        self.assertFalse(result["deletion_performed"])
        self.assertIn(result["state"], ("candidate", "unavailable"))

    def test_windows_requires_native_handle_backend(self):
        with patch.object(backend.os, "name", "nt"):
            result = backend.inspect_cleanup_backend_capabilities()
        self.assertEqual(result["state"], "unavailable")
        self.assertEqual(result["reason"], "windows_native_handle_backend_required")

    def test_missing_dir_fd_capability_fails_closed(self):
        with patch.object(backend.os, "name", "posix"), patch.object(
                backend.os, "supports_dir_fd", set()):
            result = backend.inspect_cleanup_backend_capabilities()
        self.assertEqual(result["reason"], "dir_fd_operations_unavailable")
        self.assertFalse(result["cleanup_allowed"])

    def test_missing_nofollow_fails_closed(self):
        with patch.object(backend.os, "name", "posix"), patch.object(
                backend.os, "supports_dir_fd",
                {backend.os.open, backend.os.stat, backend.os.unlink,
                 backend.os.rmdir}), patch.object(
                backend.os, "supports_follow_symlinks", {backend.os.stat}):
            with patch.object(backend.os, "O_NOFOLLOW", None, create=True):
                # None is not a usable flag; the probe must reject it.
                result = backend.inspect_cleanup_backend_capabilities()
            self.assertFalse(result["cleanup_allowed"])


if __name__ == "__main__":
    unittest.main()
