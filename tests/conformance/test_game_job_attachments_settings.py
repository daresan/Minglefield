import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_job_attachments_settings import normalize_job_attachments


class JobAttachmentsSettingsTests(unittest.TestCase):
    def test_legacy_value_is_preserved_under_new_name(self):
        old = {"staging_root": "/var/tmp/minglefield/jobs", "output_root": "/tmp/output"}
        result = normalize_job_attachments(old)
        self.assertEqual(result["state"], "normalized")
        self.assertEqual(result["settings"]["job_attachments_root"],
                         "/var/tmp/minglefield/jobs")
        self.assertNotIn("staging_root", result["settings"])
        self.assertEqual(old["staging_root"], "/var/tmp/minglefield/jobs")
        self.assertFalse(result["mutation_performed"])

    def test_conflicting_dual_keys_are_rejected(self):
        self.assertEqual(normalize_job_attachments({
            "staging_root": "/tmp/a", "job_attachments_root": "/tmp/b"
        })["reason"], "conflicting_job_attachments_roots")

    def test_identical_dual_keys_are_accepted(self):
        result = normalize_job_attachments({
            "staging_root": "/tmp/a", "job_attachments_root": "/tmp/a"})
        self.assertEqual(result["settings"], {"job_attachments_root": "/tmp/a"})

    def test_installation_storage_is_never_conflated(self):
        result = normalize_job_attachments({
            "job_attachments_root": "/tmp/jobs",
            "installation_staging_root": "/tmp/install"})
        self.assertEqual(result["reason"],
                         "installer_storage_not_part_of_job_settings")

    def test_missing_invalid_or_relative_path_is_rejected(self):
        for settings in ({}, None, {"job_attachments_root": 3},
                         {"job_attachments_root": "relative/jobs"}):
            with self.subTest(settings=settings):
                self.assertEqual(normalize_job_attachments(settings)["state"],
                                 "blocked")


if __name__ == "__main__":
    unittest.main()
