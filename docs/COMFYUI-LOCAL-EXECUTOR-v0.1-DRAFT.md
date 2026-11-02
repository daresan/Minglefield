# Minglefield ComfyUI Effect Adapter v0.1 — Integration design

Status: proposed, 2026-11-01. **Not implemented**. Current Private Alpha gateway is simulation-only and must not be treated as a production execution gateway. SEC-01 remains open.

## Strict UI boundary: parameter surface only (clarification 2026-11-01)
Minglefield **does not integrate or recreate the ComfyUI application**. ComfyUI remains the independent authoring/editor, model manager, node graph environment and runtime. Minglefield exposes **only the selected workflow's required inputs and permitted configurable parameters** in its existing Alpha Effects form, plus submission and basic job status/result references via existing Minglefield Jobs. Do not add a node editor, full workflow browser, ComfyUI settings/model management, or arbitrary ComfyUI control panels.

The user authors/edits the workflow in ComfyUI, uploads an exported JSON to the existing Effects tab, and Minglefield stores it privately outside Git. At import, analyze node input definitions and editable literal values, persist a minimal typed input schema and safe parameter bindings. Internal graph links, implementation-only settings and unsupported node controls are not automatically surfaced. For ambiguous parameters, allow a one-time import-time choice of which controls to expose; do not infer that all node widgets are required user inputs. Subsequent jobs set only those validated bindings, then use existing Minglefield effect/job dispatch to invoke ComfyUI. Re-import/revision is explicit.

## Approved import-time parameter selection (2026-11-01)
**Decision confirmed by project owner:** on upload, Minglefield automatically discovers **all identifiable editable workflow inputs and parameters** and presents them **once** in an import-time selection interface inside the existing Alpha Effects tab. The user selects which parameters will be exposed for future jobs. Persist that allowlist, type/range/enum metadata, node/input binding, default value and workflow content hash with the registered effect. On subsequent use, display **only selected parameters** in the ordinary Minglefield job/effect form; do not require repeated analysis or selection. Do not silently expose newly added parameters after a workflow revision; re-import/review explicitly. Unrecognized parameters must be marked as unsupported, not silently exposed or coerced. ComfyUI remains a separate application. This is a binding product decision, not an implemented feature.

## Binding product decision: upload once, register persistently in existing Alpha UI (2026-11-01)
- **No separate workflow browser or standalone ComfyUI interface.** Extend the existing Alpha **Effects** tab for workflow import/registration and parameter editing; use the existing Jobs tab for execution/status, or a contextual submit action that invokes the exact same existing job path.
- Upload a ComfyUI JSON file from the browser to an authenticated Minglefield user-scoped private data directory, **outside the Git checkout**. Use a configured application data root (Windows user application data by default), not a path inside the repository with only a .gitignore. Use immutable opaque storage IDs, safe filenames, file-size limits, ownership checks and atomic writes.
- **On each new upload**, parse and validate the workflow, query available ComfyUI node metadata when reachable, derive supported editable inputs and parameters, and persist the validated workflow definition **and derived form schema** in the existing Minglefield resource/effect storage. A workflow upload creates/updates a registered effect; it does not create a second workflow registry or scheduler. Preserve a content hash, version, ownership, host binding and validation warnings. Failed imports must not leave a partially registered effect.
- Subsequent UI visits load the stored schema and generate the form without requiring a reupload or reanalysis. Allow explicit reanalysis on version change or when installed ComfyUI custom-node metadata changes; do not silently change the semantics of existing registered workflows.
- Each execution references the stored registered effect/workflow version plus validated overrides. Dispatch through the existing Minglefield action/job/host/effect lifecycle and its audit/authorization gates.
- The ComfyUI API is expected on the same configured local interface used by the user's installation but may be **offline**. Upload and basic JSON analysis must work offline; metadata-dependent controls must be marked unresolved until ComfyUI is reachable. Never pretend unknown node schemas are validated.
- Remote-trigger-capable by architecture, but remote execution is disabled until SEC-01 safety gates pass. User-private workflow data must never become accessible merely because another user can see an effect ID.

## Goal / acceptance demo
On the Windows host running Minglefield and ComfyUI:
1. User uploads a ComfyUI workflow JSON in the existing Alpha Effects tab; the authenticated server stores it in the owner's private Minglefield application data directory outside Git.
2. On upload, Minglefield parses/validates the file and persistently registers the workflow and its derived parameter schema as an existing host-bound effect.
3. On subsequent visits the existing Effects UI regenerates controls from the stored schema for supported exposed inputs: text, integer, float, boolean, enum, seeds, image/file inputs, with defaults, ranges and labels.
4. User edits parameters and submits a local job with authenticated authorization and explicit consent.
5. Local executor submits a patched **API-format** prompt to a loopback ComfyUI endpoint (normally 127.0.0.1:8188), monitors progress/history, and reports output references, errors and logs.
6. Generated outputs can later be registered as versioned Minglefield assets and committed to a game repository after review.

