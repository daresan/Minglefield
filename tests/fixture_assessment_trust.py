"""Test-only pinned assessment fixture anchor.

This is a developer-controlled fixture allowlist, NOT a production publisher
trust store. Never load these entries for arbitrary user repositories/releases.
"""
from game_integration_assessment_provenance import verify_assessment_document_bytes

_FIXTURE_COMMIT = "6df11272a9ca14dcfb8dc3bbe26b29c189d12253"
_FIXTURE_REPO = "daresan/minglefield-integration-test"
_DIGESTS = {
    "compatibility": "d14e3952d1afad096ffb31c20f12fab4b74f1ca57af3edefbc3be0c72aef11e5",
    "migration": "7d37b304a01a5e4fac0c77823416f688ccbaa9cd98f0b682cc6cf88e4aed3ccb",
}


def verify_pinned_test_assessment(kind, raw_bytes, *, source_repository,
                                  source_commit, integration_id,
                                  from_version, to_version):
    """Verify one exact fixture; never allow arbitrary caller-selected anchors."""
    blocked = {"provenance_verified": False, "installation_allowed": False}
    if (source_repository != _FIXTURE_REPO or source_commit != _FIXTURE_COMMIT
            or integration_id != "community.daresan.test"
            or from_version != "v1.0.0" or to_version != "v1.1.0"):
        return {**blocked, "state": "invalid", "reason": "unapproved_fixture_identity"}
    if kind not in _DIGESTS:
        return {**blocked, "state": "invalid", "reason": "unapproved_assessment_kind"}
    return verify_assessment_document_bytes(
        kind, raw_bytes, expected_sha256=_DIGESTS[kind],
        independent_digest_authenticated=True,
        expected_integration_id="community.daresan.test",
        authorized_source={"provider": "github", "repository": _FIXTURE_REPO},
        from_version="v1.0.0", to_version="v1.1.0")
