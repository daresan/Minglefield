"""Build-time GitHub source-provenance check; not an end-user installer prerequisite.

Requires only Python's standard library on the RELEASE BUILD machine. It
verifies a claimed commit against GitHub's repository ID and branch ancestry.
It does NOT authenticate build artifacts or authorize installation.
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request

OFFICIAL_REPOSITORY_ID = 1440772489
OFFICIAL_FULL_NAME = "daresan/Minglefield"


class ProvenanceError(ValueError):
    pass


def parse_source(text):
    fields = {}
    required = {"version", "repository_id", "repository", "commit"}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ProvenanceError("invalid source metadata line")
        key, value = (part.strip() for part in line.split("=", 1))
        if key not in required or key in fields:
            raise ProvenanceError("unknown or duplicate source metadata field")
        fields[key] = value
    if set(fields) != required or fields["version"] != "1":
        raise ProvenanceError("incomplete or unsupported source metadata")
    if not re.fullmatch(r"[1-9][0-9]*", fields["repository_id"]):
        raise ProvenanceError("invalid repository ID")
    repo_id = int(fields["repository_id"])
    if repo_id > 2**64 - 1:
        raise ProvenanceError("repository ID out of range")
    pieces = fields["repository"].split("/")
    if len(pieces) != 2 or any(
        not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", piece) or piece in (".", "..")
        for piece in pieces
    ):
        raise ProvenanceError("invalid repository owner/name")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", fields["commit"]):
        raise ProvenanceError("invalid commit SHA")
    return {
        "repository_id": repo_id,
        "repository": fields["repository"],
        "commit": fields["commit"].lower(),
    }


def github_get(path):
    request = urllib.request.Request(
        "https://api.github.com/" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Minglefield-release-provenance-build-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = response.read(1024 * 1024 + 1)
    if len(payload) > 1024 * 1024:
        raise ProvenanceError("GitHub response exceeds size limit")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ProvenanceError("unexpected GitHub response shape")
    return data


def verify_source(source, get=github_get):
    """Check GitHub API claims, never convert this into artifact authorization."""
    owner, name = source["repository"].split("/")
    root = "repos/{}/{}".format(
        urllib.parse.quote(owner, safe=""),
        urllib.parse.quote(name, safe=""),
    )
    repo = get(root)
    if (
        type(repo.get("id")) is not int
        or repo["id"] != source["repository_id"]
        or str(repo.get("full_name", "")).lower() != source["repository"].lower()
    ):
        raise ProvenanceError("GitHub repository identity mismatch")

    official = repo["id"] == OFFICIAL_REPOSITORY_ID
    if official and repo.get("full_name") != OFFICIAL_FULL_NAME:
        raise ProvenanceError("official repository name mismatch")

    commit_sha = source["commit"]
    commit = get(root + "/commits/" + commit_sha)
    if str(commit.get("sha", "")).lower() != commit_sha:
        raise ProvenanceError("commit does not match claimed SHA")

    branch_name = repo.get("default_branch")
    if not isinstance(branch_name, str) or not branch_name:
        raise ProvenanceError("missing GitHub default branch")
    if official and branch_name != "main":
        raise ProvenanceError("official release must originate from main")

    branch = get(root + "/branches/" + urllib.parse.quote(branch_name, safe=""))
    if branch.get("name") != branch_name:
        raise ProvenanceError("default branch mismatch")
    if official and branch.get("protected") is not True:
        raise ProvenanceError("official main is not marked protected")
    branch_sha = branch.get("commit", {}).get("sha", "")
    if not isinstance(branch_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}", branch_sha):
        raise ProvenanceError("invalid GitHub branch head")
    branch_sha = branch_sha.lower()

    comparison = get(root + "/compare/" + commit_sha + "..." + branch_sha)
    if (
        comparison.get("status") not in ("identical", "ahead")
        or comparison.get("behind_by") != 0
        or str(comparison.get("base_commit", {}).get("sha", "")).lower() != commit_sha
        or str(comparison.get("head_commit", {}).get("sha", "")).lower() != branch_sha
    ):
        raise ProvenanceError("commit is not on the default branch ancestry")

    return {
        "source_verified_via_github": True,
        "distribution": "official_upstream" if official else "independent_fork",
        "repository_id": repo["id"],
        "repository": repo["full_name"],
        "release_commit": commit_sha,
        "verified_branch_head": branch_sha,
        "artifact_authenticated": False,
        "installation_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="path to release source metadata")
    args = parser.parse_args(argv)
    try:
        with open(args.source, encoding="utf-8") as handle:
            source = parse_source(handle.read())
        print(json.dumps(verify_source(source), sort_keys=True))
        return 0
    except (OSError, ValueError, urllib.error.URLError) as error:
        print("release source verification failed: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