## Workflow discovery and parsing
ComfyUI has multiple JSON representations: UI graph/export JSON and executable API prompt JSON. v0.1 accepts API-format JSON directly; UI-format JSON needs an explicit supported conversion/export step, never blind guessing.

API prompt nodes are keyed by node ID and have class_type and inputs. Inputs may be literals or links [node_id, output_index]. Obtain node metadata via ComfyUI /object_info when available to discover input types, widgets, ranges, enums and required/optional parameters. Do not infer a universal schema from raw JSON alone. Present node title/type and stable node ID in an advanced panel; use allowlisted widget/input types for v0.1. Exclude linked inputs from naive text editing; expose them only through explicit graph-aware controls. Unknown/custom node types remain read-only with an actionable warning until supported.

The uploaded workflow is stored in a per-user application data root outside Git. Never trust a browser-supplied filesystem path; use opaque storage IDs, authenticated ownership checks, bounded upload sizes, safe file handling and atomic registration. For uploaded image assets, validate content, size, and target input-node type; store in a controlled staging directory. Do not concatenate paths or shell commands.

## Mandatory reuse of existing Minglefield execution architecture
**Do not create a parallel executor, queue, scheduler, job registry, authorization subsystem or independent ComfyUI job API.** Reuse and extend the existing MAP action submission, durable job/queue, host/effect registration, dispatch adapter contracts, status, audit and cancellation mechanisms. First inspect the actual B1/B2 implementation and conformance tests on the current branch; document the precise integration points and missing capabilities before writing runtime code. The Alpha UI is currently a simulation-only façade, not authorization to bypass existing security gates.

Implement ComfyUI as a **host-installed effect adapter** under the existing effect/dispatch lifecycle. The one-time workflow upload, import-time input inspection and minimal dynamic parameter form are frontend/discovery capabilities; ComfyUI's own UI stays external. On submission they produce a validated action request and parameter payload handled by the existing Minglefield action/job path. A local ComfyUI process is the initial target, not a new local-only execution architecture.

A host owner must explicitly opt into the ComfyUI capability, register trusted workflows and grant eligible users/agents actions. Initially authorize only the local owner, with explicit human confirmation. The same adapter/host contract must remain capable of later receiving **authorized remote requests**; remote execution is gated on SEC-01 isolation, network security, revocation, quotas and provenance. Do not conflate host location, request origin and model location. The Alpha gateway must NOT directly run arbitrary scripts, custom nodes, PowerShell or Blender code. ComfyUI and custom nodes are powerful executable code and require trusted local installation.

Validate ComfyUI base URL against an explicit local allowlist; prevent SSRF or user-supplied endpoints. Prefer HTTP POST /prompt, GET /history/{prompt_id}, GET /queue and optional WebSocket /ws for progress. Use the **existing Minglefield** job IDs, idempotency, quotas, cancellation and audit semantics; add ComfyUI-specific prompt IDs as adapter metadata. Enforce output-path validation, bounded polling and timeout handling. Never promote the existing simulation-only effect endpoint into real execution implicitly.

## Interface mapping (non-normative)
- Workflow discovery/schema inspection: add read-only host-effect capability methods or endpoints only if the existing host/effect API cannot express them.
- Execution: **existing** action submission and B1/B2 job dispatch. Do not add `/api/local-comfy/jobs` or a second queue.
- Status and cancellation: **existing** Minglefield job endpoints and lifecycle; map ComfyUI prompt IDs and progress to the existing job record.
- Workflow hash and parameter overrides belong to the existing job request/audit metadata with secret redaction.
- No raw arbitrary filesystem path or unrestricted ComfyUI URL in job requests. Any necessary new fields must be schema-versioned and tested for backward compatibility.

## Incremental delivery
- P0: authenticated upload in existing Effects tab, private out-of-repo storage, one-time import analysis, persistent registered effect/schema, generated form and fixture tests.
- P1: integrate one trusted workflow into existing Minglefield host/effect adapter dispatch and job lifecycle; explicit local-owner opt-in, status, cancellation and mocked ComfyUI tests.
- P2: file/image uploads, richer custom-node controls, persistent queue, progress WebSocket and asset catalog integration.
- P3: approved agent-triggered jobs and repository publication with independent authorization, audit and review.

## Security and scope
Local-only does **not** mean sandboxed. Do not expose to remote users, teams or autonomous agents until SEC-01 controls, process isolation, limits, revocation propagation and code/data provenance are implemented and reviewed. The first milestone is a **human-approved local action through the existing Minglefield dispatch architecture**. The same host/adapter contract must be remote-trigger-capable by design, but remote invocation stays disabled until its security gates are satisfied; hosted LLMs are a separate later goal. Never assume successful conformance tests certify arbitrary workflow execution.
