"""Trusted installer record assessment: scope, provenance and tamper controls."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from game_integration_evidence import evaluate_trusted_installer_record

class InstallerRecordAssessmentTests(unittest.TestCase):
    def test_origin_scope_integrity_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"installed.bin"
            target.write_bytes(b"original")
            digest=hashlib.sha256(b"original").hexdigest()
            record={"host_id":"host.one","project_id":"game.one",
                    "integration_id":"integration.one",
                    "release_source":{"provider":"github","repository":"owner/repo"},
                    "installed_files":{"installed.bin":digest},
                    "independent_checks":{"source_authorized":True,
                                          "release_identity_valid":True,
                                          "expected_digest":digest,"observed_digest":digest}}
            kwargs=dict(expected_host_id="host.one",expected_project_id="game.one",
                        expected_integration_id="integration.one",
                        authorized_source=record["release_source"],project_root=directory)
            checks=dict(source_authorized=True,release_identity_valid=True,
                        expected_digest=digest,observed_digest=digest)
            self.assertEqual(evaluate_trusted_installer_record(record,**kwargs)["state"],"unknown")
            self.assertEqual(evaluate_trusted_installer_record(
                record,trusted_origin=True,**kwargs)["state"],"unknown")
            self.assertEqual(evaluate_trusted_installer_record(
                record,trusted_origin=True,independent_checks=checks,**kwargs)["state"],
                "installation_verified")
            self.assertEqual(evaluate_trusted_installer_record(
                dict(record,host_id="host.two"),trusted_origin=True,
                independent_checks=checks,**kwargs)["state"],"invalid")
            self.assertEqual(evaluate_trusted_installer_record(
                record,trusted_origin=True,independent_checks=dict(checks,source_authorized=False),
                **kwargs)["state"],"invalid")
            target.write_bytes(b"tampered")
            self.assertEqual(evaluate_trusted_installer_record(
                record,trusted_origin=True,independent_checks=checks,**kwargs)["reason"],
                "installed_file_changed")

if __name__=="__main__":
    unittest.main()
