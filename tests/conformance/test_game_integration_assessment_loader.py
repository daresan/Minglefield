"""Focused tests for pinned GitHub assessment byte retrieval."""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_integration_assessment_loader import load_pinned_assessment_bytes

REPO = "daresan/minglefield-integration-test"
COMMIT = "6df11272a9ca14dcfb8dc3bbe26b29c189d12253"


class Response:
    def __init__(self, url, payload):
        self.url, self.stream = url, io.BytesIO(payload)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.stream.close()
    def geturl(self):
        return self.url
    def read(self, size):
        return self.stream.read(size)


class PinnedAssessmentLoaderTests(unittest.TestCase):
    def test_exact_commit_and_path(self):
        urls = []
        def opener(request, timeout):
            self.assertEqual(timeout, 8)
            urls.append(request.full_url)
            return Response(request.full_url, b'{"ok":true}')
        self.assertEqual(load_pinned_assessment_bytes(
            REPO, COMMIT, "compatibility", opener=opener), b'{"ok":true}')
        self.assertEqual(urls, ["https://raw.githubusercontent.com/" + REPO + "/"
                         + COMMIT + "/fixtures/assessments/v1.0.0-to-v1.1.0.compatibility.json"])

    def test_invalid_identity_never_fetches(self):
        def forbidden(*args, **kwargs):
            self.fail("unexpected network call")
        for repo, commit, kind in (
            ("evil/repo/extra", COMMIT, "compatibility"),
            ("../repo", COMMIT, "compatibility"),
            (REPO, "main", "compatibility"),
            (REPO, COMMIT, "../other.json")):
            with self.subTest(repo=repo, commit=commit, kind=kind):
                with self.assertRaises(ValueError):
                    load_pinned_assessment_bytes(repo, commit, kind, opener=forbidden)

    def test_redirect_and_oversize_rejected(self):
        for opener in (
            lambda request, timeout: Response("https://evil.example/data", b"{}"),
            lambda request, timeout: Response(request.full_url, b"x" * (1024 * 1024 + 1)),
            lambda request, timeout: Response(request.full_url, b"")):
            with self.assertRaises(ValueError):
                load_pinned_assessment_bytes(REPO, COMMIT, "migration", opener=opener)

    def test_network_error_is_closed(self):
        def offline(request, timeout):
            raise OSError("offline")
        with self.assertRaises(ValueError):
            load_pinned_assessment_bytes(REPO, COMMIT, "migration", opener=offline)


if __name__ == "__main__":
    unittest.main()
