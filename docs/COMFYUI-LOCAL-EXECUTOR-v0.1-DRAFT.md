# Minglefield Local ComfyUI Executor v0.1 — Implementation design

Status: proposed, 2026-11-01. **Not implemented**. Current Private Alpha gateway is simulation-only and must not be treated as a production execution gateway. SEC-01 remains open.

## Goal / acceptance demo
On the Windows host running Minglefield and ComfyUI:
1. User selects an existing local ComfyUI workflow JSON from an explicitly configured directory (or uploads a JSON through the browser; the browser cannot arbitrarily browse server paths).
2. Minglefield parses and validates it without executing it.
3. UI generates controls for supported exposed inputs: text, integer, float, boolean, enum, seeds, image/file inputs, with defaults, ranges and labels.
4. User edits parameters and submits a local job with authenticated authorization and explicit consent.
5. Local executor submits a patched **API-format** prompt to a loopback ComfyUI endpoint (normally 127.0.0.1:8188), monitors progress/history, and reports output references, errors and logs.
6. Generated outputs can later be registered as versioned Minglefield assets and committed to a game repository after review.

## Workflow discovery and parsing
ComfyUI has multiple JSON representations: UI graph/export JSON and executable API prompt JSON. v0.1 accepts API-format JSON directly; UI-format JSON needs an explicit supported conversion/export step, never blind guessing.

API prompt nodes are keyed by node ID and have class_type and inputs. Inputs may be literals or links [node_id, output_index]. Obtain node metadata via ComfyUI /object_info when available to discover input types, widgets, ranges, enums and required/optional parameters. Do not infer a universal schema from raw JSON alone. Present node title/type and stable node ID in an advanced panel; use allowlisted widget/input types for v0.1. Exclude linked inputs from naive text editing; expose them only through explicit graph-aware controls. Unknown/custom node types remain read-only with an actionable warning until supported.

The selected workflow file is read from an admin-configured allowed root; resolve real paths and reject traversal, symlinks escaping root, oversized files and non-JSON. Never let a browser-provided arbitrary filesystem path be read by the server. For uploaded image assets, validate content, size, and target input-node type; store in a controlled staging directory. Do not concatenate paths or shell commands.

## Executor boundary
Create a distinct local-only executor process/adapter. The Alpha gateway must NOT directly run arbitrary scripts, ComfyUI custom nodes, PowerShell or Blender code. Require explicit opt-in to enable execution, bind loopback only, and authenticate each job with current Minglefield user/session, ownership and host permissions. ComfyUI itself and installed custom nodes must be treated as powerful executable code; start with trusted, locally installed workflows only.

Validate ComfyUI base URL against an explicit local allowlist; prevent SSRF or user-supplied endpoints. Prefer HTTP POST /prompt, GET /history/{prompt_id}, GET /queue and optional WebSocket /ws for progress. Use server-side job IDs, idempotency, quotas, cancellation, output-path validation, bounded polling and timeout handling. Record audit events without logging secrets. Never promote the existing simulation-only effect endpoint into a real executor implicitly.

## Proposed API (non-normative)
- GET /api/local-comfy/workflows — list allowlisted workflow names/IDs.
- GET /api/local-comfy/workflows/{id}/schema — validated graph, editable controls, warnings.
- POST /api/local-comfy/jobs — workflow ID, validated parameter overrides, explicit confirmation.
- GET /api/local-comfy/jobs/{id} — status/progress/error/output manifest.
- POST /api/local-comfy/jobs/{id}/cancel — cancel authorized job, where safely supported.

No raw arbitrary workflow path or unrestricted ComfyUI URL in job requests. Track states queued, validating, submitted, running, completed, failed, cancel_requested, cancelled. Store workflow hash and exact parameter overrides for reproducibility.

## Incremental delivery
- P0: read-only workflow discovery, parser, metadata matching, generated form and fixture tests.
- P1: separate loopback executor with one known trusted minimal workflow; submission, status, cancellation, explicit opt-in, integration tests with mocked ComfyUI.
- P2: file/image uploads, richer custom-node controls, persistent queue, progress WebSocket and asset catalog integration.
- P3: approved agent-triggered jobs and repository publication with independent authorization, audit and review.

## Security and scope
Local-only does **not** mean sandboxed. Do not expose to remote users, teams or autonomous agents until SEC-01 controls, process isolation, limits, revocation propagation and code/data provenance are implemented and reviewed. The first milestone is a **human-approved local action**; remote compute and hosted LLMs are later goals. Never assume successful conformance tests certify arbitrary workflow execution.
