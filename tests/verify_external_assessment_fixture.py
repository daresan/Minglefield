"""T4 read-only fixture verification against an exact external Git commit.

Run with the local minglefield-integration-test checkout path. No Git fetch,
checkout, writes, installation, or trust promotion. Git object IDs are not a
substitute for an independently approved SHA-256 trust anchor.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from fixture_assessment_trust import verify_pinned_test_assessment

COMMIT = "6df11272a9ca14dcfb8dc3bbe26b29c189d12253"
SOURCE = {"provider": "github", "repository": "daresan/minglefield-integration-test"}
IDENTITY = dict(expected_integration_id="community.daresan.test",
                authorized_source=SOURCE, from_version="v1.0.0", to_version="v1.1.0")
FILES = {
    "compatibility": ("fixtures/assessments/v1.0.0-to-v1.1.0.compatibility.json",
                      "e3bcbfa4be91fac54d9c134b89f7271c6781bc8d"),
    "migration": ("fixtures/assessments/v1.0.0-to-v1.1.0.migration.json",
                  "70c979f1910759a568a76e5241055c757b386fee"),
}


def git(repo, *args, data=None):
    return subprocess.run(["git", "-C", str(repo), *args], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True).stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path, help="Local test-repository checkout")
    args = parser.parse_args()
    if not args.repo.is_dir():
        parser.error("Test repository directory does not exist")
    try:
        resolved = git(args.repo, "rev-parse", "--verify", COMMIT + "^{commit}").decode().strip()
        if resolved != COMMIT:
            raise ValueError("Unexpected commit identity")
        for kind, (path, expected_blob) in FILES.items():
            data = git(args.repo, "show", COMMIT + ":" + path)
            blob = git(args.repo, "hash-object", "--stdin", data=data).decode().strip()
            if blob != expected_blob:
                raise ValueError(kind + ": pinned Git blob mismatch")
            result = verify_pinned_test_assessment(
                kind, data, source_repository="daresan/minglefield-integration-test",
                source_commit=COMMIT, integration_id="community.daresan.test",
                from_version="v1.0.0", to_version="v1.1.0")
            if result["state"] != "verified" or result["provenance_verified"] is not True:
                raise ValueError(kind + ": approved fixture digest not verified: " + str(result))
            tampered = verify_pinned_test_assessment(
                kind, data + b" ", source_repository="daresan/minglefield-integration-test",
                source_commit=COMMIT, integration_id="community.daresan.test",
                from_version="v1.0.0", to_version="v1.1.0")
            if tampered["state"] != "invalid":
                raise ValueError(kind + ": modified bytes accepted")
            wrong_source = verify_pinned_test_assessment(
                kind, data, source_repository="attacker/repository",
                source_commit=COMMIT, integration_id="community.daresan.test",
                from_version="v1.0.0", to_version="v1.1.0")
            if wrong_source["state"] != "invalid":
                raise ValueError(kind + ": wrong source accepted")
            print(kind + ": approved pinned fixture SHA-256 verified; tamper/source denied")
        print("PASS: test-only pinned fixture provenance and negative controls")
    except (subprocess.CalledProcessError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
