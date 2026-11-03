"""Verify a staged platform payload against a complete SHA-256 inventory.

The inventory is UTF-8 JSON: {"format_version": 1, "files": [
  {"path": "Minglefield.exe", "sha256": "<hex>", "size": 123}
]}
This checks integrity, not publisher authenticity. The caller must first verify
the signed release metadata and the inventory hash against that metadata.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

_HEX = re.compile(r"[0-9a-f]{64}\Z")


class PayloadError(ValueError):
    pass


def _safe_path(s):
    if not isinstance(s, str) or not s or s.startswith("/") or "\\" in s or ":" in s:
        raise PayloadError("unsafe payload path")
    if any(p in ("", ".", "..") for p in s.split("/")) or any(ord(c) < 32 for c in s):
        raise PayloadError("unsafe payload path")
    return s


def parse_inventory(raw):
    try:
        def no_duplicates(pairs):
            d = {}
            for k, v in pairs:
                if k in d:
                    raise PayloadError("duplicate JSON key")
                d[k] = v
            return d
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeError, ValueError) as exc:
        raise PayloadError("invalid inventory JSON") from exc
    if not isinstance(doc, dict) or set(doc) != {"format_version", "files"}:
        raise PayloadError("invalid inventory shape")
    if type(doc["format_version"]) is not int or doc["format_version"] != 1:
        raise PayloadError("unsupported inventory format")
    files = doc["files"]
    if not isinstance(files, list) or not files:
        raise PayloadError("empty or invalid inventory")
    seen = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size"}:
            raise PayloadError("invalid file record")
        p = _safe_path(entry["path"])
        if p in seen or p.casefold() in {x.casefold() for x in seen}:
            raise PayloadError("duplicate or case-colliding path")
        seen.add(p)
        if not isinstance(entry["sha256"], str) or not _HEX.fullmatch(entry["sha256"]):
            raise PayloadError("invalid SHA-256")
        if type(entry["size"]) is not int or entry["size"] < 0:
            raise PayloadError("invalid file size")
    return doc


def verify_payload(root, raw_inventory, *, expected_inventory_sha256=None):
    """Fail closed on missing/extra files, symlinks and mismatched hashes.

    The staging directory must be private and not concurrently writable by an
    attacker. This function does not provide race-safe handle-based verification.
    """
    if expected_inventory_sha256 is not None:
        if hashlib.sha256(raw_inventory).hexdigest() != expected_inventory_sha256:
            raise PayloadError("inventory digest mismatch")
    doc = parse_inventory(raw_inventory)
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise PayloadError("invalid payload root")
    expected = {entry["path"]: entry for entry in doc["files"]}
    actual = set()
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        for name in dirs + files:
            p = Path(current) / name
            if p.is_symlink():
                raise PayloadError("symlink in payload")
            mode = p.lstat().st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise PayloadError("special file in payload")
        for name in files:
            p = Path(current) / name
            rel = p.relative_to(root).as_posix()
            _safe_path(rel)
            actual.add(rel)
            if rel not in expected:
                raise PayloadError("unexpected payload file")
            entry = expected[rel]
            if p.stat().st_size != entry["size"]:
                raise PayloadError("payload size mismatch")
            digest = hashlib.sha256()
            with p.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != entry["sha256"]:
                raise PayloadError("payload SHA-256 mismatch")
    if actual != set(expected):
        raise PayloadError("missing payload file")
    return len(actual)
