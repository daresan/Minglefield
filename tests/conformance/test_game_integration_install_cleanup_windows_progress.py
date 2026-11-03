"""Cross-platform tests for read-only Windows cleanup progress planning."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_cleanup_windows_progress import (
    plan_windows_cleanup_progress)


class WindowsCleanupProgressTests(unittest.TestCase):
    def setUp(self):
        self.expected = ["blob-000000", "blob-000001", "manifest.json"]

    def test_first_blob_candidate_is_deterministic_and_non_authorizing(self):
        result = plan_windows_cleanup_progress(
            self.expected, ["manifest.json", "blob-000001", "blob-000000"])
        self.assertEqual(result["state"], "candidate")
        self.assertEqual(result["next_file"], "blob-000000")
        self.assertFalse(result["cleanup_allowed"])
        self.assertFalse(result["deletion_performed"])

    def test_partial_operation_requires_persistent_progress_evidence(self):
        for observed in (["blob-000001", "manifest.json"],
                         ["manifest.json"], []):
            with self.subTest(observed=observed):
                result = plan_windows_cleanup_progress(self.expected, observed)
                self.assertEqual(result["state"], "partial")
                self.assertEqual(result["reason"],
                                 "progress_requires_durable_evidence")
                self.assertNotIn("next_file", result)

    def test_unknown_file_and_missing_manifest_fail_closed(self):
        for observed, reason in (
            (["blob-000000", "manifest.json", "foreign"], "unexpected_staging_entries"),
            (["blob-000000", "blob-000001"], "manifest_missing_before_blob_cleanup")):
            result = plan_windows_cleanup_progress(self.expected, observed)
            self.assertEqual(result["state"], "blocked")
            self.assertEqual(result["reason"], reason)

    def test_invalid_names_and_duplicates_are_rejected(self):
        for expected, observed in (
            (["manifest.json", "blob-000002"], []),
            (self.expected, ["manifest.json", "manifest.json"]),
            (self.expected, ["../foreign"])):
            with self.subTest(expected=expected, observed=observed):
                result = plan_windows_cleanup_progress(expected, observed)
                self.assertEqual(result["state"], "blocked")
