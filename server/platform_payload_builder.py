"""Deterministic SHA-256 inventory builder for a *prepared* platform payload.

This is not a bundler, signer or dependency resolver. The input is a private,
immutable staging directory containing all files intended for installation.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

from server.platform_payload_integrity import PayloadError, _safe_path, parse_inventory, verify_payload


def build_inventory(root: str | Path) -> bytes:
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise PayloadError("payload root must be a real directory")
    records = []
    names = set()
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        for name in dirs + files:
            p = Path(current) / name
            if p.is_symlink():
                raise PayloadError("symlink in payload")
            mode = p.lstat().st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise PayloadError("special file in payload")
        for name in files:
            path = Path(current) / name
            rel = _safe_path(path.relative_to(root).as_posix())
            folded = rel.casefold()
            if folded in names:
                raise PayloadError("case-colliding paths")
            names.add(folded)
            h = hashlib.sha256()
            size = 0
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
                    size += len(chunk)
            records.append({"path": rel, "sha256": h.hexdigest(), "size": size})
    records.sort(key=lambda x: x["path"])
    raw = (json.dumps({"format_version": 1, "files": records},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    parse_inventory(raw)
    verify_payload(root, raw)
    return raw


def write_inventory(root: str | Path, destination: str | Path) -> str:
    """Create inventory outside payload, without replacing an existing file."""
    root = Path(root).resolve(strict=True)
    destination = Path(destination)
    parent = destination.parent.resolve(strict=True)
    if parent == root or root in parent.parents:
        raise PayloadError("inventory output must be outside payload")
    if destination.is_symlink():
        raise PayloadError("inventory destination is a symlink")
    raw = build_inventory(root)
    with destination.open("xb") as output:
        output.write(raw)
    return hashlib.sha256(raw).hexdigest()
