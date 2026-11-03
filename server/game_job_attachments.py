"""Persistent, project-scoped job attachments.

No ComfyUI transfer occurs here. Callers must authenticate/authorize project
ownership before calling this storage primitive.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
from datetime import datetime, timezone

_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
MAX_ASSET_BYTES = 512 * 1024 * 1024


class JobAttachmentsError(ValueError):
    pass


class ProjectJobAttachments:
    """File-backed asset registry under a configured per-game directory.

    Store the staging root outside the Git working tree or add it to .gitignore.
    A single asset is immutable after creation. The original name is metadata,
    never used as a filesystem destination.
    """

    def __init__(self, project_id, root):
        if type(project_id) is not str or not _PROJECT.fullmatch(project_id):
            raise JobAttachmentsError("invalid_project_id")
        root = Path(root).expanduser()
        if not root.is_absolute():
            raise JobAttachmentsError("absolute_job_attachments_root_required")
        self.project_id = project_id
        self.root = root.resolve()
        self.assets = self.root / "assets"
        self.metadata = self.root / "metadata"

    def stage(self, filename, stream, size):
        if (type(filename) is not str or not _FILENAME.fullmatch(filename)
                or filename in (".", "..")):
            raise JobAttachmentsError("invalid_filename")
        if type(size) is not int or not 0 <= size <= MAX_ASSET_BYTES:
            raise JobAttachmentsError("invalid_asset_size")
        self.assets.mkdir(parents=True, exist_ok=True)
        self.metadata.mkdir(parents=True, exist_ok=True)
        asset_id = secrets.token_hex(16)
        digest = hashlib.sha256()
        temp_path = None
        target = self.assets / asset_id
        try:
            with tempfile.NamedTemporaryFile(dir=self.assets, prefix=".stage-",
                                             delete=False) as temp:
                temp_path = Path(temp.name)
                remaining = size
                while remaining:
                    chunk = stream.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise JobAttachmentsError("incomplete_asset")
                    temp.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_path, target)
            temp_path = None
            record = {"asset_id": asset_id, "project_id": self.project_id,
                      "filename": filename, "size": size,
                      "sha256": digest.hexdigest(),
                      "created_at": datetime.now(timezone.utc).isoformat()}
            metadata_temp = self.metadata / (asset_id + ".tmp")
            with metadata_temp.open("x", encoding="utf-8") as output:
                json.dump(record, output, sort_keys=True)
                output.flush()
                os.fsync(output.fileno())
            os.replace(metadata_temp, self.metadata / (asset_id + ".json"))
            return record
        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            (self.metadata / (asset_id + ".tmp")).unlink(missing_ok=True)
            raise

    def verify(self, asset_id):
        if type(asset_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", asset_id):
            raise JobAttachmentsError("invalid_asset_id")
        record_path = self.metadata / (asset_id + ".json")
        asset_path = self.assets / asset_id
        if not record_path.is_file() or not asset_path.is_file() or asset_path.is_symlink():
            raise JobAttachmentsError("asset_not_found")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("asset_id") != asset_id or record.get("project_id") != self.project_id:
            raise JobAttachmentsError("asset_project_mismatch")
        digest = hashlib.sha256()
        count = 0
        with asset_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                count += len(chunk)
                digest.update(chunk)
        if count != record.get("size") or digest.hexdigest() != record.get("sha256"):
            raise JobAttachmentsError("asset_integrity_failed")
        return record
