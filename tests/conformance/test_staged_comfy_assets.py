"""Focused regression tests for immutable asset reference resolution."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from game_asset_staging import ProjectAssetStaging, StagingError
from staged_comfy_assets import staged_record, upload_staged_asset


class StagedComfyAssetsTests(unittest.TestCase):
    def test_resolves_only_verified_host_asset(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=ProjectAssetStaging("host.alpha",root/"a")
            record=a.stage("model.glb",io.BytesIO(b"glb data"),8)
            token="minglefield-asset:"+record["asset_id"]
            path,loaded=staged_record("host.alpha",root/"a",token)
            self.assertEqual(path.read_bytes(),b"glb data")
            self.assertEqual(loaded["sha256"],record["sha256"])
            with self.assertRaises(StagingError):
                staged_record("host.beta",root/"a",token)
            with self.assertRaises(StagingError):
                staged_record("host.alpha",root/"a","minglefield-asset:../../etc")
            path.write_bytes(b"tampered")
            with self.assertRaises(StagingError):
                staged_record("host.alpha",root/"a",token)

    def test_upload_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            record=ProjectAssetStaging("host.alpha",root).stage("model.glb",io.BytesIO(b"glb"),3)
            with patch("staged_comfy_assets.http.client.HTTPConnection") as conn:
                response=conn.return_value.getresponse.return_value
                response.status=200
                response.read.return_value=b'{"name":"model.glb","type":"input","subfolder":""}'
                name=upload_staged_asset("http://127.0.0.1:8188",root/"assets"/record["asset_id"],record)
                self.assertEqual(name,"model.glb")
                self.assertEqual(conn.return_value.putrequest.call_args.args,
                                 ("POST","/upload/image"))
                conn.return_value.send.assert_any_call(b"glb")


if __name__=="__main__":
    unittest.main()
