import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_install_preflight import installation_preflight

GOOD = dict(source_approved=True, release_binding_verified=True,
            artifact_sha256="a" * 64, observed_artifact_sha256="a" * 64,
            installed_bytes_verified=True, expected_project_revision=2,
            current_project_revision=2, conflicting_paths=[],
            owner_confirmed=True)


class InstallationPreflightTests(unittest.TestCase):
    def test_complete_evidence_still_does_not_install(self):
        result = installation_preflight(**GOOD)
        self.assertEqual(result["state"], "ready_for_transaction")
        self.assertFalse(result["installation_allowed"])
        self.assertFalse(result["mutation_performed"])

    def test_local_source_trust_is_not_install_authority(self):
        for key, value, reason in (
            ("source_approved", False, "source_not_trusted_by_host"),
            ("release_binding_verified", False, "release_binding_not_verified"),
            ("installed_bytes_verified", False, "installed_bytes_not_verified"),
            ("owner_confirmed", False, "explicit_owner_confirmation_required"),
        ):
            with self.subTest(key=key):
                result = installation_preflight(**{**GOOD, key: value})
                self.assertEqual(result["reason"], reason)
                self.assertFalse(result["installation_allowed"])

    def test_artifact_digest_must_match_independent_bytes(self):
        for replacement in ("b" * 64, "invalid", None):
            with self.subTest(digest=replacement):
                result = installation_preflight(
                    **{**GOOD, "observed_artifact_sha256": replacement})
                self.assertEqual(result["reason"], "artifact_integrity_not_verified")

    def test_revision_and_conflicts_fail_closed(self):
        self.assertEqual(installation_preflight(
            **{**GOOD, "current_project_revision": 3})["reason"],
            "project_revision_conflict")
        self.assertEqual(installation_preflight(
            **{**GOOD, "conflicting_paths": None})["reason"],
            "conflict_analysis_missing")
        result = installation_preflight(
            **{**GOOD, "conflicting_paths": ["assets/hero.glb"]})
        self.assertEqual(result["reason"], "filesystem_conflicts")
        self.assertEqual(result["conflicting_paths"], ["assets/hero.glb"])


if __name__ == "__main__":
    unittest.main()
