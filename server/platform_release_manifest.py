"""Validate a Minglefield platform release manifest (format v1).

This validates the *shape and safety* of metadata, not publisher trust or payload
integrity. Installers must additionally verify an out-of-band trusted signature
and hash actual downloaded files before execution.
"""
from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?\Z")
_OS = {"windows", "macos", "linux"}
_ARCH = {"x86_64", "arm64"}
_CHANNEL = {"alpha", "beta", "stable"}


class ManifestError(ValueError):
    """Release metadata is invalid or unsupported."""


def _object(value: Any, keys: set[str], where: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ManifestError(f"{where}: expected exactly {sorted(keys)}")
    return value


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ManifestError(f"{where}: nonempty string required")
    return value


def _hash(value: Any, where: str) -> None:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise ManifestError(f"{where}: lowercase SHA-256 required")


def _path(value: Any, where: str) -> None:
    s = _string(value, where)
    if (
        "\\" in s or ":" in s or s.startswith("/")
        or any(p in ("", ".", "..") for p in s.split("/"))
        or PurePosixPath(s).is_absolute()
        or any(ord(c) < 32 for c in s)
    ):
        raise ManifestError(f"{where}: unsafe relative payload path")


def validate_manifest(doc: Any, *, expected_os: str | None = None,
                      expected_arch: str | None = None) -> dict:
    """Return validated metadata; never treat this as signature verification."""
    m = _object(doc, {"format_version", "product_id", "release", "target",
                      "payload", "runtime", "data", "legal", "provenance"}, "manifest")
    if type(m["format_version"]) is not int or m["format_version"] != 1:
        raise ManifestError("unsupported manifest format")
    if m["product_id"] != "org.minglefield.app":
        raise ManifestError("wrong product identity")
    release = _object(m["release"], {"version", "channel"}, "release")
    if not isinstance(release["version"], str) or not _VERSION.fullmatch(release["version"]):
        raise ManifestError("invalid release version")
    if release["channel"] not in _CHANNEL:
        raise ManifestError("unsupported release channel")
    target = _object(m["target"], {"os", "arch"}, "target")
    if target["os"] not in _OS or target["arch"] not in _ARCH:
        raise ManifestError("unsupported target")
    if expected_os is not None and target["os"] != expected_os:
        raise ManifestError("wrong target OS")
    if expected_arch is not None and target["arch"] != expected_arch:
        raise ManifestError("wrong target architecture")
    payload = _object(m["payload"], {"entrypoint", "files_manifest",
                                     "files_manifest_sha256"}, "payload")
    for key in ("entrypoint", "files_manifest"):
        _path(payload[key], "payload." + key)
    _hash(payload["files_manifest_sha256"], "payload.files_manifest_sha256")
    runtime = _object(m["runtime"], {"kind", "python_version", "lockfile",
                                     "lockfile_sha256"}, "runtime")
    if runtime["kind"] != "bundled-python":
        raise ManifestError("unsupported runtime kind")
    _string(runtime["python_version"], "runtime.python_version")
    _path(runtime["lockfile"], "runtime.lockfile")
    _hash(runtime["lockfile_sha256"], "runtime.lockfile_sha256")
    data = _object(m["data"], {"schema_version", "minimum_compatible_schema",
                               "migration_manifest"}, "data")
    _string(data["schema_version"], "data.schema_version")
    _string(data["minimum_compatible_schema"], "data.minimum_compatible_schema")
    if data["migration_manifest"] is not None:
        _path(data["migration_manifest"], "data.migration_manifest")
    legal = _object(m["legal"], {"license_manifest", "license_manifest_sha256"}, "legal")
    _path(legal["license_manifest"], "legal.license_manifest")
    _hash(legal["license_manifest_sha256"], "legal.license_manifest_sha256")
    provenance = _object(m["provenance"], {"source_revision", "build_id", "signature"}, "provenance")
    if not isinstance(provenance["source_revision"], str) or not re.fullmatch(r"[0-9a-f]{40}", provenance["source_revision"]):
        raise ManifestError("invalid source revision")
    _string(provenance["build_id"], "provenance.build_id")
    _string(provenance["signature"], "provenance.signature")
    return m


def load_manifest(raw: bytes, **kwargs: Any) -> dict:
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ManifestError("invalid UTF-8 JSON") from exc
    return validate_manifest(doc, **kwargs)
