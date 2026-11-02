"""Artifact preflight must fail closed before any installation is attempted."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
from game_integration_evidence import verify_artifact_bytes


class ArtifactPreflightTests(unittest.TestCase):
    def test_authorized_release_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"release.bin"
            path.write_bytes(b"artifact")
            source={"provider":"github","repository":"owner/repo"}
            digest=hashlib.sha256(b"artifact").hexdigest()
            kwargs=dict(authorized_source=source,selected_source=source,
                        release_identity_verified=True,expected_digest=digest)
            self.assertEqual(verify_artifact_bytes(path,**kwargs)["state"],"integrity_verified")
            self.assertEqual(verify_artifact_bytes(path,**dict(kwargs,
                selected_source={"provider":"github","repository":"other/repo"}))["state"],"invalid")
            self.assertEqual(verify_artifact_bytes(path,**dict(kwargs,
                release_identity_verified=False))["state"],"unknown")
            self.assertEqual(verify_artifact_bytes(path,**dict(kwargs,
                expected_digest=None))["state"],"unknown")
            path.write_bytes(b"tampered")
            self.assertEqual(verify_artifact_bytes(path,**kwargs)["reason"],"digest_mismatch")

    def test_missing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            source={"provider":"github","repository":"owner/repo"}
            result=verify_artifact_bytes(Path(directory)/"missing",
                authorized_source=source,selected_source=source,
                release_identity_verified=True,expected_digest="a"*64)
            self.assertEqual(result["state"],"invalid")


if __name__=="__main__":
    unittest.main()
