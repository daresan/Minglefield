"""Normalize GitHub Releases API records for read-only display."""


def normalize_release(record):
    if not isinstance(record, dict):
        raise ValueError("invalid_release")
    tag = record.get("tag_name")
    url = record.get("html_url")
    if not isinstance(tag, str) or not tag.strip():
        raise ValueError("invalid_release_tag")
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        raise ValueError("invalid_release_url")
    return {"tag_name": tag, "release_notes": record.get("body") or "",
            "release_url": url, "published_at": record.get("published_at"),
            "draft": record.get("draft") is True,
            "prerelease": record.get("prerelease") is True}
