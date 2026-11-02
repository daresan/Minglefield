# Game Workspace and Asset Lifecycle v0.1 — Design Draft

Status: **requirements captured; not implemented** (2026-11-02). This document records decisions and pending work. It does not claim that the described features are shipped.

## Scope and product decisions

- Add a **Game** tab to the Minglefield alpha UI. A game is a versioned project associated with a local game-project repository and its configuration.
- Provide game create/import/open, settings, asset management, build, test, run and debugging workflows.
- Each game project defines its own **persistent local asset staging root** and **output root**. These are explicit, editable settings; neither is a ComfyUI input directory.
- File inputs use a native client file picker (browser file input on the current web UI). **Never require a raw path textbox as the primary file selection interface.**
- After selection, persist an asset into the game's managed local staging area, record its identity and integrity, and bind the job to that staged asset. **Do not upload to ComfyUI on selection or job creation.**
- **Only when the job starts**: validate the staged asset, transfer it to the selected local ComfyUI runtime if required, resolve the workflow's file parameter, then execute. Transfer failure must fail the job explicitly, with audit information.
- Use generic metadata/capability-driven file input handling, **not bespoke functions for every ComfyUI node**. ComfyUI custom widgets may expose insufficient metadata; report unsupported capabilities instead of guessing.
- Current target: gateway and ComfyUI run on the user's own Windows workstation. No cloud storage or provider linking is in scope now. Other users likewise operate against their own authorized local game workspace.
- Games should run **in the browser where supported**; otherwise launch a **separate local application instance** with observable process status and logs. Do not assume every game engine supports browser builds.

## Conceptual boundaries

1. **GameProject**: stable project ID, repository reference, engine/runtime profile, settings revision and owner/permissions.
2. **GameWorkspace**: local checkout and explicitly configured staging/output roots. Paths are resolved on the authorized user's host, not treated as remote third-party file shares.
3. **StagedAsset**: opaque ID, game ID, safe storage location, original display filename, size, SHA-256, type, created timestamp and lifecycle state. Never trust client-supplied absolute paths.
4. **JobAssetBinding**: job ID + workflow binding + staged asset ID; immutable for a queued job unless a deliberate job revision is made.
5. **RuntimeAsset**: transient or cached ComfyUI-side reference created **during job execution**; separate from the staged asset ID.
6. **OutputArtifact**: output path/reference, job ID, content hash, provenance, review/retention state and optional Git inclusion.
7. **GameRun**: engine/build target, launch mode (browser/local), build revision, process/session ID, logs and exit status.

## Proposed Game tab

- **Projects**: create, import from local Git checkout, select, inspect repository status, validate game manifest.
- **Settings**: project identity, repository root, staging root, output root, engine/build profile, startup/test commands; validate paths and permissions before saving.
- **Assets**: choose files with the OS dialog, stage and inspect assets, associate assets with jobs, view provenance and reference counts, safe cleanup.
- **Build & Test**: explicit human-triggered compile/build, test, inspect diagnostics and artifacts; no arbitrary shell execution from untrusted manifests.
- **Run & Debug**: browser launch when the target produces a supported web build; otherwise launch a separate local process. Show stdout/stderr, structured logs, errors, run state and stop/restart. Advanced debugger integration is a later capability requiring an engine-specific adapter.

## Asset and job state machine

```text
OS file picker
    -> stage locally (copy/stream into managed game staging; hash; durable metadata)
    -> bind staged asset ID to draft/queued job
    -> job accepted / waiting (NO ComfyUI transfer)
    -> job start: validate authorization, path containment, existence, size/hash
    -> runtime transfer using a supported generic ComfyUI upload capability
    -> resolve runtime file reference into workflow binding
    -> execute and track job
    -> capture outputs under configured project output root
    -> retain staged asset according to reference/retention policy
```

Staging on selection is **local persistence**, not transfer to ComfyUI. A canceled job must not silently delete assets still used by other jobs.

## Security and robustness gates

