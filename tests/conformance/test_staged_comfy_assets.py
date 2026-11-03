"""Focused regression tests for immutable asset reference resolution."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.game_job_attachments import ProjectJobAttachments, JobAttachmentsError
from server.staged_comfy_assets import staged_record, upload_staged_asset


class StagedComfyAssetsTests(unittest.TestCase):
    def test_resolves_only_verified_host_asset(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=ProjectJobAttachments("host.alpha",root/"a")
            record=a.stage("model.glb",io.BytesIO(b"glb data"),8)
            token="minglefield-asset:"+record["asset_id"]
            path,loaded=staged_record("host.alpha",root/"a",token)
            self.assertEqual(path.read_bytes(),b"glb data")
            self.assertEqual(loaded["sha256"],record["sha256"])
            with self.assertRaises(JobAttachmentsError):
                staged_record("host.beta",root/"a",token)
            with self.assertRaises(JobAttachmentsError):
                staged_record("host.alpha",root/"a","minglefield-asset:../../etc")
            path.write_bytes(b"tampered")
            with self.assertRaises(JobAttachmentsError):
                staged_record("host.alpha",root/"a",token)

    def test_upload_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            record=ProjectJobAttachments("host.alpha",root).stage("model.glb",io.BytesIO(b"glb"),3)
            with patch("server.staged_comfy_assets.http.client.HTTPConnection") as conn:
                response=conn.return_value.getresponse.return_value
                response.status=200
                response.read.return_value=b'{"name":"model.glb","type":"input","subfolder":"3d"}'
                name=upload_staged_asset("http://127.0.0.1:8188",root/"assets"/record["asset_id"],record)
                self.assertEqual(name,"3d/model.glb")
                self.assertIn(b'name="subfolder"\r\n\r\n3d',
                              b"".join(call.args[0] for call in conn.return_value.send.call_args_list))
                self.assertEqual(conn.return_value.putrequest.call_args.args,
                                 ("POST","/upload/image"))
                conn.return_value.send.assert_any_call(b"glb")


if __name__=="__main__":
    unittest.main()
