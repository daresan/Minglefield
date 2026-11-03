"""Read-only update discovery for registry-authorized integration sources.

Version comparison uses packaging.version (PEP 440), stable public versions only.
This module never claims artifact integrity or installation.
"""
from packaging.version import Version, InvalidVersion
from urllib.parse import quote
from game_release_metadata import fetch_releases, fetch_compare_files
from game_integration_assessment import assess_compatibility, assess_migration


def _version(value):
    if not isinstance(value,str) or not value.strip():
        return None
    try:
        version = Version(value.strip())
        return None if version.local is not None else version
    except InvalidVersion:
        return None


def _discover_integration_update(entry, catalog, *, fetcher=fetch_releases,
                                compare_fetcher=fetch_compare_files):
    """Compare a declared version against stable releases from a matching curated source."""
    if not isinstance(entry,dict) or not isinstance(catalog,dict):
        return {"state":"unknown","reason":"invalid_input"}
    if catalog.get("state")!="available":
        return {"state":"unknown","reason":"registry_unavailable"}
    items=catalog.get("integrations")
    if not isinstance(items,list) or any(not isinstance(x,dict) for x in items):
        return {"state":"unknown","reason":"invalid_registry_catalog"}
    match=next((x for x in items
                if x.get("integration_id")==entry.get("integration_id")),None)
    if match is None:
        return {"state":"unknown","reason":"not_in_curated_registry"}
    source=match.get("release_source")
    if (entry.get("source_state")!="registry_match"
            or source!=entry.get("release_source")
            or match.get("publisher") is None):
        return {"state":"unknown","reason":"untrusted_source"}
    installed=_version(entry.get("declared_version"))
    if installed is None or installed.is_prerelease or installed.is_devrelease:
        return {"state":"unknown","reason":"invalid_installed_version"}
    if not isinstance(source,dict) or source.get("provider")!="github":
        return {"state":"unknown","reason":"unsupported_release_provider"}
    try:
        result=fetcher(source["repository"])
    except (ValueError,KeyError,TypeError,OSError):
        return {"state":"unknown","reason":"release_source_unavailable"}
    if not isinstance(result,dict) or result.get("state")!="available":
        return {"state":"unknown","reason":"release_source_unavailable"}
    releases=result.get("releases")
    if not isinstance(releases,list) or any(not isinstance(r,dict) for r in releases):
        return {"state":"unknown","reason":"invalid_release_data"}
    if result.get("complete") is False:
        return {"state":"unknown","reason":"incomplete_release_catalog"}
    versions=[]
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue
        version=_version(release.get("tag_name"))
        if version is not None and not version.is_prerelease and not version.is_devrelease:
            versions.append((version,release))
    if not versions:
        return {"state":"unknown","reason":"no_comparable_releases"}
    latest,release=max(versions,key=lambda item:item[0])
    comparison_url=None
    if latest>installed:
        # A link is only a navigation aid, not evidence of actual installed bytes.
        repository=source.get("repository")
        old_tag=entry.get("declared_version")
        new_tag=release.get("tag_name")
        if (isinstance(repository,str) and isinstance(old_tag,str)
                and isinstance(new_tag,str) and old_tag and new_tag):
            comparison_url=("https://github.com/"+repository+"/compare/"
                            +quote(old_tag,safe="")+"..."+quote(new_tag,safe=""))
    changed={"state":"unknown","files":[],"comparison_url":comparison_url}
    if comparison_url is not None:
        try:
            comparison=compare_fetcher(source["repository"],entry["declared_version"],release["tag_name"])
            if (isinstance(comparison,dict) and comparison.get("state")=="available"
                    and isinstance(comparison.get("files"),list)):
                changed={"state":"available","files":comparison["files"],
                         "comparison_url":comparison_url}
        except (ValueError,TypeError,KeyError,OSError):
            pass
    return {"state":"unknown","reason":"installation_not_verified",
            "version_comparison":"newer_release_than_declared" if latest>installed else "no_newer_release_than_declared",
            "declared_version":entry["declared_version"],
            "comparison_state":"update_available" if latest>installed else "up_to_date",
            "available_version":release["tag_name"],
            "release_notes":release.get("release_notes",""),
            "release_url":release.get("release_url"),
            "published_at":release.get("published_at"),
            "verification_state":"unknown",
            "preview":{"state":"incomplete","release_notes":release.get("release_notes",""),
                       "changed_files":changed,
                       "compatibility":assess_compatibility(),
                       "migration":assess_migration(),
                       "artifact_integrity":{"state":"unknown"},
                       "installation_allowed":False},
            "note":"Version comparison only; installation and artifact integrity unverified."}


def discover_integration_update(entry, catalog, *, fetcher=fetch_releases,
                                compare_fetcher=fetch_compare_files):
    """Discovery states compare declarations only; installation state stays unknown."""
    result = _discover_integration_update(entry, catalog, fetcher=fetcher,
                                         compare_fetcher=compare_fetcher)
    errors = {"invalid_input", "invalid_registry_catalog", "invalid_release_data",
              "release_source_unavailable"}
    result.setdefault("comparison_state", "error" if result.get("reason") in errors else "unknown")
    result.setdefault("verification_state", "unknown")
    result["comparison_basis"] = "declared_version"
    result["version_scheme"] = "pep440"
    result["installation_allowed"] = False
    return result
