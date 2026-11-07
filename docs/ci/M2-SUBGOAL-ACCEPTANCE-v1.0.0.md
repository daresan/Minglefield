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

### M2.07 — Crash recovery and rollback (full automation deferred)

**Binding owner reprioritization, 2026-11-07:** The original database
and separately verified backup are preserved by the controlled Alpha copy,
and a failure is recoverable for the **current Alpha use case** by repeating
the existing consented migration on a fresh, unused target filename. The
previous target/receipt is never automatically deleted, overwritten or
reused. The existing M2.07 read-only diagnostic and tests remain available
**optionally**, not as an additional check that must pass before a new
destination is selected. Do not extend M2.07 journal/rollback,
handle-relative durability, or power-loss fixtures as a development
dependency of M2.08–M2.11. These stronger recovery guarantees stay open
for later update/repair/general-release scope. The immediate work resumes
at **M2.08 authenticated one-time local Host setup**, followed by actual
Minglefield installation and operational launch. Source/backup preservation,
exclusive target creation and first-run authorization are never waived.


**M2.07 credential-free restart triage (post-testbuild, 2026-11-06):**
The existing Tauri read-only recovery command now has **two explicit GUI
entrypoints**, with no new filesystem writer or Host authorization:
a preliminary, destination-path-only inspection, and the original full
source/backup/SQLCipher comparison. The lightweight path sends empty
source/backup/password fields and no staged corrections or schema selections;
the existing core `inspect_interrupted_encrypted_copy` can then
distinguish no receipt, occupied unrecorded destination, and a reserved
receipt without a final destination without decrypting any database.
Any present encrypted destination needing original source/backup/key
validation is merely **manual review required** in the preliminary mode:
a positive ciphertext-equivalence claim is forbidden there.
The full mode still requires the existing passwords, matching source/backup,
staged corrections and registered DDL selection. Neither mode can retry,
delete, roll back, install or claim a Host. Concurrent button invocation,
stale request responses and forged backend capability flags fail closed
in the frontend; this is not OS-level path-race protection.

