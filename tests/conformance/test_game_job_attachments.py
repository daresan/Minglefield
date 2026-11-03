"""Conformance tests for local, persistent, project-scoped staging."""
import io
import tempfile
import unittest
from pathlib import Path

from server.game_job_attachments import ProjectJobAttachments, JobAttachmentsError


class ProjectJobAttachmentsTests(unittest.TestCase):
    def test_persists_and_verifies_across_instances(self):
        with tempfile.TemporaryDirectory() as root:
            store = ProjectJobAttachments("my-game", Path(root) / "stage")
            record = store.stage("fighter.glb", io.BytesIO(b"glb-example"), 11)
            restored = ProjectJobAttachments("my-game", Path(root) / "stage")
            self.assertEqual(restored.verify(record["asset_id"]), record)
            self.assertEqual(list((Path(root) / "stage" / "assets").iterdir()).__len__(), 1)

    def test_incomplete_stream_cleans_up(self):
        with tempfile.TemporaryDirectory() as root:
            store = ProjectJobAttachments("game", Path(root) / "stage")
            with self.assertRaises(JobAttachmentsError):
                store.stage("fighter.glb", io.BytesIO(b"short"), 99)
            self.assertEqual(list(store.assets.iterdir()), [])

    def test_tampering_detected(self):
        with tempfile.TemporaryDirectory() as root:
            store = ProjectJobAttachments("game", Path(root) / "stage")
            record = store.stage("fighter.glb", io.BytesIO(b"123"), 3)
            (store.assets / record["asset_id"]).write_bytes(b"456")
            with self.assertRaisesRegex(JobAttachmentsError, "asset_integrity_failed"):
                store.verify(record["asset_id"])

    def test_invalid_names_and_project(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(JobAttachmentsError):
                ProjectJobAttachments("../other", Path(root) / "stage")
            store = ProjectJobAttachments("game", Path(root) / "stage")
            with self.assertRaises(JobAttachmentsError):
                store.stage("../escape.glb", io.BytesIO(b""), 0)
            with self.assertRaises(JobAttachmentsError):
                store.verify("../other")


if __name__ == "__main__":
    unittest.main()
