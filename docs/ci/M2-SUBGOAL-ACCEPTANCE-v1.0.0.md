# M2 Platform Setup Manager — acceptance cases (MDCI v1.0.0)

**Purpose:** testable checkpoints for the already accepted M2 product under-goal
sequence. This is an **engineering acceptance specification**, not evidence
that an unimplemented or untested step is complete. See the
[MDCI policy](MINGLEFIELD-DEVELOPMENT-CI-POLICY-v1.0.0.md) for triggers,
version rollback and artifact-build rules.

For each gate record: source SHA, GitHub Actions run IDs with each actual
job status, test platform/version, fixture versus original data, observable
result, open defects, and the maintainer's acceptance. Never record DB keys,
login secrets, session tokens or raw rows in CI logs.

## Previously accepted GUI and safety checkpoints (no repeated package build)

### M2.01 — Portable Tauri Setup Manager

- Launch standalone Windows EXE, Linux AppImage and macOS app without first
  installing the Setup Manager or a Python developer environment.
- Open complete GPL and README offline from both Standard and Advanced.
- Keep actual Minglefield application installation disabled at this stage.
- **Packaging:** previous accepted milestone; rerun only on changed behavior.

### M2.02 — Database inspection and typed editor

- Load known Alpha tables and all actual records into Login, Hosts, Effects,
  Jobs and Games; show unknown tables separately.
- Stage supported typed value changes; reject invalid/stale corrections.
- Verify original versus proposed review and unchanged source after close.
- **Packaging:** previously accepted; no repeat for core-only changes.

### M2.03 — Temporary encrypted SQLCipher proof

- Compare all rows, BLOBs, metadata and schema objects against verified RAM.
- Reject wrong key, occupied final targets and unsafe source/destination paths.
- Require full cleanup and `destinationCreated=false`,
  `migrationEnabled=false`, `executionEnabled=false`.
- **Packaging:** previously accepted on Shadow.

### M2.04 — Rust/Python ciphertext and login interoperability

- Python SQLCipher runtime opens the exact Rust-exported test ciphertext.
- Provision the independently protected `mingleadmin` account in a disposable
  encrypted DB, authenticate normally, reject wrong key/duplicate provision.
- Deny unrelated Host permissions and do not create an invitation.
- **Packaging:** none; collect three-OS core CI evidence.

### M2.05 — Destination-volume rehearsal

- Stage private encrypted scratch only within a test target parent on the
  selected filesystem, reopen and compare all rows/schema objects.
- Reject occupied final target, missing parent, non-directory and symlink
  parent; preserve existing target bytes.
- After success, find no final target and no residual scratch files; source
  remains identical. Review native Windows/macOS and Ubuntu CI separately.
- **Packaging:** none; the existing GUI still uses OS-temporary rehearsal.

## Pending user-visible gates

### M2.06 — Exclusive durable encrypted database publication

- On a **disposable representative fixture**, require positive user approval,
  strong new SQLCipher key and a verified full-source review before mutation.
- Stage on the target volume, pin/check native parent identity at mutation
  time and verify ciphertext is flushed and fully readable before publication.
- Publish the final name exclusively; a collision/race must fail without
  modifying the existing file or the original Alpha source.
- Reopen the published encrypted file, reject wrong keys, compare full
  rows/schema and verify registered migration metadata.
- Negative: stale review, source change, access denial and directory
  substitution must fail closed. No partial destination or leaked key.
- **Packaging:** one portable three-OS acceptance build when usable GUI
  execution and rollback/authorization gates are ready; never test first
  against an unbacked-up real user database.

### M2.07 — Crash recovery and rollback

- Inject interruption before staging, after encrypted export, before exclusive
  publication, just after publication and during post-publish verification.
- Restart and inspect for an intact prior source, absence of partial target,
  and correctly classified recoverable state.
- Reject idempotency/retry collisions; distinguish cleanup failures from a
  verified target and preserve any preexisting non-Minglefield file.
- **Packaging:** one acceptance build after automated fault injection.

### M2.08 — First-run `mingleadmin` and local Host binding

