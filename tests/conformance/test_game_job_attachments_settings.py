import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_job_attachments_settings import normalize_job_attachments


class JobAttachmentsSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a = str(Path(self.tmp.name) / "a")
        self.b = str(Path(self.tmp.name) / "b")

    def test_canonical_value_is_preserved(self):
        original = {"job_attachments_root": self.a, "output_root": self.b}
        result = normalize_job_attachments(original)
        self.assertEqual(result["state"], "normalized")
        self.assertEqual(result["settings"], original)
        self.assertFalse(result["mutation_performed"])

    def test_legacy_and_dual_key_api_payloads_are_rejected(self):
        for settings in (
                {"staging_root": self.a},
                {"staging_root": self.a, "job_attachments_root": self.a},
                {"staging_root": self.b, "job_attachments_root": self.a}):
            with self.subTest(settings=settings):
                result = normalize_job_attachments(settings)
                self.assertEqual(result["state"], "blocked")
                self.assertEqual(result["reason"], "legacy_staging_root_not_accepted")

    def test_installation_storage_is_never_conflated(self):
        result = normalize_job_attachments({
            "job_attachments_root": self.a,
            "installation_staging_root": self.b})
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
