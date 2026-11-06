# Operational SQLCipher database access — integration gate

**Status:** Code and cross-platform real-driver regression tests added to the
existing Alpha storage boundary. This is *not* authorization to publish the
final encrypted destination or a claim that the installed application can
already bootstrap and unlock it.

## Motivation

The existing Tauri installer can produce and independently verify an encrypted
SQLCipher copy, but the current local Alpha gateway historically opens its
database through Python's ordinary `sqlite3`. The ability to export
ciphertext is not the same as the ability to operate Minglefield afterward.

The new `server/alpha_sqlcipher_runtime.py` provides a single runtime
connection decision at the Alpha store's established `_Transaction`
boundary, used by authentication and Host/Effects/Jobs/Game persistence.
It deliberately does not add a new storage service, configuration file,
launcher flag, or duplicate database.

## Modes and trust boundaries

- **Existing local Alpha developer mode:** `AlphaAuthStore(path)` retains
  the previous plaintext SQLite behavior and development fixtures. It
  refuses to interpret an encrypted file using plaintext sqlite3. This
  existing mode is not the installed operational Minglefield database.
- **Encrypted operational mode:** `AlphaAuthStore(path,
  sqlcipher_key_provider=callable)`. The callable is a future local,
  authenticated first-run/unlock boundary returning the key in memory.
  The prototype does not persist it, read environment variables, or
  accept it through command-line flags. A missing provider cannot
  unlock an encrypted DB.
- Encrypted mode requires an **existing** non-symlink regular database
  file, refuses a plaintext SQLite header, imports `sqlcipher3.dbapi2`
  only when needed, applies `PRAGMA key` as the first database operation
  (with correctly quoted passphrase), verifies a real
  `PRAGMA cipher_version` and a real `sqlite_schema` query, and
  enables foreign key checks for subsequent application writes.
  An absent SQLCipher driver or wrong key fails closed, closes the
  connection and never retries using plaintext sqlite3.
- The existing Host policy handles uniqueness conflicts with the
  selected driver's `IntegrityError`; this avoids a compatibility bug
  where a SQLCipher unique-key error would differ from the builtin
  sqlite3 exception type.

## Cross-platform verification

The existing Windows/Linux/macOS Python conformance workflow
`.github/workflows/game-installation-security.yml` installs a pinned
`sqlcipher3==0.6.4` **binary wheel** on Python 3.11 for Windows, Linux
and macOS, then runs actual encrypted connection/reopen, wrong-key,
password quoting, live Alpha authentication and Host project uniqueness
tests, followed by the existing Alpha/Host regression suites. The
vendor's driver must be included as a verified, pinned platform
dependency in the eventual actual application payload. This is a CI
test dependency, not an installer-supplied package yet.

The independent installed runtime still requires: tested installer
distribution of a compatible Python runtime and SQLCipher driver;
an authenticated local GUI key-unlock flow that avoids persistent
plaintext secrets; **cross-implementation** verification that Python
opens the specific SQLCipher file written by the Rust installer;
concurrency/path-identity protections; exclusive/atomic encrypted
target publication and recovery. The existing bootstrap-secret Host
claim boundary must not be bypassed.

No durable migration execution has been enabled. All previous
source-preservation, original password handling and five database
review areas remain intact.

The runtime test file is `tests/conformance/test_game_integration_install_alpha_sqlcipher_runtime.py`.
The existing conformance test matcher runs it without adding another workflow.
The package in `requirements-ci.txt` is CI-only, not yet a packaged Minglefield runtime dependency.

## First-run identity/password isolation (accepted 2026-11-06)

The SQLCipher key provider is strictly a **local database unlock**
mechanism, not Minglefield user authentication. The default editable
first login name `mingleadmin` uses its *own* password and scrypt
verifier in `alpha_passwords`. A trusted local first-run flow may
create it without a manual invite, but must obtain distinct user
credentials and explicit, single-use owner/Host authorization before
writing the verified encrypted destination. No user receives universal
Host privileges. Imported user/Host conflicts and remote Host grants
must never be silently rewritten. See the approved phase contract
`docs/MINGLEFIELD-INSTALLER-AND-ONBOARDING-PHASE.md`.

A storage-layer account/Host transaction, if developed independently
for tests, must remain inaccessible from the existing HTTP gateway
until the authorized local-only bootstrap/identity proof is complete.
This operational-runtime milestone does **not** enable durable
migration publication or automatic Host claims.



