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
from game_integration_assessment_provenance import verify_assessment_document_bytes

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
            document = json.loads(data.decode("utf-8"))
            # No independently authenticated digest yet: result MUST stay unknown.
            result = verify_assessment_document_bytes(
                kind, data, expected_sha256=hashlib.sha256(data).hexdigest(),
                independent_digest_authenticated=False, **IDENTITY)
            if result["state"] != "unknown" or result["provenance_verified"] is not False:
                raise ValueError(kind + ": untrusted digest promoted to provenance")
            print(kind + ": pinned Git blob OK; SHA-256 " +
                  hashlib.sha256(data).hexdigest() +
                  "; independent provenance UNKNOWN (expected)")
        print("PASS: pinned fixture integrity and fail-closed provenance boundary")
    except (subprocess.CalledProcessError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
