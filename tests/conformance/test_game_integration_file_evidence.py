"""Negative controls for read-only installed-file evidence rechecking."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from game_integration_evidence import recheck_installed_files


class InstalledFileEvidenceTests(unittest.TestCase):
    def test_missing_evidence_is_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(recheck_installed_files(directory,{})["state"],"unknown")

    def test_matching_and_tampered_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"game.dat"
            path.write_bytes(b"original")
            digest=hashlib.sha256(b"original").hexdigest()
            self.assertEqual(recheck_installed_files(directory,{"game.dat":digest})["state"],
                             "installation_files_match")
            path.write_bytes(b"tampered")
            self.assertEqual(recheck_installed_files(directory,{"game.dat":digest})["reason"],
                             "installed_file_changed")

    def test_path_traversal_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            digest="0"*64
            self.assertEqual(recheck_installed_files(directory,{"../outside":digest})["reason"],
                             "unsafe_installed_path")

    def test_missing_file_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(recheck_installed_files(directory,{"absent":"0"*64})["reason"],
                             "missing_installed_file")


if __name__=="__main__":
    unittest.main()