- Require an explicitly authorized, installation-bound, local-only,
  single-use Host activation handshake (no manual local console invite).
- Create only the local user, salted login verifier and approved local Host
  ownership; sign-in password differs from SQLCipher key.
- Reject replay, concurrent double setup, preexisting identity/Host ownership,
  impersonation and remote-Host escalation; roll back partial transactions.
- Verify normal login and host-scoped administration; remote Host control
  requires separate valid grant.
- **Packaging:** one acceptance build after real first-run path is wired.

### M2.09 — Encrypted operational runtime

- Launch the installed Alpha against the migrated encrypted SQLCipher file.
- Verify ordinary login/session, Hosts, Effects, Jobs and Game storage survive
  process restart and remain tenant/Host-scoped.
- Missing driver, missing key or wrong key must fail closed without silently
  falling back to plaintext SQLite or retaining the key in logs/config.
- **Packaging:** combine with M2.10 unless distinct user-visible UX requires
  a separately accepted build.

### M2.10 — Managed Python runtime and Minglefield application payload

- On clean Windows/Linux/macOS environments, install the separately packaged
  Minglefield Alpha and verified pinned Python/SQLCipher runtime.
- Launch without Git, Conda, developer Python or prior Minglefield checkout.
- Verify manifest, runtime dependency closure and checksum/integrity.
- Close or remove the portable Setup Manager; installed app and user data
  must remain available.
- **Packaging:** one three-OS acceptance build.

### M2.11 — Standard, Advanced and headless parity

- Standard: safe user-scoped defaults, suitable data directory and clear
  installation completion.
- Advanced: selected destination/data paths, existing-install detection,
  conflict prompts and optional component consent.
- CLI: `--silent --defaults` shares validation/engine; no implicit Host claim,
  credential generation, optional runtime consent or destructive action.
- Negative: inaccessible destination, interrupted install and invalid config
  yield safe errors and deterministic no-mutation behavior.
- **Packaging:** one three-OS acceptance build.

### M2.12 — Optional Conda and ComfyUI integration

- Detect existing non-PATH Conda and a manually selected compatible runtime.
- Detect/reuse/local-connect ComfyUI and only install the consented official
  standard distribution; never add models/custom nodes/workflows implicitly.
- Confirm per-Host runtime configuration via existing Hosts persistence and
  local connection check; avoid global hardcoded runtime settings.
- Negative: decline consent, offline acquisition and incompatible paths do
  not affect existing environments.
- **Packaging:** one three-OS acceptance build.

### M2.13 — Update, repair and uninstall

- Verify unchanged data, users, Hosts, agent ownership and saved runtime
  settings across update/repair.
- Repeated repair is idempotent; corrupted download, wrong provenance and
  interruption fail safely with recovery/rollback.
- Uninstall asks explicitly about keeping persistent user data and does not
  delete unrelated files or a shared Python/ComfyUI installation.
- **Packaging:** one three-OS acceptance build.

### M2.14 — Cross-platform acceptance

- On Windows/Linux/macOS test clean install, preexisting installation,
  non-PATH optional tools, manual custom paths, database migration and
  credential/Host conflicts.
- Verify launch and recovery in native environments, not only successful
  compilation of the GUI bundle.
- Run the representative nontechnical-user study for the approved 80%
  unaided-onboarding **target**; report observed outcomes rather than
  claiming the target from CI alone.
- **Packaging:** one release-candidate three-OS build.

### M2.15 — First Alpha release

- Verify versioned release manifest, platform/arch and entry points,
  checksums, repeatable dependency lock/inventory and GPL/attribution.
- Validate installer-to-application boundary, clean launch, upgrade and
  recovery; document experimental/local-only limitations.
- Publish only after explicit maintainer approval. Apple notarization/signing
  is not an additional requirement under the current accepted scope.
- **Packaging:** one approved release build, distinct from the setup-manager
  prototype artifacts.

## Acceptance rule

A technical-only gate may be **CI accepted without a new portable package**.
A package may be built only for the identified user-visible subgoal's
explicit test request or a separately authorized build repair. Never use a
green build status to infer successful real-world installation, durable
database migration or Host ownership authorization.
