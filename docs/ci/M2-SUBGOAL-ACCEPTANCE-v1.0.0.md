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

**Verified intermediate T2/T3 evidence (not full M2.06 acceptance):**
At source commit `b136fbfb5d16134916ddb68a0dbbc189293bc06c`,
the Rust-test-only fixture path creates a real SQLCipher file at a
previously unoccupied selected test filename, reopens and compares its
contents, and independently opens it with the operational Python runtime.
Plain/encrypted source, edited values, source preservation, occupied output,
weak key, stale review and absent parent cases passed on
[Ubuntu](https://github.com/daresan/Minglefield/actions/runs/42162575420)
and [Windows/macOS](https://github.com/daresan/Minglefield/actions/runs/42162575471).
This is **real file creation in CI, not a usable GUI migration command**;
`execution_enabled` and public rehearsal flags remain false.
The next acceptance gate is an explicitly authorized/limited Tauri
migration path and separate real-user backup safeguards.

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
- **Controlled Alpha testbuild gate (before full M2.06 closure):**
  publish a verified SQLCipher copy to a previously absent chosen test
  filename, reopen it from Rust and Python, verify all source/staged values
  and schema, and reject existing-file collision, wrong key, stale review
  and denied access without touching the original. CI uses only disposable
  fixtures. Installer exposure requires explicit user consent and a
  clearly labeled test-only scope; any real-user source needs an
  independently verified backup and explicit risk acknowledgement.
  The controlled Alpha testbuild may precede complete hostile-directory
  race hardening, but cannot bypass the basic exclusive-creation guarantee.
- **Controlled GUI wiring (implemented; human acceptance pending):**
  The final Tauri Review page now offers an expressly consented database-only
  creation command after both existing proof steps. It requires a separately
  verified source backup and exact operator confirmation, revalidates in
  Rust, and reports the real new encrypted destination file without enabling
  general Minglefield installation or local Host activation. Source and
  backup are preserved; stale edits, mismatched backups, hardlink aliases,
  missing confirmation and preexisting target names are denied. Rust core
  and frontend/Tauri CI evidence are separate from any later manual
  GUI/portable testbuild acceptance. See
  [operational SQLCipher runtime notes](../../installer/OPERATIONAL-SQLCIPHER-RUNTIME.md).
  **Next gate:** confirm all OS core/Tauri checks, then request exactly one
  portable M2.06 Alpha testbuild through the existing explicit marker.
  Human tests must verify real selected-path output, denial/error UI and
  no automatic Host/application activation before calling the gate accepted.
- **Full M2.06 acceptance:** complete native handle-relative publication,
  durability and relevant security boundaries for all supported OSs,
  plus necessary authorization/recovery gates. The testbuild does not
  imply full M2.06 closure or permit a general release. Only the separate
  execution API may report a created destination; the existing rehearsal
  flags must remain false and truthful.
- **Packaging:** one expressly requested portable three-OS testbuild when
  the controlled Alpha gate passes; further release/repair builds only
  after a documented reason and the stronger acceptance gates.

### M2.07 — Crash recovery and rollback

**M2.07 operation receipt v1 — test-scoped implementation (2026-11-06):**
The installer core now contains `recovery_receipt.rs`, a bounded,
**non-authorizing** versioned recovery receipt contract. A randomized
128-bit operation correlation ID identifies the candidate receipt;
SHA-256 fingerprints bind the source file, separate backup, exact chosen
destination path, encrypted file bytes, staged typed corrections and
chosen registered schema-object names. No plaintext row values, DB keys,
login credentials or capability tokens are serialized. A new receipt is
created only with create-if-absent semantics and flushed using
`File::sync_all`; a reused operation ID, malformed/missing/extra
fields, foreign filename, changed file, changed schema selection,
mismatching backup, plaintext copy and hard-linked backup are denied.
The reader reports `Missing`, `Matched` or `Unverified`, never an
instruction to retry, delete or deploy. A matching receipt proves
**byte consistency, not authenticated provenance or operator approval**.

The new test path creates a **real SQLCipher target** using the
existing verified export, records the fixture digest, and launches
a **separate test process** to reopen both the persisted receipt and
the SQLCipher destination without inheriting the writer's memory.
This complements the previous real-process termination checkpoints.
[Ubuntu Rust checks](https://github.com/daresan/Minglefield/actions/runs/42273342933)
passed all 119 regular core tests, including the separate reader.
[Windows/macOS native checks](https://github.com/daresan/Minglefield/actions/runs/42273342890)
also exercise the same tests.

**Not yet operationally wired:** This initial receipt is a
**fixture-only** capability and does not write sidecars from the
regular Tauri/CLI migration command. It currently caps fixture
file fingerprints at 64 MiB and hashes them in memory; larger real
databases require a streaming verifier. It does **not** prove
exclusive trustworthy process ownership, authenticated record origin,
directory-entry crash durability, safe adversarial path resolution,
or privacy-safe production ACLs on every OS. A raw data-dependent
hash of corrections is local diagnostic metadata, not a substitute
for confidential or keyed commitments. These boundaries must be
resolved when integrating the receipt with the real publish operation,
including recording it **before** final-file creation and verifying
the state in a later process after interruption. M2.07 remains OPEN;
no automatic retry/cleanup/rollback or portable build is authorized.

**M2.06 controlled Alpha acceptance evidence (2026-11-06):**
Owner confirmed the portable Windows GUI from
[run 42164863176](https://github.com/daresan/Minglefield/actions/runs/42164863176)
created the selected SQLCipher destination and preserved one staged value
change. Installer output: `destinationCreated=true`,
`encryptedDestinationVerified=true`, `backupVerified=true`,
27 tables, 143 rows, 58 original schema entries and cleaned staging.
The build's Windows, Ubuntu and macOS package jobs succeeded.
This accepts the **bounded experimental database-copy test**, not full
durable M2.06 publication or installed application behavior. The owner's
full-schema preview also revealed **59 registered / 58 source objects**:
the sole missing `uq_game_install_one_active_project` index is
a **possible older-schema compatibility difference**, not a lost
SQLCipher export object or an automatic security finding. The generic
M2 missing-schema workflow now offers none, individual objects or all
missing registered DDL objects for the **new isolated encrypted copy**
only, defaults to none, and uses an all-or-nothing schema transaction.
If a selected constraint conflicts with existing data, it is rejected
without altering the source, backup or publishing a target. A subset
can still be incompatible with the later application runtime, which
requires its own complete schema check. No individual index-specific
approval or repair branch is permitted.

**M2.07 first development slice (read-only, not yet GUI acceptance):**
Classify a candidate interrupted encrypted-copy target as absent,
present/structurally matching the verified source plus allowed staged
values, or present/unverified. An incorrect key, plaintext copy,
occupied unrelated file or changed expected corrections must never
become a verified encrypted copy. **No automatic retry, rollback,
delete, overwrite, Host authorization or reinstallation** is implied
by this inspection. Run T1–T3 with portable packaging disabled.
Provenance-bound journal records, durable directory updates and
interruption fault injection remain mandatory subsequent M2.07 work.

**M2.07 deterministic interruption checkpoints — implemented and T2-verified
(2026-11-06; commit `5e8e791b65f1be3ce4347d51ff70324e512a979f`):**
The existing core's staging and final-name publication path now exposes
private, non-user-configurable checkpoint callbacks. Ordinary production
callers invoke only the no-op wrapper; unit tests inject one controlled
failure at each of five boundaries: before staging, after SQLCipher export,
before exclusive final-name creation, immediately after final-name creation
and during final-ciphertext verification. Tests additionally cover one
reviewed-edit scenario interrupted after publication. After the
**caught synthetic error** they invoke the independent read-only
recovery classifier again. Expected outcome: absent destination before
publication; intact, inspectable encrypted destination after publication;
original source bytes and unrelated occupied files preserved; no
automatic deletion or retry; no residual staging directories following
RAII cleanup. The edit-aware recovery classifies the correctly edited
file as matching, but rejects interpreting it as an unedited copy.

**Actual confirmed CI:** [Ubuntu Rust](https://github.com/daresan/Minglefield/actions/runs/42246330621)
and [Windows/macOS native security](https://github.com/daresan/Minglefield/actions/runs/42246330676)
(all successful). **These are caught, deterministic errors, not abrupt
process termination, power-loss durability, a persistent operation journal,
or user-facing recovery/rollback.** Those remain open before M2.07 and
full M2.06 acceptance. No new portable artifact was requested.

**M2.07 actual process-exit fixture — implemented (commit
`bd79683145152b2ed6b2674b4594e384bbe1794b`):**
A separate instance of the existing Rust **test binary** executes the
unchanged SQLCipher staging/publication path and calls
`std::process::exit(77)` at each of the five private checkpoints.
This is **not** a caught error: no Rust destructor or `Drop` cleanup
runs in the worker. The parent test asserts the exact exit code,
unchanged source bytes and unrelated sentinel, and inspects the
destination via the existing read-only recovery function after the
worker is gone. Before final-name publication the target is absent;
after publication the target reopens with the correct key, rejects
a wrong key, and matches the source snapshot. Real leftover private
staging is observed after process termination; production does
**not** sweep or delete it. Only the parent test deletes its own
entire isolated temporary fixture directory after verification.
No production execution API or GUI fault trigger is introduced.

**Evidence:** [Ubuntu Rust CI](https://github.com/daresan/Minglefield/actions/runs/42264191700)
and [Windows/macOS native security CI](https://github.com/daresan/Minglefield/actions/runs/42264192011).
These tests exercise deliberate process termination with
`std::process::exit`, **not** `SIGKILL`, `TerminateProcess`, system
crash or power removal. They do not prove directory-entry durability,
restore provenance, or authorize automatic retry/rollback. Follow-on
gates remain a nonsecret, verified operation receipt bound to the
actual source/backup/destination/selected edits and DDL; explicit
exclusive ownership and idempotency; durable file and directory
flush behavior; separate process-restart inspection; and
non-destructive owner-approved recovery decisions. Do not promote a
matching SQLCipher file to successful installation solely from its
contents.

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
