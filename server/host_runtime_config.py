"""Host-owned runtime definitions and safe ComfyUI workflow registration primitives.

This module does not execute workflows or make network requests. Callers must
authenticate the owner before invoking registry mutations.
"""
import copy
import hashlib
import json
import re
from urllib.parse import urlsplit

from server.comfy_workflow_inspection import inspect_api_workflow, WorkflowError

_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}$")
_TYPES = frozenset(("comfyui",))


class RuntimeConfigurationError(ValueError):
    pass


def validate_runtime(configuration):
    if type(configuration) is not dict:
        raise RuntimeConfigurationError("invalid_runtime")
    runtime_id = configuration.get("id")
    kind = configuration.get("type")
    if type(runtime_id) is not str or not _ID.fullmatch(runtime_id):
        raise RuntimeConfigurationError("invalid_runtime_id")
    if kind not in _TYPES:
        raise RuntimeConfigurationError("unsupported_runtime_type")
    endpoint = configuration.get("endpoint")
    if type(endpoint) is not str:
        raise RuntimeConfigurationError("invalid_endpoint")
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or parsed.port is None):
        raise RuntimeConfigurationError("endpoint_must_be_loopback")
    if not 1 <= parsed.port <= 65535:
        raise RuntimeConfigurationError("invalid_port")
    enabled = configuration.get("enabled", False)
    if type(enabled) is not bool:
        raise RuntimeConfigurationError("invalid_enabled")
    return {"id": runtime_id, "type": kind, "endpoint": endpoint.rstrip("/"),
            "enabled": enabled}


class HostRuntimeRegistry:
    """In-memory registry for integration with the existing host persistence layer.

    This is not a replacement for durable host storage.
    """
    def __init__(self):
        self._hosts = {}

    def put(self, owner_id, host_id, configuration):
        if not owner_id or not host_id:
            raise RuntimeConfigurationError("missing_host_identity")
        validated = validate_runtime(configuration)
        self._hosts.setdefault((owner_id, host_id), {})[validated["id"]] = validated
        return copy.deepcopy(validated)

    def list(self, owner_id, host_id):
        return copy.deepcopy(list(self._hosts.get((owner_id, host_id), {}).values()))

    def remove(self, owner_id, host_id, runtime_id):
        return self._hosts.get((owner_id, host_id), {}).pop(runtime_id, None) is not None

    def require(self, owner_id, host_id, runtime_id, kind="comfyui"):
        runtime = self._hosts.get((owner_id, host_id), {}).get(runtime_id)
        if runtime is None or not runtime["enabled"] or runtime["type"] != kind:
            raise RuntimeConfigurationError("runtime_unavailable")
        return copy.deepcopy(runtime)


def prepare_comfy_effect(raw, metadata, selected_bindings):
    """Prepare a versioned effect payload; caller persists via existing effect API.

    Only metadata-verified, scalar or enum inputs can be selected.
    """
    result = inspect_api_workflow(raw, metadata)
    if type(selected_bindings) is not list or any(type(b) is not str for b in selected_bindings):
        raise WorkflowError("invalid_selection")
    if len(selected_bindings) != len(set(selected_bindings)):
        raise WorkflowError("duplicate_selection")
    verified = {c["binding"]: c for c in result["candidates"] if c["verified"]}
    if any(b not in verified for b in selected_bindings):
        raise WorkflowError("unverified_binding")
    return {"adapter": "comfyui", "format": "api_prompt",
            "workflow_sha256": result["sha256"],
            "selected_bindings": list(selected_bindings),
            "parameters": [copy.deepcopy(verified[b]) for b in selected_bindings],
            "warnings": result["warnings"]}
