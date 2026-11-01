# Minglefield ComfyUI Effect Adapter v0.1 — Integration design

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

## Mandatory reuse of existing Minglefield execution architecture
**Do not create a parallel executor, queue, scheduler, job registry, authorization subsystem or independent ComfyUI job API.** Reuse and extend the existing MAP action submission, durable job/queue, host/effect registration, dispatch adapter contracts, status, audit and cancellation mechanisms. First inspect the actual B1/B2 implementation and conformance tests on the current branch; document the precise integration points and missing capabilities before writing runtime code. The Alpha UI is currently a simulation-only façade, not authorization to bypass existing security gates.

Implement ComfyUI as a **host-installed effect adapter** under the existing effect/dispatch lifecycle. The workflow picker, node-schema inspection and dynamic form are frontend/discovery capabilities. On submission they produce a validated action request and parameter payload handled by the existing Minglefield action/job path. A local ComfyUI process is the initial target, not a new local-only execution architecture.

A host owner must explicitly opt into the ComfyUI capability, register trusted workflows and grant eligible users/agents actions. Initially authorize only the local owner, with explicit human confirmation. The same adapter/host contract must remain capable of later receiving **authorized remote requests**; remote execution is gated on SEC-01 isolation, network security, revocation, quotas and provenance. Do not conflate host location, request origin and model location. The Alpha gateway must NOT directly run arbitrary scripts, custom nodes, PowerShell or Blender code. ComfyUI and custom nodes are powerful executable code and require trusted local installation.

Validate ComfyUI base URL against an explicit local allowlist; prevent SSRF or user-supplied endpoints. Prefer HTTP POST /prompt, GET /history/{prompt_id}, GET /queue and optional WebSocket /ws for progress. Use the **existing Minglefield** job IDs, idempotency, quotas, cancellation and audit semantics; add ComfyUI-specific prompt IDs as adapter metadata. Enforce output-path validation, bounded polling and timeout handling. Never promote the existing simulation-only effect endpoint into real execution implicitly.

## Interface mapping (non-normative)
- Workflow discovery/schema inspection: add read-only host-effect capability methods or endpoints only if the existing host/effect API cannot express them.
- Execution: **existing** action submission and B1/B2 job dispatch. Do not add `/api/local-comfy/jobs` or a second queue.
- Status and cancellation: **existing** Minglefield job endpoints and lifecycle; map ComfyUI prompt IDs and progress to the existing job record.
- Workflow hash and parameter overrides belong to the existing job request/audit metadata with secret redaction.
- No raw arbitrary filesystem path or unrestricted ComfyUI URL in job requests. Any necessary new fields must be schema-versioned and tested for backward compatibility.

## Incremental delivery
- P0: read-only workflow discovery, parser, metadata matching, generated form and fixture tests.
- P1: integrate one trusted workflow into existing Minglefield host/effect adapter dispatch and job lifecycle; explicit local-owner opt-in, status, cancellation and mocked ComfyUI tests.
- P2: file/image uploads, richer custom-node controls, persistent queue, progress WebSocket and asset catalog integration.
- P3: approved agent-triggered jobs and repository publication with independent authorization, audit and review.

## Security and scope
Local-only does **not** mean sandboxed. Do not expose to remote users, teams or autonomous agents until SEC-01 controls, process isolation, limits, revocation propagation and code/data provenance are implemented and reviewed. The first milestone is a **human-approved local action through the existing Minglefield dispatch architecture**. The same host/adapter contract must be remote-trigger-capable by design, but remote invocation stays disabled until its security gates are satisfied; hosted LLMs are a separate later goal. Never assume successful conformance tests certify arbitrary workflow execution.
