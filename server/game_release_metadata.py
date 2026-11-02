"""Read-only GitHub Releases adapter; no custom release catalog or Git mutation."""
import json
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_MAX_BYTES = 1024 * 1024


def normalize_release(record, repository):
    """Validate GitHub API release metadata before exposing it to the UI."""
    if not isinstance(record, dict) or not isinstance(repository, str) or not _REPO.fullmatch(repository):
        raise ValueError("invalid_release")
    tag, url = record.get("tag_name"), record.get("html_url")
    if not isinstance(tag, str) or not tag.strip() or len(tag) > 128:
        raise ValueError("invalid_release_tag")
    if not isinstance(url, str):
        raise ValueError("invalid_release_url")
    parsed = urlsplit(url)
    prefix = "/" + repository + "/releases/tag/"
    if (parsed.scheme != "https" or parsed.netloc != "github.com"
            or not parsed.path.startswith(prefix) or not parsed.path[len(prefix):]
            or parsed.query or parsed.fragment):
        raise ValueError("invalid_release_url")
    notes, published = record.get("body"), record.get("published_at")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("invalid_release_notes")
    if published is not None and not isinstance(published, str):
        raise ValueError("invalid_release_date")
    return {"tag_name": tag, "release_notes": notes or "", "release_url": url,
            "published_at": published, "draft": record.get("draft") is True,
            "prerelease": record.get("prerelease") is True}


def fetch_releases(repository, *, opener=urlopen):
    """Read public GitHub Releases API; callers decide how to handle unavailability."""
    if not isinstance(repository, str) or not _REPO.fullmatch(repository):
        raise ValueError("invalid_repository")
    url = "https://api.github.com/repos/" + repository + "/releases?per_page=30"
    request = Request(url, headers={"Accept": "application/vnd.github+json",
                                    "User-Agent": "Minglefield-Alpha"})
    try:
        with opener(request, timeout=8) as response:
            raw = response.read(_MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {"state": "unavailable", "reason": type(exc).__name__, "releases": []}
    if len(raw) > _MAX_BYTES:
        return {"state": "unavailable", "reason": "response_too_large", "releases": []}
    try:
        records = json.loads(raw)
        if not isinstance(records, list):
            raise ValueError("invalid_release_list")
        releases = [normalize_release(record, repository) for record in records
                    if isinstance(record, dict) and record.get("draft") is not True]
    except (ValueError, UnicodeError, TypeError):
        return {"state": "unavailable", "reason": "invalid_release_data", "releases": []}
    return {"state": "available", "releases": releases}
