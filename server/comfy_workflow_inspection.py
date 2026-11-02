"""Read-only ComfyUI API-prompt inspection for Minglefield effect imports.

No network access, execution, filesystem access, or workflow mutation.
The importer must use trusted /object_info metadata for authoritative widget types.
"""
import hashlib
import json
import math

MAX_WORKFLOW_BYTES = 2 * 1024 * 1024
MAX_NODES = 2048


class WorkflowError(ValueError):
    pass


def _is_link(value, nodes):
    return (type(value) is list and len(value) == 2
            and type(value[0]) is str and value[0] in nodes
            and type(value[1]) is int and value[1] >= 0)


def inspect_api_workflow(raw, object_info=None):
    """Return a deterministic candidate input schema; no parameters are exposed yet.

    object_info: optional trusted ComfyUI /object_info dictionary. Without it,
    literal candidates are reported as *unverified*, never authoritative.
    """
    if type(raw) is str:
        raw = raw.encode("utf-8")
    if type(raw) is not bytes or len(raw) > MAX_WORKFLOW_BYTES:
        raise WorkflowError("invalid_workflow_size")
    try:
        nodes = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise WorkflowError("invalid_json") from exc
    if type(nodes) is not dict or not 1 <= len(nodes) <= MAX_NODES:
        raise WorkflowError("invalid_api_prompt")
    for node_id, node in nodes.items():
        if (type(node_id) is not str or not node_id.isdecimal()
                or type(node) is not dict
                or type(node.get("class_type")) is not str
                or not node["class_type"]
                or type(node.get("inputs")) is not dict):
            raise WorkflowError("api_prompt_required")
    if object_info is not None and type(object_info) is not dict:
        raise WorkflowError("invalid_node_metadata")
    candidates = []
    warnings = []
    for node_id in sorted(nodes, key=lambda k: (int(k), k)):
        node = nodes[node_id]
        cls = node["class_type"]
        info = (object_info or {}).get(cls)
        definitions = info.get("input", {}) if type(info) is dict else {}
        definitions = definitions if type(definitions) is dict else {}
        fields = {}
        for group in ("required", "optional"):
            data = definitions.get(group, {})
            if type(data) is dict:
                fields.update(data)
        for name, value in sorted(node["inputs"].items()):
            if type(name) is not str:
                raise WorkflowError("invalid_input_name")
            if _is_link(value, nodes):
                continue
            if type(value) not in (str, int, float, bool):
                warnings.append(f"{node_id}.{name}: unsupported literal")
                continue
            if type(value) is float and not math.isfinite(value):
                warnings.append(f"{node_id}.{name}: non-finite number")
                continue
            spec = fields.get(name)
            kind = None
            choices = None
            limits = {}
            if type(spec) in (list, tuple) and len(spec) >= 1:
                t = spec[0]
                if type(t) is list and all(type(x) is str for x in t):
                    kind, choices = "enum", t
                elif t in ("STRING", "INT", "FLOAT", "BOOLEAN"):
                    kind = {"STRING": "string", "INT": "integer",
                            "FLOAT": "number", "BOOLEAN": "boolean"}[t]
                if len(spec) >= 2 and type(spec[1]) is dict:
                    limits = {k: v for k, v in spec[1].items()
                              if k in ("min", "max", "step") and
                              type(v) in (int, float) and math.isfinite(v)}
            # ComfyUI Load3D uses a custom file widget for model_file.
            # Some versions expose a non-scalar type in /object_info; the
            # workflow value itself remains a string path under input/3d/.
            if (cls == "Load3D" and name == "model_file"
                    and type(value) is str and type(info) is dict
                    and name in fields):
                kind = "file"
            if kind is None:
                kind = {str: "string", int: "integer", float: "number",
                        bool: "boolean"}[type(value)]
                verified = False
            # File picker widgets often publish STRING metadata with file-oriented
            # options; do not infer file permissions from the input name alone.
            if (kind == "string" and verified and type(spec) in (list, tuple)
                    and len(spec) >= 2 and type(spec[1]) is dict
                    and (spec[1].get("image_upload") or spec[1].get("file_upload")
                         or spec[1].get("upload") or spec[1].get("folder_paths"))):
                kind = "file"
            else:
                verified = True
            candidate = {"binding": f"{node_id}.{name}", "node_id": node_id,
                         "class_type": cls, "input": name, "type": kind,
                         "default": value, "verified": verified}
            if choices is not None:
                candidate["choices"] = choices
            if limits:
                candidate["limits"] = limits
            candidates.append(candidate)
            if not verified:
                warnings.append(f"{node_id}.{name}: type not verified by ComfyUI")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "node_count": len(nodes),
            "candidates": candidates, "warnings": warnings,
            "selected_bindings": []}
