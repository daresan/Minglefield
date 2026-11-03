"""Bounded, read-only retrieval of assessment fixture bytes from pinned Git commits.

A remote response is never authority: the resolver verifies an independently
approved SHA-256 and release identity after this loader returns bytes.
"""
import re
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

_REPOSITORY = re.compile(r"^(?![.]+/)(?![^/]+/[.]+$)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_PATHS = {
    "compatibility": "fixtures/assessments/v1.0.0-to-v1.1.0.compatibility.json",
    "migration": "fixtures/assessments/v1.0.0-to-v1.1.0.migration.json",
}
_MAX_BYTES = 1024 * 1024


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def load_pinned_assessment_bytes(repository, commit, kind, *, opener=None):
    """Retrieve exact pinned fixture path; reject redirects and oversized payloads.

    This first loader supports the v1.0.0 -> v1.1.0 test fixture paths only.
    Generalized artifact locations require a separately reviewed manifest.
    """
    if (not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository)
            or not isinstance(commit, str) or not _COMMIT.fullmatch(commit)
            or kind not in _PATHS):
        raise ValueError("invalid_pinned_assessment_request")
    url = ("https://raw.githubusercontent.com/" + repository + "/"
           + commit + "/" + _PATHS[kind])
    request = Request(url, headers={"User-Agent": "Minglefield-Alpha",
                                    "Accept": "application/octet-stream"})
    if opener is None:
        opener = build_opener(_NoRedirect()).open
    try:
        with opener(request, timeout=8) as response:
            if response.geturl() != url:
                raise ValueError("unexpected_assessment_response_url")
            data = response.read(_MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValueError("assessment_fetch_unavailable") from exc
    if not isinstance(data, bytes) or not data or len(data) > _MAX_BYTES:
        raise ValueError("invalid_assessment_response_bytes")
    return data