## Implemented storage primitive for initial Host account (2026-11-06)

The existing `HostCommitPolicy` now contains
`provision_first_run_local_host_admin_trusted(local_host_id, login_password,
login_user_id="mingleadmin")`. It is **trusted offline database plumbing,
not a newly authorized HTTP endpoint or runnable installation flow**.

The function requires the existing `AlphaAuthStore` to be connected
through the encrypted-only SQLCipher key-provider path, refuses an
unencrypted development source, and rejects login passwords identical
to the database key. The login password must satisfy the existing
12–256-character Alpha user-password policy.

Inside the established `BEGIN IMMEDIATE` store transaction, the helper
checks the complete available table inventory for identity references and
Host-ID conflicts (including orphan Host Admin/ownership references).
It then inserts exactly four records into existing tables:

1. `alpha_users`: the chosen ordinary user identity.
2. `alpha_passwords`: independently salted **scrypt verifier**, never
   the login password or the SQLCipher key.
3. `alpha_executor_hosts`: the single locally authorized host.
4. `sec01_host_owners`: ownership for that same host only.

No invitation or active session is created; normal `AlphaAuthStore.login`
works after provisioning. No global administrator or additional remote
Host grants are created. Existing `sec01_host_admins` stays unchanged
because the registered Host owner already has Host-admin authority.

If any of the four writes fails, the whole transaction rolls back.
Repeated calls, preexisting identities, unexpected identity references,
existing Host IDs, bad credentials, and plaintext databases fail closed.

**Evidence:** `tests/conformance/test_first_run_local_host_admin.py`
runs 11 focused tests using real disposable SQLCipher targets in the
Ubuntu Python conformance suite, including transaction failure,
parallel first-run calls, password separation, role isolation and
non-overwriting migrated accounts.

**Outstanding authorization boundary:** this trusted storage method is
not callable from the installer GUI, the HTTP gateway or the public
Host-claim API. The authorized local, single-use installation-bound
handshake must prove the actual Host and intended *new target*, then
invoke it through a trusted process immediately before final encrypted
publication. On-disk original/source preservation and atomic
destination publication remain mandatory. No setup action is
authorized merely by knowing the username, possession of a database
password or a client-controlled boolean. No `migrationEnabled` or
`executionEnabled` flag has changed.


## Installer-produced ciphertext → real Python login/Host integration

