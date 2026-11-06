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

**M2.07 read-only operator recovery triage — implemented in the
shared core and Tauri GUI; manual portable acceptance pending:**
The installer can now inspect a user-selected interrupted Alpha
database-copy attempt after Setup Manager restarts, using the saved
destination-specific receipt and the source/backup keys, staged edits
and registered schema-object choices. It reports one of five
read-only states: no recorded operation, unrecorded occupied target,
reservation without final target, published ciphertext matching
the receipt and complete corrected SQLCipher snapshot, or
unverifiable/manual review required. Mismatched source/backup,
corrupted receipts, wrong ciphertext key and changed schema
selection all fail closed. The existing Tauri Review page exposes a
dedicated **Recovery-Zustand prüfen (nur lesen)** button; it does
not depend on a stale in-memory rehearsal or invoke any filesystem
writer. The frontend independently validates the returned operation
ID and refuses permission-bearing flags.

**All five status classes are informational only.** The command
always returns `automaticRetryPermitted=false`,
`automaticDeletePermitted=false` and
`installationEnabled=false`. A matching receipt is a checksum-based
consistency signal and remains unauthenticated evidence, NOT proof
of provenance or owner authorization. There is no automatic
rollback, restart, deletion, Host claim or production installation.
This command is subject to Rust cross-platform tests, Tauri command
compilation/tests and frontend unit/build checks, with distinct
CI statuses tracked separately. A subsequent **explicitly approved**
portable GUI milestone build is required for human acceptance;
ordinary commits do not trigger any packaging.

**M2.07 receipt v1: integrated pre-publication operation reservation
(2026-11-06, controlled Alpha path; full milestone still OPEN).**
The first fixture-only recovery receipt was tested on all three platforms
([Ubuntu](https://github.com/daresan/Minglefield/actions/runs/42273342933),
[Windows/macOS](https://github.com/daresan/Minglefield/actions/runs/42273342890)).
It is now also connected to the explicitly approved, backup-checked,
normally compiled SQLCipher final-copy path. After the ciphertext stage
is fully verified and flushed, **before exclusive final-name publication**,
the Rust core records a new 128-bit random operation ID and SHA-256
fingerprints for the source file, distinct backup, canonical destination
pathname, staged ciphertext, typed corrections and selected registered
schema additions. No source data rows, DB keys, auth tokens or raw paths
are serialized. The backing file itself is never modified.

**Exclusive/idempotency rule:** A deterministic
`minglefield-target-<destination-path-sha256>.receipt` sidecar in the
destination directory is created using `create_new`; if that
destination has any existing receipt, the new operation is rejected
even when the intended ciphertext filename is absent. The original
receipt is never deleted, silently replaced or reused. The receipt
is read back against the verified staged ciphertext before final hard
link; after publication the **final encrypted filename** is checked
against that same record. The regular Tauri Alpha result includes
`recoveryOperationId`, `recoveryReceiptDirectorySynced` and
`destinationDirectorySynced` without implying that either metadata
flag authorizes recovery, installation or Host activation.

**Streaming integrity:** Existing dependency-free SHA-256 is now
incremental with 64-KiB chunks. File fingerprints no longer require
loading a whole user DB into RAM or enforcing the original 64-MiB
fixture cap; streaming known-vector/boundary and 64-MiB-plus tests
cover the digest. Both source and backup hashes are recorded
independently: a logically equivalent SQLite backup is not required
to have identical physical bytes (higher-level SQLCipher/SQLite
verification still checks logical equivalence before copying).

**Crash/order evidence:** The existing separate-process fixture
now deliberately calls `std::process::exit(77)` immediately after
record reservation and immediately after final-name publication.
Following a real process termination, a separate test process
checks the reserved receipt and surviving staged or final encrypted
file. A receipt with an absent final target means **reserved but
not published**, not a free/retryable destination. Existing targets,
source bytes and independently verified backups remain untouched;
automated retry/delete is always false. Existing controlled-error,
wrong-key, tamper, collision and source-preservation cases remain
mandatory. No new portable package is triggered.

**Current evidence:** [Ubuntu core](https://github.com/daresan/Minglefield/actions/runs/42291412639)
and [native Windows/macOS](https://github.com/daresan/Minglefield/actions/runs/42291412669).
The new GUI action has not yet been manually accepted in a portable
build carrying this receipt integration. The result is an **Alpha
development gate**, not complete M2.07 recovery acceptance.

**Remaining release boundaries:** Sidecar digests and a random ID
are *not* authenticated provenance or an authorization token. The
record is file-synced and its parent directory explicitly synced
where supported in the current Unix implementation. On Windows
directory-entry crash durability is **unproven**, and the result
flags truthfully report `false`. NTFS/APFS/ext4 crash consistency,
malicious ancestor/path replacement, native owner-bound/ACL-secured
receipt creation, crash-recovery journal state transitions and
power-loss tests still need separate evidence. A failed operation
can leave a receipt and possibly a verified ciphertext file; the
installer must report the state and require a human decision rather
than automatically cleaning up or resuming. **Do not close M2.07,
enable silent recovery, or request another portable build without
an approved milestone gate.**

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
