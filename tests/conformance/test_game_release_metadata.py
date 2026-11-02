"""Contract tests for the read-only GitHub Releases API adapter."""
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from game_release_metadata import fetch_releases, normalize_release, fetch_compare_files


class Response:
    def __init__(self, data, link=""):
        self.data = data
        self.headers = {"Link": link}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.data[:size]


class GameReleaseMetadataTests(unittest.TestCase):
    def test_normalization(self):
        release = {"tag_name": "v1.2.3",
                   "html_url": "https://github.com/daresan/Minglefield/releases/tag/v1.2.3",
                   "body": "Changes", "published_at": "2026-11-02T00:00:00Z"}
        result = normalize_release(release, "daresan/Minglefield")
        self.assertEqual(result["release_notes"], "Changes")
        self.assertEqual(result["tag_name"], "v1.2.3")

    def test_rejects_untrusted_release_links(self):
        for url in ("https://evil.example/releases/tag/v1", "http://github.com/a/b/releases/tag/v1",
                    "https://github.com/daresan/Other/releases/tag/v1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_release({"tag_name": "v1", "html_url": url}, "daresan/Minglefield")

    def test_fetch_uses_github_api_and_skips_drafts(self):
        records = [
            {"tag_name": "v1", "html_url": "https://github.com/a/b/releases/tag/v1"},
            {"tag_name": "v2", "html_url": "https://github.com/a/b/releases/tag/v2", "draft": True},
        ]
        def opener(request, timeout):
            self.assertEqual(request.full_url,
                             "https://api.github.com/repos/a/b/releases?per_page=30")
            self.assertEqual(timeout, 8)
            return Response(json.dumps(records).encode())
        result = fetch_releases("a/b", opener=opener)
        self.assertEqual(result["state"], "available")
        self.assertEqual([x["tag_name"] for x in result["releases"]], ["v1"])

    def test_compare_requires_complete_forward_response(self):
        payload={"status":"ahead","ahead_by":1,"total_commits":1,
                 "files":[{"filename":"src/plugin.py","status":"modified"}]}
        def fetch(data,link=""):
            return fetch_compare_files("a/b","v1","v2",opener=lambda *_args,**_kw:
                                       Response(json.dumps(data).encode(),link))
        self.assertEqual(fetch(payload)["state"],"available")
        self.assertEqual(fetch(payload)["files"][0]["path"],"src/plugin.py")
        self.assertEqual(fetch(payload,'<https://api.github.com/x>; rel="next"')["state"],"unknown")
        self.assertEqual(fetch(dict(payload,status="behind"))["state"],"unknown")
        self.assertEqual(fetch(dict(payload,total_commits=True))["state"],"unknown")
        self.assertEqual(fetch(dict(payload,files=[{"filename":"a","status":"modified"}]*100))["state"],"unknown")

    def test_invalid_repository_and_invalid_data(self):
        with self.assertRaises(ValueError):
            fetch_releases("https://example.com/a/b")
        self.assertEqual(fetch_releases("a/b", opener=lambda *a, **kw:
                         Response(b'{}'))["state"], "unavailable")

    def test_incomplete_malformed_offline_and_oversized_fail_closed(self):
        valid={"tag_name":"1.0","html_url":"https://github.com/a/b/releases/tag/1.0"}
        for payload,link in [([valid], '<url>; rel="next"'), ([valid,None], ""),
                             ([dict(valid,prerelease="false")], "")]:
            result=fetch_releases("a/b",opener=lambda *a,**k: Response(json.dumps(payload).encode(),link))
            self.assertEqual(result["state"],"unavailable")
        self.assertEqual(fetch_releases("a/b",opener=lambda *a,**k: Response(b"x"*(1024*1024+1)))["reason"],"response_too_large")
        def offline(*args,**kwargs):
            raise TimeoutError()
        self.assertEqual(fetch_releases("a/b",opener=offline)["state"],"unavailable")


if __name__ == "__main__":
    unittest.main()
