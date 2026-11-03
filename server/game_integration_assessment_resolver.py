"""Server-controlled assessment resolver for read-only previews.

Only an operator-controlled, pre-approved manifest may be passed to this
factory. Neither release metadata nor request fields may supply this manifest.
The loader fetches bytes; it cannot select the trusted digest.
"""
from collections.abc import Mapping
from types import MappingProxyType
import re

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KINDS = frozenset(("compatibility", "migration"))


def make_assessment_resolver(approved_records, *, byte_loader):
    """Freeze approved records at construction; return a read-only resolver.

    Records keyed by (kind, integration_id, repository, from_version, to_version).
    Each record supplies an operator-approved sha256 and immutable commit ref.
    The byte_loader(repository, commit, kind) must fetch from that exact commit,
    enforce network/size limits, and never use branch-head substitution.
    """
    if not isinstance(approved_records, Mapping) or not callable(byte_loader):
        raise ValueError("invalid_resolver_configuration")
    checked = {}
    for key, record in approved_records.items():
        if (not isinstance(key, tuple) or len(key) != 5
                or key[0] not in _KINDS
                or any(not isinstance(part, str) or not part for part in key)
                or not isinstance(record, Mapping)):
            raise ValueError("invalid_approved_assessment_record")
        digest, commit = record.get("sha256"), record.get("commit")
        if (not isinstance(digest, str) or not _SHA256.fullmatch(digest)
                or not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit)):
            raise ValueError("invalid_approved_assessment_record")
        checked[key] = (digest, commit)
    frozen = MappingProxyType(checked)

    def resolve(*, kind, integration_id, release_source, from_version, to_version):
        if (not isinstance(release_source, dict)
                or release_source.get("provider") != "github"
                or not isinstance(release_source.get("repository"), str)):
            return None
        repository = release_source["repository"]
        key = (kind, integration_id, repository, from_version, to_version)
        approved = frozen.get(key)
        if approved is None:
            return None
        digest, commit = approved
        raw = byte_loader(repository, commit, kind)
        return {"raw_bytes": raw, "expected_sha256": digest, "authenticated": True}

    return resolve
