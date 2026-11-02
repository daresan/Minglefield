# Local ComfyUI GLB transfer — P0 acceptance (2026-11-02)

## Scope and evidence

User reported successful execution of the imported SkinTokens workflow from the Minglefield alpha UI, following local GLB selection, staging, manual job creation and explicit execution. The user subsequently approved documenting the milestone and proceeding to the next phase. This is a **user-reported functional acceptance**, not an independently inspected ComfyUI output artifact.

Confirmed on the user's Windows/ComfyUI installation:

- `POST /upload/3d` with a GLB returned HTTP 405; do not use this route for uploads.
- `POST /upload/image` with multipart field `image`, `type=input`, `subfolder=3d` returned HTTP 200, `name=Chimal_pixellated.glb`, `subfolder=3d`, `type=input`.
- `GET /object_info/Load3D` exposed `model_file` as `COMBO` with `file_upload=true` and options containing `3d/Chimal_pixellated.glb`.
- Staged-asset focused tests: 2 passed. Full conformance suite: 431 passed (reported after pre-prompt error handling commits).
- User explicitly reported successful execution of the workflow in the alpha UI; output artifact identity, hash and final ComfyUI history were not independently collected.

## Implemented behavior

- Stage immutable, host-scoped file assets locally with integrity verification.
- Persist asset references at job creation; do not upload to ComfyUI until explicit execution.
- Reverify staged asset, upload to `/upload/image` with `subfolder=3d`, and substitute `3d/<uploaded-name>` for `Load3D.model_file` before `/prompt`.
- Differentiate failures before `/prompt` (terminal `failed`, slot released) from uncertain submissions after `/prompt` was attempted (`submission_unknown`, no automatic retry).

## P0 disposition

**Functionally accepted by the user for the tested local SkinTokens workflow.** This closes the *manual GLB transfer / execute* P0 gate and permits starting the separately gated Game tab (P1). It does **not** certify general ComfyUI file-upload compatibility, production readiness, remote-host support, autonomous execution or comprehensive job lifecycle management.

## P1 follow-up

1. Game tab: create/import/select Git-backed projects; project-scoped staging and output settings with migration/compatibility for existing host-scoped settings.
2. Job lifecycle: reconcile `submitted` with ComfyUI history/queue, persist completion/failure and output references, release active slots.
3. Asset lifecycle: list/reuse/delete staged assets with reference checks and audit; avoid deleting files referenced by active jobs.
4. Expand tests for failed upload, invalid response, `submission_unknown`, duplicate execute, project isolation and full UI flow.

Keep explicit execution authorization and no-premature-upload invariant intact.