The installer now includes an **explicit opt-in integration test** in
`installer/crates/installer-core/src/encrypted_copy_preflight.rs` named
`cross_runtime_sqlcipher_export_python_first_run`. It requires
Python 3.11 and a compatible `sqlcipher3==0.6.4` wheel.
**Focused cross-runtime CI evidence (2026-11-06):** the test remains
`#[ignore]` during the ordinary Rust suite, but `installer-rust.yml`
now explicitly invokes `cargo test -p minglefield-installer-core --locked
cross_runtime_ -- --ignored` after provisioning Python 3.11 and the pinned
CI SQLCipher dependencies. In
[Ubuntu Installer Rust checks #533](https://github.com/daresan/Minglefield/actions/runs/42300421292),
both `cross_runtime_published_fixture_python_open` and
`cross_runtime_sqlcipher_export_python_first_run` passed (2/2) against
the actual Rust-produced encrypted files and the Python application
runtime. This is a single-platform CI acceptance for that explicit
integration path, **not** first-run authorization, operator GUI acceptance,
three-OS Python runtime certification, or complete M2.08.

The test reuses the real Rust `sqlcipher_export` operation to create a
randomly staged SQLCipher database, then starts a real Python subprocess
using the existing `AlphaAuthStore` / `HostCommitPolicy` architecture.
It transmits the temporary database path and **both separate** in-memory
test passwords through a private stdin pipe, not argv, environment,
HTTP, logs, or persisted configuration. Python must:

- decrypt the actual Rust-written file and verify preexisting fixture values;
- reject a wrong SQLCipher key;
- create `mingleadmin`, its separately salted password verifier, and
  one local Host owner using the existing encrypted-only trusted transaction;
- reject replay, create no invitation, authenticate via the ordinary
  `AlphaAuthStore.login` path, reject login using the database key, and
  deny authority on an unrelated Host.

After Python exits, Rust reopens the **same file** with its original
SQLCipher key, verifies the inserted owner and original BLOB, performs
an integrity check, and removes the entire private staging directory.
No real source database, final destination or permanent operational
application data is modified by this test.

This test validates the **cross-language ciphertext and application
storage compatibility gate**, not yet installer authorization, native
destination-creation/publishing semantics, production release packaging,
key-unlock UX or lifecycle recovery. It runs only inside CI / an
explicit developer invocation. The normal app and setup-manager
`executionEnabled` flags remain false.

## Atomic encrypted stage-link rehearsal (next publication safety gate)

The existing `rehearse_encrypted_test_copy` does not yet publish a
permanent destination. It now additionally tests the platform's
**exclusive native hard-link promotion** of a complete, already verified
SQLCipher staged inode inside the *same private temporary staging
directory*. The link operation must refuse to overwrite an occupied
file; the original collision-control file must remain byte-identical;
reopening the promoted ciphertext with the new key must reproduce
every staged row and schema object. Both temporary link names are
deleted with the private staging directory.

The observable `verifiedTemporaryEncryptedCopy.atomicTemporaryPublicationVerified`
field is required to be `true` for the revised temporary-copy proof.
The original source remains untouched, and
`destinationCreated=false`, `encryptedDestinationVerified=false`,
`migrationEnabled=false`, `executionEnabled=false` remain unchanged.

**Scope limit:** this proves atomic *create-if-absent* behavior only on
the CI/test system's **temporary filesystem**, not on the user's
chosen destination volume. It does not solve path-parent replacement,
handle-pinning/TOCTOU races, cross-volume publishing, interruption
durability, cleanup after an interrupted live publish, encrypted
runtime packaging, first-run local authorization, or any real
operational installation. The final publication gate must relocate
staging to an independently secured directory on the **actual
destination filesystem**, verify native handle/path identity, flush
ciphertext and directory metadata where supported, and then invoke
the guarded irreversible publish step with explicit consent.


## Isolated destination-volume encrypted staging rehearsal (2026-11-06)

Following the owner's successful Shadow acceptance of the OS-temporary
hard-link rehearsal, `installer-core::encrypted_copy_preflight` now offers
`rehearse_encrypted_test_copy_on_destination_volume` as a **separate,
explicitly invoked core-only test path**. It reuses the established
`preview_migration_destination` check, verified RAM copy, SQLCipher export,
wrong-key control, row/schema fidelity comparison and exclusive native
hard-link check. Its scratch directory is randomly named and created directly
under the **canonical proposed destination parent**, so the trial exercises
the chosen filesystem rather than assuming the OS temporary volume behaves
identically.

The original OS-temporary GUI rehearsal is unchanged; **the new path is not
wired to the GUI or CLI**. No real selected destination filename is created,
opened for writing, or overwritten. Both temporary hard-link names and the
encrypted scratch directory are removed on normal completion. Focused
cross-platform Rust regression cases exercise empty target cleanup, occupied
target preservation, missing parent rejection, source preservation, and Unix
symlink-parent rejection. Their CI acceptance must be recorded separately.

This is deliberately **not** final destination publication: rechecking
canonical paths before and after does **not** pin native directory handles
against TOCTOU substitution, and a successful scratch hard-link does not prove
a durable or race-safe link at the actual destination filename. Crash
recovery/flush ordering, exact target-handle identity, deliberate first-run
authorization and verified operational application packaging remain open.
Keep `destinationCreated=false`, `encryptedDestinationVerified=false`,
`migrationEnabled=false`, and `executionEnabled=false` for every
application-facing result until those independent gates pass.

## Verified-stage file flush barrier (M2.06 prerequisite, 2026-11-06)

Before its **existing private temporary hard-link rehearsal**, the installer
core now requires `sync_verified_ciphertext_stage` to succeed on the
already-reopened and independently compared SQLCipher ciphertext file.
The barrier rejects absent, non-regular and symlink staging paths, opens
the verified stage with a writable handle for Windows `FlushFileBuffers`
compatibility, and calls Rust `File::sync_all` without modifying its
contents. A failed flush refuses even the *temporary* promotion link.
Focused Rust regression coverage checks successful flush, unchanged file
contents, missing paths, directory rejection and Unix symlink rejection.

This is **only a file-content flush prerequisite**, not a completed
crash-durable database publication. It neither flushes the target parent
directory entry nor pins an exclusive native destination directory handle.
There is no final user-selected target creation, no application first-run
authorization, no recovery journal and no GUI/CLI migration execution.
The existing four fail-closed installer result flags stay unchanged.
Cross-platform CI evidence for this incremental step is recorded separately.

## Destination-parent file-identity rehearsal (M2.06 prerequisite)

The isolated destination-volume rehearsal now holds a native open handle to
the **canonical destination parent** throughout the SQLCipher export,
full-content verification, file flush and test-only hard-link promotion.
It compares the directory's OS identity with a newly opened handle before
and after rehearsal (Unix device/inode; Windows volume serial/file index via
the Windows system API). On Windows the directory handle is opened with
backup-directory semantics and without delete sharing, so ordinary parent
rename attempts are prevented while the handle is live.

A replaced parent that preserves the same pathname must fail identity
revalidation; occupied final target names are also rejected. Focused
regressions cover unchanged files, an existing output collision and Unix
parent-directory substitution. The canonical path already used by the
preflight preserves the macOS /var-to-/private/var normalization rule.
The original operating-system-temporary GUI rehearsal is unchanged.

**Security limit:** the subsequent scratch file operations still use
pathnames, not directory-relative native operations. A malicious actor may
race those pathname operations between checks, particularly on Unix and
when an ancestor component changes. Holding and checking a handle is a
useful *detection and refusal gate*, not a guarantee of no TOCTOU and not
a permission to publish a real destination. The final atomic
directory-relative create-if-absent operation, appropriate parent
directory sync, crash recovery and first-run owner authorization are
separate unfinished requirements. No selected final destination is written.

## Unix pinned-dirfd exclusive-link contract (M2.06, test-only)

The next isolated test gate uses POSIX `linkat` with **two already-open
directory descriptors**: the directory holding a disposable staged fixture
and the selected destination parent pinned by
`PinnedDestinationParent`. Its target name must be a private
`minglefield-rehearsal-*` basename, never the selected final migration
filename. A second link creation must fail as `AlreadyExists`. The private
link is removed using `unlinkat` relative to the original destination
directory descriptor, not by a pathname vulnerable to a substituted parent.
A pre-existing same-named user file must remain untouched.

The native helper currently compiles **only into Unix Rust tests** and
does not create final database files in the GUI, CLI, or production core.
There is no portable fallback to ordinary path-based `hard_link` for real
publication. Windows requires a separately validated native file-handle
relative implementation, and *all platforms* still require checked stage
inode identity, destination entry durability, exclusive publication
authorization, interruption recovery and first-run trust before enabling
installation. Previous file-flush and path-preview checks are still
necessary but insufficient to meet these gates.

MDCI acceptance for this test-only step: Ubuntu/macOS run the Unix
relative-link collision/cleanup test; Windows continues to compile
and exercise its existing destination identity, SQLCipher, and Host
tests. Do not request portable GUI artifacts for this technical gate.

## Verified real-file fixture migration on chosen destination (M2.06 development gate)

**Implementation/test commit:** `b136fbfb5d16134916ddb68a0dbbc189293bc06c`
(after applying GitHub's exact rustfmt diff).

A Rust-test-only `publish_disposable_fixture_copy` now drives the **same
verified export and staging implementation** used by existing preflight,
but requests an actual output file at an explicitly selected and previously
absent filename within a disposable target directory. It verifies the
encrypted stage, flushes ciphertext, then uses a no-overwrite hard-link
promotion to the real fixture destination. The reopened **destination**,
not just the temporary stage, is checked against the expected corrected
RAM snapshot. The randomized staging directory is removed and the final
fixture database remains until the caller's test cleanup.

The tests cover plaintext and SQLCipher sources, metadata and BLOB fidelity,
seven reviewed changes, stale-review rejection, weak password, occupied
target, missing parent, unchanged source bytes and no residual staging.
An **ignored-by-default Python 3.11 integration test**, invoked explicitly by
existing installer CI after `sqlcipher3` installation, opens the **final
published fixture path** through `server/alpha_sqlcipher_runtime.py`,
confirms data/metadata/integrity, and rejects a wrong key.

**Verified three-OS CI evidence** (including real Python runtime):
- Ubuntu core: https://github.com/daresan/Minglefield/actions/runs/42162575420
- Windows and macOS native security:
  https://github.com/daresan/Minglefield/actions/runs/42162575471
- AGENTS security: https://github.com/daresan/Minglefield/actions/runs/42162575388

**Critical separation:** The actual final-name publication is guarded
by Rust `#[cfg(test)]` and is not compiled into normal installer builds.
Existing public rehearsal results still return
`destination_created=false`, `encrypted_destination_verified=false`
and `execution_enabled=false`. The synthetic fixture test truthfully
reports its own created-and-verified output but
`execution_enabled=false`, meaning the general application migration
path is **not** exposed. No GUI or CLI command, first-run Host claim,
operational installation, or real user database migration is enabled.

This demonstrates that **GitHub Actions and the supported operating systems
do permit actual selected-path SQLCipher creation** in an isolated test
directory. It is not yet evidence of a production-safe, path-race-resistant,
crash-recoverable installation. The next bounded milestone task is the
**explicit-consent, tightly scoped installer execution command**, reusing
this proven core path and preserving no-overwrite, source-safety and
backup/rollback requirements before any real user-data test. Never weaken
the existing Python login/Host authorization boundary.

## Controlled Alpha GUI: explicit, backup-verified encrypted database copy (2026-11-06)

**Implementation:** `installer-core::encrypted_copy_preflight::execute_reviewed_encrypted_copy`
and Tauri `migration_review::create_experimental_encrypted_copy`. This is the
first **normally compiled** (not `#[cfg(test)]`-only) path that can publish a
real encrypted SQLCipher copy at a user-selected, unused destination filename.
The existing source is opened read-only; the seven previously verified
categories of staged corrections reuse the same corrected in-memory snapshot
and SQLCipher export path as the fully passing CI fixture tests.

**Operator flow:** review the existing Alpha source and all tables, enter and
confirm a strong NEW destination DB password once in the existing wizard,
complete both the in-memory rehearsal and the temporary SQLCipher proof, and
on the final Review page enter an **existing separate source backup** and
type exactly `CREATE EXPERIMENTAL ENCRYPTED COPY`. The Tauri backend
repeats the mandatory approval and migration checks. The Rust core requires
a regular non-symlink backup that is a **different underlying file**
(natively checked, including hardlink aliases on Windows/Unix), reopens both
source and backup through read-only verified SQLite/SQLCipher snapshots and
compares complete data, schema, metadata and foreign-key/integrity evidence.
If validation fails it creates **no final destination**. A selected target
that already exists, an invalid source, incorrect key, stale staged edit,
invalid destination path, or wrong/absent confirmation is rejected.

**After approval:** a private directory on the chosen destination volume
holds the fully checked encrypted ciphertext. The file is flushed before
the final name is created with a no-overwrite hard link; the **real final
destination file**, not just the temporary stage, is reopened and independently
compared to the corrected RAM snapshot. The final file remains at the
chosen path; temporary staging is cleaned up. The returned result has
`status=experimental_encrypted_copy_created`,
`destinationCreated=true`, `encryptedDestinationVerified=true`,
`backupVerified=true`; it explicitly reports
`applicationInstallationEnabled=false` and
`hostProvisioningEnabled=false`. The old preflight results continue
truthfully to report `destinationCreated=false`.

**Limitations — not production-ready or M2.06 fully accepted:**
- The backup is **user-supplied** and must be created independently while
  the source application is stopped. We verify data equivalence and
  distinguish hard links, but do not create/manage an automatic backup,
  attest independent physical storage, or guarantee the copy has survived
  arbitrary power failures. The GUI must not claim otherwise.
- This deliberately bounded Alpha path uses an OS pathname for the final
  hard-link. Despite destination-volume staging and directory-identity
  checks, a malicious concurrent ancestor/target-directory substitution
  may race pathname resolution. Full native handle-relative publication
  and parent-directory durability/recovery remain required before general
  release.
- If a late verification/cleanup operation fails **after** creating the
  final hard link, the destination may remain. The UI instructs the
  operator to inspect the path before retrying; it must never overwrite
  an existing file, silently remove data or falsely report clean rollback.
- The current source is resnapshotted on execution; edits/credentials and
  backup are checked again. Running a live database with concurrent writes
  can invalidate the backup equivalence; **stop the application** and retain
  a known-good source copy for manual Alpha tests.
- This command does **not** start or install the application, unlock the
  runtime on subsequent launches, create `mingleadmin`, claim the Host,
  enable unattended migration or create any other installation artifact.
  Those remain separate approved milestones and security boundaries.
- There is **no portable acceptance build from this development commit**.
  The CI core and GUI checks prove narrow backend/frontend behavior; the
  owner must still inspect a portable Alpha milestone build and its actual
  user-visible behavior on Shadow/other supported systems.

**Tests:** ordinary Rust cross-OS tests now cover absent/mismatched backup,
hardlink aliases, insufficient confirmation, occupied target and verified
successful encrypted publication. Separate Python interoperability and
fixture tests continue on all three OS. The GUI frontend tests the same
review/consent prerequisites, and the Tauri backend validates the exact
confirmation and presence of a backup before any database work.

## M2.07 first read-only interruption/recovery classification

The installer core now provides
`encrypted_copy_preflight::inspect_encrypted_copy_recovery` as an
**inspection-only** building block. Given a current read-only
source snapshot, the original source key, candidate destination key,
and the exact reviewed corrections, it reconstructs the expected
post-edit snapshot in private memory and classifies the final target
as `DestinationAbsent`, `ExistingMatchesExpected`, or
`ExistingUnverified`. It rejects an existing plaintext SQLite
copy, incorrect ciphertext key, source-file hardlink alias, unrelated
occupied file or different corrected values as a *verified encrypted
copy*. Both returned automation permissions are always false:
`automatic_retry_permitted=false` and
`automatic_delete_permitted=false`.

**Security boundary:** matching values are evidence of *content
equivalence at the time of inspection*, not a proof that this file came
from a particular installer attempt, that the parent directory is
durable on disk, or that a Host/application has been installed.
Unknown source data, paths or failed inspection do not authorize
mutation. No cleanup or overwrite is performed. The original
core-only function has been extended by the later M2.07 read-only
receipt-aware classification documented below. Neither function
updates the owner database or constitutes general crash recovery.

### Restart-safe read-only recovery status in Tauri (M2.07 development gate)

The shared core now exposes
`inspect_interrupted_encrypted_copy`, combining the existing
independent receipt reader, source/backup verification, registered
schema-addition review and full read-only SQLCipher data comparison.
The final Tauri Review page provides a **Recovery-Zustand prüfen
(nur lesen)** action using the already selected original database,
existing independent backup, proposed encrypted destination and
corresponding DB passwords. Unlike execution, this command does
not require a fresh in-memory rehearsal to have survived the
process restart.

The function returns exactly one of these informational states:

- `NoRecordedOperation` — neither the destination name nor the
  reserved receipt is present; this grants **no automatic retry**.
- `UnrecordedDestination` — a target exists without its expected
  reserved receipt; it must not be overwritten.
- `ReservationWithoutDestination` — a validly shaped receipt
  reserves the target path, but the final encrypted file is absent;
  no replay, cleanup or rollback is authorized.
- `PublishedContentMatches` — saved receipt fingerprint, source,
  separate backup, reviewed corrections/schema additions and
  **actual SQLCipher contents** match on read-only inspection.
  This is *not* authenticated provenance or application installation.
- `ManualReviewRequired` — malformed receipt, changed backup,
  mismatched edits/schema selection, incorrect destination key,
  plaintext/foreign target or other verification failure.

Every result always reports
`automaticRetryPermitted=false`,
`automaticDeletePermitted=false` and
`installationEnabled=false`. The UI independently validates these
flags and refuses to display an unexpected response as success.
The Tauri command does not invoke any write-capable migration,
claim or Host-provisioning function. This new feature has
focused automated CI tests but awaits a separately authorized
portable GUI milestone build for real-world visual acceptance.

**Security limitations:** The receipt is still a self-asserted,
unkeyed hash record, not an authorization token, trusted signature
or proof that a particular installer process created the file.
Checking the receipt and re-opening the SQLCipher file are read-only
operations but not an atomic cross-file transaction; concurrent
adversarial filesystem substitutions and unsupported native
directory durability remain separate M2.07 gates. Do not infer a
right to delete or retry from any status.

### Verified deterministic fault-injection follow-up

The common private SQLCipher stage/publish function now accepts a
**private checkpoint callback**; its normal entrypoint always supplies a
no-op callback. This is not an installer CLI/API parameter, a persistent
setting, or an extra user-controlled fault surface. Rust unit tests
inject a controlled error at five distinct checkpoints: before temporary
staging, after encrypted export, immediately before exclusive final-file
publication, immediately after that publication, and during final-file
verification. A separate test stages reviewed row changes and injects
a post-publication error.

On every caught test error, source bytes and unrelated occupied files
are unchanged, and private staging cleans up on scope exit. Before
publication the final filename is absent; after publication it remains
a complete encrypted copy which the separate read-only recovery checker
can inspect again. No implicit retry, deletion, overwrite or trust
promotion occurs. The tests verify only the **normal error-unwinding
cleanup path**. They do NOT emulate `abort()`, killed processes,
abrupt service termination, NTFS/APFS/ext4 journal recovery or power
failure. A real abrupt exit can leave a private staging directory;
no automatic sweep of unknown paths has been authorized.

Verified by [Ubuntu Rust](https://github.com/daresan/Minglefield/actions/runs/42246330621)
and [Windows/macOS native security](https://github.com/daresan/Minglefield/actions/runs/42246330676)
at implementation SHA
`5e8e791b65f1be3ce4347d51ff70324e512a979f`.
### Verified actual subprocess termination and post-exit inspection

The next slice invokes the existing SQLCipher stage/publish path from a
**separate copy of the Rust test binary**, configured only through its
private test fixture. It deliberately exits via
`std::process::exit(77)` at five pre-existing checkpoints: before
staging, after ciphertext export, before target publication, after
target publication, and during target verification. Unlike the prior
caught-error tests, **no `Drop` cleanup runs in the terminated
worker**. The test parent verifies the worker exit code, byte-identical
source, unchanged unrelated sentinel and precise file state; it then
reopens the independent recovery inspector without reusing the worker
database connection. Before publication the final path is absent;
after publication the complete encrypted file is readable with
the expected key and refuses a wrong key. Private staged material may
remain on disk after the process exit; this is **expected** and no
production cleanup of unknown directories or retries is authorized.
Only the test parent deletes its entire self-owned fixture directory
after examining the residue.

Verified in [Ubuntu Rust CI](https://github.com/daresan/Minglefield/actions/runs/42264191700)
and [Windows/macOS native CI](https://github.com/daresan/Minglefield/actions/runs/42264192011)
at implementation commit
`bd79683145152b2ed6b2674b4594e384bbe1794b`.
This deliberately forces a process termination **without unwinding**.
It is not a simulated power cut, kernel crash, `SIGKILL`, Windows
`TerminateProcess` or proof of directory-entry persistence.

### M2.07: exclusive operation receipt before encrypted final-file publication

**Development milestone (2026-11-06):** The initial isolated
`recovery_receipt.rs` primitive has now been connected to the
**controlled Alpha SQLCipher destination-creation path** in
`encrypted_copy_preflight.rs`. The prior fixture-only receipt and
fresh-process tests remain. No new crates were added and none of the
existing schema-selection, source-integrity, independent backup or
typed-correction approvals were removed.

The normal ordered path is now:

1. Verify read-only source snapshot and separate existing backup for
   complete logical SQLite/SQLCipher equality, and validate the
   explicit operator consent and selected registered DDL additions.
2. Create an isolated corrected in-memory snapshot; export SQLCipher
   to same-volume private staging, reopen with correct key, reject
   wrong key, compare all values and metadata, and flush the verified
   ciphertext bytes.
3. Generate a **non-authorizing** random 128-bit operation ID. Compute
   streaming SHA-256 fingerprints for physical source and backup files,
   canonical destination path, staged ciphertext and selected edits
   and schema objects. The two logically equivalent databases may have
   different physical file bytes, which are recorded independently.
4. Exclusively create
   `minglefield-target-<SHA256-of-canonical-destination-path>.receipt`
   alongside the destination using `create_new`. A prior operation
   with the same selected destination, even if it never published a
   final database file, **blocks a second operation**. Never silently
   overwrite/delete/reuse such a receipt. The file is flushed and the
   containing directory synced on Unix; Windows directory-entry
   durability remains unproven and is reported as false.
5. Reopen and verify the receipt against the staged ciphertext and
   the same source, independent backup, corrections, schema additions
   and destination path. Only then perform no-overwrite final-name
   hard-link creation. On Unix attempt a final destination-directory
   sync; on Windows report `destinationDirectorySynced=false`.
6. Reopen the actual target with the NEW SQLCipher key, compare its
   complete contents with the corrected isolated snapshot, and recheck
   the same reserved receipt against the **final file** before
   reporting success and removing test staging.
7. Return `recoveryOperationId`,
   `recoveryReceiptDirectorySynced` and
   `destinationDirectorySynced` alongside the prior verified-copy
   flags. These are *evidence fields*, never permission to install,
   claim a Host, run unattended retry or remove any file.

**New fault-injection tests** use real worker-process termination via
`std::process::exit(77)` immediately after exclusive receipt
reservation **before** final-name publication and immediately after
publication. Subsequent read-only recovery checks confirm that the
receipt remains bound to the surviving verified staged or final
ciphertext. A missing target in the presence of a receipt is
**reserved/not published**, never automatically available for retry.
Interleaved operation attempts and occupied receipt names fail
closed. The original Alpha source and backup remain unchanged; only
isolated test-owned fixture directories are removed by tests.

SHA-256 now uses a streaming implementation with **64-KiB chunks**;
even databases larger than the old 64-MiB fixture limit can be
fingerprinted without loading the entire database into memory.
The hash remains an **unkeyed integrity fingerprint**, not a secure
proof of author identity or a confidential commitment. The receipt
contains no raw data rows, plain file paths, SQLCipher passwords,
authentication tokens or user credentials.

**Evidence:** [Ubuntu Installer Rust CI](https://github.com/daresan/Minglefield/actions/runs/42291412639),
[Windows/macOS native security CI](https://github.com/daresan/Minglefield/actions/runs/42291412669).
Existing earlier controls were already proven by
[Ubuntu](https://github.com/daresan/Minglefield/actions/runs/42273342933)
and [Windows/macOS](https://github.com/daresan/Minglefield/actions/runs/42273342890).
No new portable packages have been requested for this development gate.

**Deliberate remaining limitations:** This is still an **Alpha-only,
operator-consented database copy**, not production crash recovery or
a finished Minglefield installation. The Windows parent-directory
flush/metadata durability strategy is not verified; Unix directory
`sync_all` is not itself proof of whole-system power-loss safety.
Native race-resistant handle-relative publication, operation
authentication, securely owned/read-restricted receipts on each OS,
persisted journal state transitions, safe manual recover/rollback
choices, `SIGKILL`/`TerminateProcess` and power-loss simulations
remain separate mandatory work. A failed attempt may leave a reserved
receipt and/or fully published ciphertext. Neither may be removed or
overwritten automatically; inspect them before making an explicit
recovery decision. A matching hash alone does not authorize
reinstallation, Host provisioning or access to the database.

The Shadow M2.06 Alpha acceptance and the generic, operator-selected
missing-schema addition contract are documented in
[registered Alpha schema notes](REGISTERED-ALPHA-SCHEMA.md).
Schema additions are applied only to the new isolated SQLCipher copy
after an explicit choice; they do not alter the original, grant Host
ownership, or authorize an unverified operational runtime. This generic
copy-time option is distinct from M2.07 read-only recovery inspection.

## Installed Alpha runtime and preliminary application-source payload (2026-11-07)

The existing `private_alpha_gateway` can now run against a verified,
already encrypted operational SQLCipher database through
`create_installed_local_alpha_server` and the original
`AlphaAuthStore`/`HostCommitPolicy` tables. A private isolated Python
subprocess entrypoint `server/installed_alpha_launch.py` starts the
same gateway using a bounded one-shot stdin JSON envelope from an
eventual native installer-controlled launcher; keys and passwords
are not command-line options, environment variables or saved config.
The gateway is loopback-only, the previous console bootstrap is
disabled, and the account/Host must have been provisioned by
a separate authorized transaction *before* launch.

In [Ubuntu CI 42313263186](https://github.com/daresan/Minglefield/actions/runs/42313263186)
and [Windows/macOS CI 42313263192](https://github.com/daresan/Minglefield/actions/runs/42313263192)
the subprocess was launched twice with a real disposable encrypted
Alpha store. Local login, Hosts, Effects, Jobs, Games, Host settings
and negative foreign-Host authorization checks passed over HTTP and
persisted after shutdown/restart. See also the 795-test
[MAP conformance run 42313263195](https://github.com/daresan/Minglefield/actions/runs/42313263195).

The first **actual source-bundle creation** path is
`installer/scripts/build_alpha_application_payload.py`, reusing
`audit_alpha_runtime_imports.audit`. It produces a deterministic
verified ZIP of the precise imported Python Alpha application modules
and an inspectable per-file checksum/size manifest. The bundle
can be extracted and its real launch script imported/run under
a separately provided compatible Python. [Focused CI 42313949256](https://github.com/daresan/Minglefield/actions/runs/42313949256)
passed after correcting the necessary required-module check.

**Not yet built:** a pinned, redistributable cross-platform Python
interpreter and verified SQLCipher driver, an installable Minglefield
application, native Tauri execution/handoff, installation-bound
single-use `mingleadmin` authorization, or a clean-machine end-user
launch. The application source ZIP itself says no embedded Python
runtime, dependency lock or publisher signature. Existing secure
source/backup copy and Host authorization requirements remain intact;
no portable acceptance build has been requested by these steps.
