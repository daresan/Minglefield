"""T4 live read-only assessment preview against pinned external GitHub fixtures.

Run manually: python -B tests/verify_live_assessment_preview.py
The allowlist here is test-only; it must never be loaded as a production trust store.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from game_integration_assessment_loader import load_pinned_assessment_bytes
from game_integration_assessment_resolver import make_assessment_resolver
from game_integration_assessment_preview import preview_release_assessments

REPO = "daresan/minglefield-integration-test"
COMMIT = "6df11272a9ca14dcfb8dc3bbe26b29c189d12253"
INTEGRATION = "community.daresan.test"
FROM_VERSION, TO_VERSION = "v1.0.0", "v1.1.0"
APPROVED = {
    ("compatibility", INTEGRATION, REPO, FROM_VERSION, TO_VERSION): {
        "sha256": "d14e3952d1afad096ffb31c20f12fab4b74f1ca57af3edefbc3be0c72aef11e5",
        "commit": COMMIT,
    },
    ("migration", INTEGRATION, REPO, FROM_VERSION, TO_VERSION): {
        "sha256": "7d37b304a01a5e4fac0c77823416f688ccbaa9cd98f0b682cc6cf88e4aed3ccb",
        "commit": COMMIT,
    },
}
ARGS = dict(integration_id=INTEGRATION,
            release_source={"provider": "github", "repository": REPO},
            from_version=FROM_VERSION, to_version=TO_VERSION)


def main():
    resolver = make_assessment_resolver(APPROVED, byte_loader=load_pinned_assessment_bytes)
    result = preview_release_assessments(**ARGS, resolver=resolver)
    for kind in ("compatibility", "migration"):
        item = result[kind]
        if (item.get("document_provenance") != "verified"
                or item.get("state") != "unknown"):
            raise AssertionError(f"{kind}: unexpected assessment result {item!r}")
        print(f"{kind}: independently pinned digest and release identity VERIFIED; "
              "target assessment UNKNOWN (expected)")
    if result["installation_allowed"] is not False:
        raise AssertionError("installation must remain blocked")

    # Wrong identity must not fetch or inherit the fixture's approval.
    wrong = preview_release_assessments(
        **{**ARGS, "to_version": "v1.2.0"}, resolver=resolver)
    if (wrong["compatibility"].get("document_provenance") == "verified"
            or wrong["migration"].get("document_provenance") == "verified"
            or wrong["installation_allowed"] is not False):
        raise AssertionError("unapproved version gained trust")
    print("PASS: live pinned assessment preview, fail-closed target and unapproved version")


if __name__ == "__main__":
    main()
