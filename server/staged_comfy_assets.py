"""Resolve local staged assets only during explicit ComfyUI job execution."""
import http.client
import json
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit
try:
    from .game_job_attachments import ProjectJobAttachments, JobAttachmentsError
except ImportError:  # Direct gateway execution: python server/private_alpha_gateway.py
    from game_job_attachments import ProjectJobAttachments, JobAttachmentsError

ASSET_PREFIX = "minglefield-asset:"
ASSET_ID = re.compile(r"^[0-9a-f]{32}$")


def staged_record(host_id, root, token):
    if not isinstance(token, str) or not token.startswith(ASSET_PREFIX):
        raise JobAttachmentsError("invalid_asset_reference")
    asset_id = token[len(ASSET_PREFIX):]
    if not ASSET_ID.fullmatch(asset_id):
        raise JobAttachmentsError("invalid_asset_reference")
    staging = ProjectJobAttachments(host_id, root)
    record = staging.verify(asset_id)
    return staging.assets / asset_id, record


def upload_staged_asset(endpoint, asset_path, record):
    """Upload a verified local asset at execution time; return ComfyUI input name."""
    url = urlsplit(endpoint)
    if url.scheme not in ("http", "https") or not url.hostname:
        raise ValueError("invalid_comfy_endpoint")
    boundary = "minglefield" + secrets.token_hex(16)
    filename = record["filename"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", filename):
        raise ValueError("invalid_asset_filename")
    prefix = ("--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"" +
              filename + "\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
    middle = ("\r\n--" + boundary + "\r\nContent-Disposition: form-data; name=\"type\"\r\n\r\ninput" +
              "\r\n--" + boundary + "\r\nContent-Disposition: form-data; name=\"subfolder\"\r\n\r\n3d").encode()
    suffix = ("\r\n--" + boundary + "--\r\n").encode()
    cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    conn = cls(url.hostname, url.port, timeout=120)
    try:
        conn.putrequest("POST", (url.path.rstrip("/") if url.path not in ("", "/") else "") + "/upload/image")
        conn.putheader("Content-Type", "multipart/form-data; boundary=" + boundary)
        conn.putheader("Content-Length", str(len(prefix) + record["size"] + len(middle) + len(suffix)))
        conn.endheaders()
        conn.send(prefix)
        with Path(asset_path).open("rb") as source:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                conn.send(chunk)
        conn.send(middle)
        conn.send(suffix)
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError("comfy_upload_http_" + str(response.status))
        data = json.loads(response.read(65537))
        if not isinstance(data, dict) or not isinstance(data.get("name"), str):
            raise ValueError("invalid_comfy_upload_response")
        if (data.get("type") != "input" or data.get("subfolder") != "3d"
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", data["name"])):
            raise ValueError("unsupported_comfy_upload_location")
        return "3d/" + data["name"]
    finally:
        conn.close()