**Verified focused acceptance:**
[Ubuntu frontend run 42307683340](https://github.com/daresan/Minglefield/actions/runs/42307683340)
for commit `5d901b50c3d5092778631fb7097c76c176f74cd7`;
[Ubuntu frontend run 42308032024](https://github.com/daresan/Minglefield/actions/runs/42308032024)
for commit `2ac8306df0e71ae7ac0a5d71f416284dd003f69b`
(including a static GUI button/command wiring check, 85/85 Node tests and
a successful frontend build). These builds do **not** produce native packages.
The existing successful portable M2.07 artifacts
[run 42303513385](https://github.com/daresan/Minglefield/actions/runs/42303513385)
precede this additional GUI behavior and do not constitute its manual acceptance.
No further portable milestone build is requested by these technical commits.

**Three-OS Rust restart-triage cross-check (2026-11-06, no additional
portable package):** The existing actual-file recovery fixtures now also
call `inspect_interrupted_encrypted_copy` with **empty source and backup
paths and no SQLCipher credentials**, mirroring the new destination-only
GUI mode. They cover an absent receipt and target, an unrecorded occupied
target, a receipt reserved before publication, verified ciphertext that
must be downgraded to manual review without keys, and interrupted
separate-process execution. All responses keep automatic retry, delete
and installation disabled and preserve the source and unrelated files.
Source commit `597bd4e1897fd1120d1a969cf8189a0391ca4282` passed
[Ubuntu installer Rust checks](https://github.com/daresan/Minglefield/actions/runs/42308522803)
and [Windows/macOS native security checks](https://github.com/daresan/Minglefield/actions/runs/42308522721).
Each reported successful `cargo fmt -- --check`, Cargo check/clippy,
Rust tests and the two explicitly invoked Python SQLCipher interoperability
checks. Ubuntu reported 128/128 core tests; Windows reported 125/125 core
tests and 2/2 separately invoked cross-runtime tests. The latest
[Ubuntu frontend check](https://github.com/daresan/Minglefield/actions/runs/42308372006)
for `7fa2771d3417cb8469c084bbde553442a0e50663` passed 85/85 tests
and the Vite build. The frontend now rejects **all** unreviewed response
fields instead of silently accepting unknown permission or metadata flags.
This is a verified read-only partial M2.07 subgoal, **not** an authorized
rollback, a crash-durable native publish protocol or manual GUI acceptance.

**Bounded receipt-reading and CI coverage gate (2026-11-06):**
`recovery_receipt.rs` now rejects nonregular/oversized receipts both before
and after opening, limits the actual read to 2 KiB + 1 byte, compares
open-handle length with read length and pathname metadata, and on Unix
compares native device/inode identities before and after the read.
The additional real-filesystem regression rejects oversized receipt
content, reserved-slot replay and symlink substitution, while preserving
the source and backup. The first Ubuntu build
[42309113767](https://github.com/daresan/Minglefield/actions/runs/42309113767)
failed at compilation because the Rust `Read` and `Write` traits both
provide `by_ref`; commit `070b702bd2eeb6e9d466a19bcbaed7b31cbd6864`
explicitly disambiguated the method and the focused regression then
passed [Ubuntu Installer Rust checks](https://github.com/daresan/Minglefield/actions/runs/42309209078)
(129 core tests plus the two explicit Python SQLCipher interoperability
tests). The native security workflow was corrected in
`3da6c943daeaeb06eaf51f2fb1e5cc8a535c2734` so subsequent changes
to **both** `recovery_receipt.rs` and `integrity.rs` trigger the existing
Windows/macOS matrix. [Native security run 42309252884](https://github.com/daresan/Minglefield/actions/runs/42309252884)
passed on **Windows** (126 core + 2 cross-runtime tests) and **macOS**
(129 core + 2 cross-runtime tests), including formatting, compilation
and Clippy. No new packaging was requested.
These bounded reads reduce a potential memory-exhaustion/TOCTOU exposure,
**not** an absolute pathname-race guarantee; Windows opened-file identity,
native handle-relative final publication and crash durability remain
separate M2.07 security gates. The self-asserted receipt is never an
authorization credential.


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

**Recovery GUI IPC contract hardening (2026-11-06; post-testbuild,
technical-only, no new packaging):** The read-only result validator now
rejects inconsistent status/operation-ID pairs and any unexpected positive
execution, rollback, resume, deletion or Host-provisioning capability claim.
The GUI's restarted-session inspector builds a strictly allowlisted IPC
request from current source/backup/destination, keys, staged corrections
and registered schema choices, without relying on a prior in-memory
migration proof or accidentally transmitting the experimental write consent.
Focused Node tests passed locally (8/8); the complete installer frontend
suite passed (80/80) in [run 42306356318](https://github.com/daresan/Minglefield/actions/runs/42306356318)
for commit `0f5b30860d03ae850dd60f646965e77422cb9f6b`.
The prior request adapter passed [run 42306172740](https://github.com/daresan/Minglefield/actions/runs/42306172740).
A first incremental CI failure (missing operation ID in an existing
test fixture, [run 42304928808](https://github.com/daresan/Minglefield/actions/runs/42304928808))
was fixed and passed in [run 42304963934](https://github.com/daresan/Minglefield/actions/runs/42304963934).
These checks prove only the JavaScript contract, **not** native
handle-relative crash durability, complete rollback or a tested
Windows/macOS desktop experience. The already issued M2.07 three-OS
testbuild [run 42303513385](https://github.com/daresan/Minglefield/actions/runs/42303513385)
completed all three packaging jobs successfully; its binaries precede
these post-build frontend-only changes, and operator acceptance remains
pending. No further portable package is authorized by this record.

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

**Implementation and gate evidence (2026-11-07, portable M2.08
acceptance pending):** `installer/gui/src-tauri/src/alpha_first_run.rs`
has a Tauri-process-local single-use authorization state populated
**only** by the confirmed encrypted-copy operation and by separately
confirmed installation of verified application files. It cannot be
armed from a caller-provided Boolean, path, database password, Host
claim token, or arbitrary frontend status. The native command consumes
this state once, rechecks the new database and installed-file inventory,
and sends the two independent credentials through a private stdin pipe
to the packaged `server/installed_alpha_first_run.py` worker. That worker
uses the existing `HostCommitPolicy.provision_first_run_local_host_admin_trusted`
atomic account/Host transaction, not a public gateway route or second
identity backend. The GUI displays an editable default `mingleadmin`
and separate confirmation/explicit consent. The original database and
independent backup remain unchanged. Repeated activation, existing
identities and pre-owned Hosts are rejected. The current local Host ID
has an installation-scoped `local.<operation-id>` value, not a global
administrator role. **Current first-run response has
`applicationLaunchEnabled=false`**: native launching is the subsequent
M2.09–M2.11 path, not a completed capability here.

Focused source/runtime checks: [Ubuntu installer Rust CI
42320729192](https://github.com/daresan/Minglefield/actions/runs/42320729192),
[Windows/macOS native SQLCipher/Host CI
42320729241](https://github.com/daresan/Minglefield/actions/runs/42320729241),
and [MAP/Python conformance
42319929885](https://github.com/daresan/Minglefield/actions/runs/42319929885),
all successful. [Frontend checks
42320390401](https://github.com/daresan/Minglefield/actions/runs/42320390401)
passed the first-run GUI validations. After the exact rustfmt fixes,
[Tauri native full Windows/Linux/macOS gate
42320859781](https://github.com/daresan/Minglefield/actions/runs/42320859781)
passed on all three operating systems at
`dda30f7a27ca06508beee8bf7622b0b6d55298b0`.
Actual portable packaging and human GUI acceptance are **not** implied
by these checks. General repair/release lifecycle and fresh empty-DB
creation remain separate future requirements; M2.07 full crash recovery
stays explicitly deferred at the operator's direction.

### Current M2.08 artifact repair and separate acceptance evidence (2026-11-07)

After the corrective CI listed below, portable build [42329947124](https://github.com/daresan/Minglefield/actions/runs/42329947124) was **again rejected on Shadow**. The previous artifact review reports the uploaded Windows ZIP omits two hidden, zero-byte files declared in its pinned inventory: `managed-alpha/runtime/python/Lib/site-packages/setuptools/_vendor/.lock` and `managed-alpha/runtime/python/Scripts/.empty`. The workflow's Windows `upload-artifact` step has no explicit include-hidden-files setting. A successful build-directory inventory is insufficient: a corrected M2.08 repair must verify the **actual uploaded/downloaded and re-extracted Windows payload**, including hidden/empty members, against the build-bound inventory (size and SHA-256), show an actionable mismatch path and preserve fail-closed integrity. Run MDCI T1–T3 before the next **single permitted failed-build repair** acceptance request, then require the maintainer's independent Shadow retest. This is a documented review finding, **not** a claim that the defect is fixed or that the previous failure was user error.

Keep M2.08 narrow: verified encrypted destination, separately installed application files and local first-Host creation **only for genuinely new identities/Hosts**. A previously provisioned imported database is **not** sent through `provision_first_run_local_host_admin_trusted`: preserve its `mingleadmin` and other users, password verifiers, `alpha_sessions` token hashes with existing expiry/revocation, existing Host IDs and local/remote owner/grant rows. Confirm existing password login still works and creates ordinary sessions; previously issued bearer tokens work only when the client still has them and they are unexpired/unrevoked. Never claim token hashes can reconstruct token secrets or automatically renew expired sessions. The currently implemented first-run creation worker rejects pre-existing IDs; this is a wrong-path integration defect for imported databases, not grounds to re-provision them or invent a new milestone. Reuse recorded `host_id`, not `local.<migration-operation-id>`. Reject only an attempted **new contradictory ownership change** while allowing otherwise valid import/startup. Remote Host acquisition and client-only mode are not installer acceptance tests; stored remote records must be preserved.

### M2.08 — First-run `mingleadmin` and local Host binding

**Rejected manual operator acceptance (2026-11-07):** The former portable M2.08 build succeeded on three packaging runners but failed on Shadow. Real users were forced through redundant test copies, an existing newly copied DB blocked application installation, absent install/data parents were rejected, and an attempted one-time Host action exhausted the entire GUI session. The selected missing-schema addition was also rejected; without the original diagnostic its exact cause is not proven. The remediation explicitly distinguishes *optional* in-memory/temporary SQLCipher diagnostics from mandatory native execution checks, preserves the source and separate backup, allows an application to be installed beside an existing new DB, creates missing parent folders only on consented writes, resolves bundled managed-alpha resources (including the Windows sibling folder), and maintains one-time local Host authority **per operation** with fresh-target retries in the same process. Wrong SQLCipher password must not consume the permit. CI and renewed operator acceptance are both required. Status: **FAILED / awaiting re-test**.

**Completed focused corrective CI (2026-11-07):** [Ubuntu installer Rust 42329523542](https://github.com/daresan/Minglefield/actions/runs/42329523542) **success**, [Windows/macOS native security 42329523531](https://github.com/daresan/Minglefield/actions/runs/42329523531) **both success**, for implementation `d8cbf16d670cf09289867e9e575cc41480941db5`. The new real encrypted-copy integration fixture covers a missing registered table with its implicit index, an existing extension row, creation of a previously absent nested data directory and preservation of original source and independent backup. [Tauri GUI native 42328609249](https://github.com/daresan/Minglefield/actions/runs/42328609249) passed for the local-first-run and application-dir changes; [GUI frontend 42329309473](https://github.com/daresan/Minglefield/actions/runs/42329309473) passed for the simplified UI and collapsed optional diagnostics. [AGENTS 42329523596](https://github.com/daresan/Minglefield/actions/runs/42329523596) passed. **These are CI results, not manual acceptance.** The prior portable build remains rejected; the development policy allows one corrected testbuild after the verified fix.



- Require an explicitly authorized, installation-bound, local-only,
  single-use Host activation handshake (no manual local console invite).
- Create only the local user, salted login verifier and approved local Host
  ownership; sign-in password differs from SQLCipher key.
- Reject replay, concurrent double setup, preexisting identity/Host ownership,
  impersonation and remote-Host escalation; roll back partial transactions.
- Verify normal login and host-scoped administration; remote Host control
  requires separate valid grant.
- **Packaging:** one acceptance build after real first-run path is wired.

**Verified executable Alpha runtime slice (2026-11-07; not the native
first-run authorization yet):** Existing `AlphaAuthStore`,
`IntegratedAlphaAdmission`, `HostCommitPolicy` and local-only
`handler_for` can now be started against an existing *real* SQLCipher
database through `server/private_alpha_gateway.py::
create_installed_local_alpha_server`, without the old plaintext
developer startup or console Host-claim token. The private executable
`server/installed_alpha_launch.py` accepts one size-limited, versioned
startup frame on inherited stdin (database path, SQLCipher key and
loopback port); it takes no key on argv/environment or disk and exposes
no initial Host provisioning route. Negative invalid/missing/wrong-key
inputs fail without a plaintext fallback.

**End-to-end evidence:** The source+runtime changes were checked
on [Ubuntu Installer Rust CI 42313263186](https://github.com/daresan/Minglefield/actions/runs/42313263186),
[Windows/macOS Installer native security CI 42313263192](https://github.com/daresan/Minglefield/actions/runs/42313263192),
and [MAP/Python conformance 42313263195](https://github.com/daresan/Minglefield/actions/runs/42313263195)
at source `bebb6d4979e91dac2397fb4b67affc19c398d271` (all successful).
The focused tests run a **real Python subprocess** and real loopback
HTTP login, create exactly one owner-scoped Effect, mock queued Job,
Game project and Host settings through the existing HTTP API, stop
the process, restart it and verify all four persisted in the encrypted
DB. Foreign-Host GET and claim attempts are denied; wrong login and
SQLCipher keys fail independently. The existing imported rows remain.
No independent operator GUI acceptance, actual installed Python runtime
or M2.08 single-use native consent is implied by this test.

**Latest operator evidence — [M2.08 portable build #20](https://github.com/daresan/Minglefield/actions/runs/42342372030), 2026-11-07:** All three native packaging jobs passed. The operator clicked Alpha installation on Shadow and confirmed **4,156 verified managed entries** copied into the selected application directory. The previously missing hidden-files error did not recur. **No actual native Minglefield executable was installed**: the destination primarily contains Python modules and a portable Python distribution; only the **file-copy step** has been operator-tested successfully. The `mingleadmin` inputs were unavailable after detecting existing user/Host data, consistent with avoiding unwanted re-provisioning, but a full installed-app login still awaits independent application launch. Do not mark M2.08 end-to-end or complete M2.10 from this file inventory. **Next action:** prove M2.09 direct application launch and M2.10 real OS application binaries before repackaging the Setup Manager; no new milestone is introduced.

### M2.09 — Encrypted operational runtime and independent application shell start

- Launch the real installed Alpha against its selected encrypted SQLCipher DB using an **application-owned** invocation independent of both Setup Manager and installer CLI. Reuse `installed_alpha_launch.py` internally; no end user must call Python or operate the interpreter. The M2.09 development shell start is a testable stepping stone to the actual native M2.10 application entrypoint, **not** the final desktop deliverable. At the **public CLI boundary**, allow the administrator's Bee-style password sources (literal argument, password file, explicit config, environment, prompt, stdin); **no unintended secret output** in application-generated logs, receipts, errors or default configs. Internally the existing private stdin gateway frame may be retained; opening a DB is not migration/re-encryption.
- Verify ordinary login/session, Hosts, Effects, Jobs and Game storage survive
  process restart and remain tenant/Host-scoped.
- Missing driver, missing key or wrong key must fail closed without silently
  falling back to plaintext SQLite or **unintentionally** retaining the key
  in logs or **generated** config. Administrator-authored plaintext config
  is a permitted, explicitly chosen input source.
- **Packaging:** combine with M2.10 unless distinct user-visible UX requires
  a separately accepted build.

**First tangible application-source artifact (2026-11-07):**
`installer/scripts/build_alpha_application_payload.py` now builds one
deterministic non-overwriting ZIP containing the exact audited
`installed_alpha_launch.py` Python module dependency closure. Its own
JSON manifest declares SHA-256 and size for every included module,
the actual Alpha entrypoint and unresolved external/dynamic imports.
The companion verifier rejects extra, tampered, missing, oversized,
nonregular source or unreviewed entries. Tests assemble the real Alpha
source package, extract it to a **separate temporary directory** and
run the included launcher with isolated `python -I -B`; a missing
request fails through the actual packaged entrypoint, not an import
of the source checkout. The test also requires mandatory runtime
gateway/auth/Host modules to be in the archive.

**Focused CI:** initial [Installer Rust run 42313764062](https://github.com/daresan/Minglefield/actions/runs/42313764062)
identified missing-module false acceptance in the builder test; fixed
in `4188346c16a493bca109936f21dfe67dbd007bf1`.
[Installer Rust checks 42313949256](https://github.com/daresan/Minglefield/actions/runs/42313949256)
then passed the offline payload tests and existing Rust/Python suites.
**Not yet a distributable or launchable clean-machine installer:**
the application ZIP does **not** include a pinned managed Python
interpreter, SQLCipher binary driver/wheels, release signing, a
trusted publisher manifest, or the installation-bound native
consent mechanism. All those are still required before any user
receives an installable application. The ZIP explicitly labels
`pythonRuntimeIncluded=false`, `runtimeDependencyLockVerified=false`,
`publisherSignatureVerified=false`; do not repurpose its checksum
manifest as publisher trust or request packaging prematurely.

### M2.10 — Managed Python runtime and Minglefield application payload

- Support a **new encrypted SQLCipher DB with no prior source**, besides migration of an existing DB. Both must be compatible with the same independently callable application shell launcher and local first-Host setup; no additional Remote Host claim acceptance.
- Build the **Minglefield application itself independently of the Setup Manager** for Windows, Linux and macOS: direct OS start via the appropriate native `Minglefield.exe`, Linux executable/app distribution and `Minglefield.app`. Bundle the verified Python/SQLCipher engine internally if it remains the chosen implementation; **a Python file tree with an interpreter alone is not a native application deliverable**.
- On clean target OS environments, prove native launch, DB selection/unlock, existing-account authentication and persisted Host/Effects/Jobs/Games across restart; no Git, Conda, developer Python, shell scripts or installer process is allowed as a runtime requirement. Verify inventory/runtime closure, release integrity and negative wrong-key/removed-file cases.
- Close or remove the portable Setup Manager **before** the direct application launch test; app executable, user data and credentials remain usable. No hardcoded machine paths or installer-issued Host rights.
- **Packaging:** one three-OS acceptance build.

### M2.11 — Standard, Advanced and headless parity

- **First prebuilt Alpha acceptance:** GUI and installer CLI consume the independently built/tested official OS package, verify and install it into the selected program directory, migrate/create the separate encrypted DB and optionally launch the same native application executable. **This is not a prohibition on later builds**: the required subsequent source-build path uses official or explicitly user-selected compatible fork build definitions, fetches declared build/application dependencies, builds the native executable and installs it. In both modes, Minglefield must remain startable when the Setup Manager is deleted.
- Distinguish the **installer CLI** (formerly `PLAN ONLY` for every action; now with one real `--install-alpha-files` action) from the application-owned M2.09/M2.10 start path. The CLI and GUI now share `installer-core::managed_alpha_install` for verified **application-file copying**; all other CLI operations remain read-only or unimplemented. Verify migration/new-db, separate login secrets, Host authorization, application launch and silent/GUI parity independently; no import can fabricate credentials or Host ownership.
- Standard: safe user-scoped defaults, suitable data directory and clear
  installation completion.
- Advanced: selected destination/data paths, existing-install detection,
  conflict prompts and optional component consent.
- CLI: `--silent --defaults` shares validation/engine; no implicit Host claim,
  credential generation, optional runtime consent or destructive action.
- Negative: inaccessible destination, interrupted install and invalid config
  yield safe errors and deterministic no-mutation behavior.
- **Packaging:** one three-OS acceptance build.

**DB CLI implementation (2026-11-07; acceptance pending):** The CLI now calls the same `installer-core` SQLCipher snapshot inspection and verified encrypted-copy publication used by the GUI. Test direct CLI/password-file/version-3 config/environment/private-stdin inputs; fail on conflicting input sources; verify an actual encrypted DB, a separate original/backup and new-key copy; preserve existing user/Host IDs, do not overwrite an occupied destination; expose a non-secret copy recovery operation ID **without** reusing it as an actual Host identity. Verify the GUI's version-3 preview accepts the same schema. The new DB CLI actions are not account provisioning, an OS executable build, or silent-install acceptance; do not call M2.11 complete. Native CI results for these new files are not yet recorded.

**Fresh SQLCipher creation slice (2026-11-07, implementation pending CI acceptance):** The explicit `--create-new-encrypted-db` operation requires a non-existing target and the exact new-db confirmation; it uses the same `installer-core` key validator and SQLCipher engine, independently reopens/verifies ciphertext, never accepts a legacy source or existing ownership as an implicit first-run approval, and never creates users/Host IDs/grants. Check correct key, wrong key, fresh empty schema, existing-path refusal, and original bytes unchanged on collision. The parent directory must already exist; future silent orchestration must handle selected directory creation without losing the exclusive target rule. Do not conflate DB-file creation with Host administration or full M2.11 acceptance.

**Future mandatory source-build acceptance, after prebuilt Alpha delivery (no new immediate M2.11 blocking gate):** Demonstrate an official-repository build and a separately consented compatible fork build using each source's versioned OS build template, documented dependency acquisition, a native OS executable artifact, independent launch, and safe failure for a missing/invalid template, incompatible dependencies or a rejected source. The developer of a custom fork is responsible for making its template compatible. Same backend operations must be callable from shell/CLI and GUI, with no arbitrary code execution on mere checkout discovery. This future capability must not be silently reclassified as an optional extra.

**Binding M2.11 CLI/GUI and silent-install credential acceptance (approved 2026-11-07; not implemented):**
- A single versioned schema and named flags cover **every** functional installer parameter and its corresponding GUI control, including paths, source/build mode, dependency acquisition, DB migration/new creation, optional app approvals, local account/Host setup and launch. `--silent` and interactive CLI must execute the same operation core; silent needs no terminal prompt when all necessary values/consents are provided.
- For SQLCipher DB unlock accept **all** approved Bee-style channels: literal `--db-password VALUE`, `--db-password-file PATH`, explicit `db_password` in an administrator-authored config, `MINGLEFIELD_DB_PASSWORD`, interactive password prompt (confirmation **only for creation/change**) and private `--secrets-stdin` input. Support correspondingly named sources for separate account-password operations. Proposed spellings become canonical once CLI contract is implemented. Document deterministic source precedence and reject explicit contradictory simultaneous values without printing them.
- Verify same parameter meaning/result via CLI, config, GUI and silent mode. Tests exercise each secret source against a disposable **encrypted** DB, successful auth with an existing independent login, wrong-key failure, missing required silent input and no surprise Host ownership mutation. No test may use a real user DB or emit secrets in CI output.
- Administrator-managed config files are permitted to contain plain passwords and are **not rejected solely for using plaintext**. Automatically generated defaults, result plans, logs, error strings, telemetry or CI artifacts must not leak secrets. A non-blocking permission warning is acceptable. Files accidentally published as a repository or public artifact are considered compromised, **not** legitimate Minglefield DB distribution.
- Retain private stdin between native launcher and embedded SQLCipher worker as an internal implementation detail, **not** an exclusion of `--db-password` or other public CLI options. Mere DB path/key possession is not consent to overwrite, re-provision, claim a remote Host or bypass normal Minglefield account authorization.
- **Do not call M2.11 complete** while any of these input/CLI/GUI parity cases are missing; the existing `alpha_application_shell.py` prompts interactively and `installer-cli` is currently PLAN ONLY. This is a **target contract** and no implementation is claimed here.

**Focused implementation evidence (2026-11-07, partial only):** [Rust/Ubuntu CI #589](https://github.com/daresan/Minglefield/actions/runs/42350729117) passed format, locked build, Clippy, core/CLI tests and packaged runtime integration. [Tauri GUI/Ubuntu #41](https://github.com/daresan/Minglefield/actions/runs/42351149124) passed after reusing the shared core and preserving first-run verification. Regression tests create disposable manifests, copy real declared files, reject wrong/tampered inventory, reject missing consent and prevent a second install to an occupied target. This does **not** prove a complete native Minglefield application or user-accepted installation. The [CLI usage note](../../installer/CLI-USAGE.md) documents this explicitly.

### M2.12 — Optional Conda and ComfyUI integration

- Git, GitHub CLI, optional Conda/Miniforge and ComfyUI: detect/reuse first; with separate explicit consent, execute official documented OS-specific installer script/package-manager flow only after appropriate release/source verification. Without a supported safe automated installation path, open the official provider page in the default OS browser for a manual step. Never bundle complete optional third-party applications into the Setup Manager (except components actually needed as Minglefield build/runtime dependencies), auto-install ComfyUI models/custom nodes, or overwrite existing runtime data. Runtime settings remain Host-owned.
- Test offline/unsupported OS handling, cancellation, no permission escalation without consent, and display of actionable official-source fallback.

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
  compilation of the GUI bundle. Existing `mingleadmin` and valid local/remote Host grants must survive migrated-data installation without replacement; active Remote Host claims are outside the installer acceptance scope.
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