- Project settings changes require authorized ownership; validate canonical paths, traversal/symlinks, access and bounded quotas.
- Restrict staging and output writes to explicitly configured, authorized roots; never interpret arbitrary client paths as server-side file read requests.
- Atomic staging (temporary file then rename), hash verification, bounded upload size and clean failure recovery.
- Avoid uploading before job start; use idempotent runtime transfer semantics where possible and log retries.
- Separate untrusted game build/run definitions from trusted execution policy: allowlisted toolchains/commands, explicit user approval, process isolation, bounded resources and termination.
- Keep audit events for asset stage/bind/transfer, build/test/run, output publication and deletion.
- No implicit Git commit for generated assets. Large binary asset strategy (Git LFS/external artifact store) remains a decision.

## Implementation sequence and acceptance gates

### P0 — restore and protect working baseline
- [ ] Run complete conformance suite after the `verified` initialization fix; record exact results.
- [ ] Re-run first successful ComfyUI workflow and SkinTokens workflow; record fixture and expected behavior.
- [x] Preserve a fallback branch: `backup/comfy-first-working-runtime-2026-11-02`. Note: backup is a Git snapshot, not a proof of green tests.
- [ ] Add regression tests for metadata-verified/unverified input classification and file widget rendering.

### P1 — project model and Game tab skeleton
- [ ] Define versioned GameProject schema, local repo binding and persistence/migration.
- [ ] Add Game tab for create/import/select and settings editing.
- [ ] Validate staging/output roots and permissions; never silently create arbitrary directories.

### P2 — managed local staging and file picker
- [ ] Native browser file input, generic across supported file parameters.
- [ ] Persist selected files into project staging, with asset IDs, hashes and durable metadata.
- [ ] Bind assets to jobs without transferring to ComfyUI; verify persistence across gateway/browser restart.
- [ ] Support GLB and other configured file formats without node-specific UI code.

### P3 — job-start runtime transfer
- [ ] Determine actual supported ComfyUI upload semantics for file categories, including Load3D/custom nodes, from tested runtime behavior; do not assume `/upload/image` works for GLB.
- [ ] Add generic transfer capability mapping and runtime-reference resolution at execution time.
- [ ] Cover retry, cancellation, missing asset, hash mismatch and no-premature-upload tests.
- [ ] Confirm first workflow and SkinTokens end-to-end with staged assets.

### P4 — output and build/test/run
- [ ] Route outputs into configured game output root with provenance.
- [ ] Engine-neutral build/test/run interface with explicit trusted adapters per engine/toolchain (not per game).
- [ ] Browser preview for supported web targets; otherwise controlled local app launch.
- [ ] Run logs, errors, stop/restart and minimal debug console; interactive debugger integration later.

## Open decisions (do not silently decide in code)

- Game manifest schema and repository layout, including whether staging/output live inside or outside the Git working tree (recommend outside or ignored by default).
- Whether staging is host-local per game or can be shared between authorized checkouts; ownership and deduplication policy.
- Max file sizes, quotas, retention, cleanup and asset versioning.
- Which engines/build targets to support first and which web preview sandbox rules apply.
- Precise ComfyUI upload support for arbitrary custom file widgets; capability discovery and extension contract.
- Definition of the local game launcher service and trusted command allowlist.
- Distinction between development/test sessions and live gameplay; agent permissions and MAP isolation.

## Non-goals for this iteration

Cloud provider connections, remote hosting, universal debugger support for every engine, autonomous execution of arbitrary repository scripts, production deployment, and marketplace distribution.

## Related documents

- [Repository & Package Architecture v0.1](REPOSITORY-PACKAGE-ARCHITECTURE-v0.1-DRAFT.md)
- [Local ComfyUI Executor v0.1](COMFYUI-LOCAL-EXECUTOR-v0.1-DRAFT.md)
- [Minglefield Platform Vision](MINGLEFIELD-PLATFORM-VISION.md)
- [Public Roadmap](../ROADMAP.md)
