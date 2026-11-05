# Tauri 2 installer GUI — non-installing proof of concept

This GUI calls the existing Rust `minglefield-installer-core::plan` function, the same one used by `installer-cli`. It only previews plans. It does not copy files, download dependencies, verify release provenance, install runtimes, authenticate, or claim Hosts. Do not distribute as a functional installer.

On a trusted developer workstation with Node.js/npm, Rust and Tauri OS prerequisites:

```powershell
cd installer/gui
npm.cmd ci
npm.cmd run dev
```

This is a development command, **not** an end-user prerequisite. Do not commit `node_modules` or `src-tauri/target`. On Shadow PowerShell use `npm.cmd` to avoid the blocked `npm.ps1` shim without changing execution policy. Before release, establish a fully offline verified asset/build pipeline and test the packaged entrypoints on supported operating systems. The npm and Cargo lockfiles are already tracked and native preview packaging is now exercised in CI. The workspace root `installer/Cargo.toml` deliberately excludes this separate Tauri crate for now, so existing Rust CI remains independent of Tauri OS prerequisites.

Both GUI and CLI use the same Rust planning function, but this does not yet establish a common packaged executable or silent installation. Those are still required by the phase specification.

## Shared configuration preview

Both the GUI and unattended CLI validate the same Rust `InstallerConfig` (version 1). The GUI accepts either separate install/data paths or a versioned UTF-8 `key=value` preview. The CLI accepts `--silent --defaults` or `--silent --config FILE`, optionally with `--install-dir ABSOLUTE_PATH` as an explicit override. A portable config contains no machine-specific paths:

```text
version=1
install_optional_conda=false
install_optional_comfyui=false
explicit_optional_consent=false
```

`install_dir` and `data_dir` are optional; omitted paths are resolved from the current operating system's per-user defaults. Unknown/duplicate keys, unsupported versions, malformed booleans and unconsented optional installs are rejected. This is still a **non-installing plan preview**; do not confuse explicit optional consent with actual installation authorization. The format is intentionally a strict line-based configuration, not JSON. Future schema changes require a new version.

### Machine-readable unattended preview

Use `minglefield-installer-cli --silent --defaults --json` or `--silent --config FILE --json`. The CLI prints one JSON object to stdout on successful planning (`status=plan_only`, `exit_code=0`) or on argument/configuration failure (`status=error`, `exit_code=2` or `3`). The JSON schema is version 1, and `execution_enabled` is always false at this stage. Code 2 means invalid arguments; code 3 means unreadable/invalid configuration or rejected plan. No installation, Host claim, or application-data mutation occurs. Without `--json`, human-readable output remains available. This preview is not an installer execution API.

### Argument validation hardening

The unattended preview rejects repeated `--silent`, `--defaults`, `--json`, `--config`, or `--install-dir` flags with exit code 2. A value-taking option cannot silently consume a following `--flag` as its value. A deliberately malformed invocation fails before file access or planning. The `--json` output remains a read-only preview; this is not an installation execution entrypoint.

### Minglefield release provenance (no paid certificates)

This section concerns **installing Minglefield itself**, not the independent, stricter game-installation security rules.

- Official distribution: the public `daresan/Minglefield` repository and a release based on its protected `main` branch.
- Forks: a fork maintainer is the publisher of their own distribution; no approval or certificate from the original maintainer is required.
- No paid publisher certificates, commercial signing services, or platform code-signing subscriptions are required by Minglefield's own trust policy.
- An artifact manifest with SHA-256 checks file integrity, but not the connection to a GitHub commit. A trusted GitHub release and a reproducible or independently attested build provenance should connect the artifact to the chosen repository and commit using free mechanisms where practical.
- The `publisher::PublisherPolicy` placeholder currently rejects even checksum-valid artifacts with `RepositoryProvenanceUnavailable`, until repository/release provenance verification is implemented. This is **not** a demand for a paid signing certificate. No installation execution is enabled.

Platform packaging and OS security prompts must be documented honestly; Minglefield's own policy must not misrepresent operating-system trust requirements.

## Cross-platform GUI CI (initial smoke gate)

The `tauri-gui` job in `.github/workflows/installer-rust.yml` now runs on Windows, Ubuntu and macOS. It checks Tauri Rust formatting, compiles and lints the separate `src-tauri` crate, runs its Rust tests and builds the Vite frontend. Linux runners install the WebKitGTK 4.1 and related development libraries.

Both `package-lock.json` and `src-tauri/Cargo.lock` are tracked. CI installs frontend dependencies with `npm ci` and checks, lints and tests the Tauri Rust backend using Cargo `--locked`. This fixes dependency resolution, but does **not** establish bit-for-bit reproducible binaries or verified artifact provenance. This job checks compilation, **not** native installation or GUI interaction. The separate `Tauri native package smoke builds` workflow produces unsigned, non-released `.exe` (NSIS), `.deb`, and `.dmg` preview packages on Windows, Ubuntu and macOS. These packages are not yet a functional Minglefield installer; creating a bundle does not verify install, launch, upgrade, removal or OS trust prompts.

## Bundled framework license preview

The setup-manager GUI now exposes the complete root `LICENSE` text as a read-only, accessible panel. The Tauri Rust backend embeds that file at compile time and returns it via `framework_license`; a Rust regression test checks its identity and completeness. The preview does not require a network request or assert acceptance, and it does not grant consent for marketplace services or installation writes. The GUI is still plan-only. When building the GUI outside the repository layout, the root `LICENSE` file must be available at the expected relative path; packaged binaries embed the text and do not need that source file at runtime.

## Standard and Advanced setup preview

The **Standard** view is selected by default and submits the Rust backend's per-user OS defaults to the shared `preview_install_plan` command. The **Advanced** view exposes custom install/data directories or the existing versioned `key=value` configuration editor (v1/v2). Switching back to Standard ignores hidden advanced values; it does not authorize optional components. Both routes remain strictly plan-only (`executionEnabled: false`). GUI acceptance of a preview does not constitute an installation or license/marketplace consent. Native packaged GUI smoke tests and a manual switch-mode test remain necessary after this change.

## Setup-mode isolation regression tests

`preview-arguments.js` is a pure, side-effect-free adapter for Standard/Advanced UI inputs. Run `node --test preview-arguments.test.js` to verify that Standard ignores hidden advanced values, Advanced custom paths and versioned configuration are mutually exclusive, and missing defaults/unknown modes fail closed. The `Installer Rust checks` workflow executes these Node tests in its Tauri GUI job on Windows, Ubuntu and macOS before the Vite build. These are parameter-mapping tests, **not** automated end-to-end GUI interaction or installation execution tests.

## Existing source checkout detection (read-only)

The shared Rust installer core now exposes `discovery::inspect_source_directory` for an **explicitly selected** directory. The Tauri GUI provides a manual path input and `inspect_source_path` command. Recognition checks the Minglefield README identity and structural markers (`AGENTS.md`, `schemas/`, `server/`, `installer/`), without requiring `.git`, a preinstalled runtime, or an executable. It returns `source_checkout` or `unrecognized`, and always reports `provenanceVerified=false`, `launchReady=false`. This is **not** a signature check, proof of authenticity, exhaustive discovery of standard OS installation locations, or packaged application recognition. It performs no installation, Host claim, or data migration. Focused Rust tests cover positive and negative structural cases; cross-platform CI results must be verified before treating this increment as passing.

## Binding application versus community-game installation scope

See [platform-versus-game installation boundary](../../docs/PLATFORM-VS-GAME-INSTALLATION-BOUNDARY.md). This Tauri/Rust setup manager installs **Minglefield itself** only. Game integration trust checks, game marketplace licensing and the 5% marketplace transaction share do not apply to installation of the Minglefield application. CI for game integration does not validate this setup manager. The current GUI is still a non-installing preview.

## Portable setup manager and bundled application README

[Binding portable manager requirements](../../docs/PORTABLE-PLATFORM-SETUP-MANAGER.md): this tool is to run without installing the manager itself, on Windows/Linux/macOS, and install the separate Minglefield app. Apple signing/notarization are out of scope unless the maintainer explicitly requests them. The root application README is now embedded in the Tauri binary using `include_str!`, exposed through `application_readme`, and displayed in a read-only panel alongside the full bundled GPL license. Both panels are independent of Standard/Advanced mode, work offline, and do not imply consent. A Rust test checks README presence. Existing NSIS/DEB preview artifacts do not meet portable packaging acceptance; actual installation execution is not implemented.

## Shadow acceptance and implementation order (2026-11-04)

See [Shadow acceptance findings](../../docs/SETUP-MANAGER-SHADOW-ACCEPTANCE-2026-11-04.md). The portable Windows preview displayed an unwanted console window and stale README licensing text; these are addressed by a release-only Windows GUI subsystem attribute and a correction to the root README, with a Rust regression assertion. Actual startup/focus must still be manually verified. **A single-page plan preview is not an acceptable finished wizard.** Next increments: multi-page Back/Next wizard; optional Git/gh/Python/Conda/ComfyUI/**Blender** detection and opt-in configuration; then real Minglefield app installation and local Host setup. The current preview still does not install the app.

## Existing application record review (read-only)

The Source inspection wizard step can inspect a user-selected SQLite or SQLCipher database. Each record reader independently verifies SQLite integrity and foreign keys before querying allowlisted tables with read-only connections and a 500-row-per-category cap. SQLCipher credentials are never displayed or included in the review. This is **not** a transferable migration manifest yet: all corrections are held in frontend memory and discarded when the inspected database is changed or the wizard is restarted.

| Tab | Existing Alpha table | Loaded fields | Editable in memory |
| --- | --- | --- | --- |
| Anmeldung | `alpha_users`, `alpha_agents` | User ID and disabled; Agent ID, owner and disabled | User and Agent disabled flags |
| Hosts | `sec01_host_owners`, `sec01_host_runtimes` | Host ownership and allowlisted runtime ID, type, endpoint, enabled, input folder | None — identities and live runtime configuration remain protected |
| Effekte | `sec01_host_effect_definitions` | Host/effect ID, description, enabled | Description (≤256 characters) and enabled flag (staged only) |
| Jobs | `alpha_jobs`, `sec01_host_jobs` | IDs, ownership/requester, effect, state | None — job and execution records are immutable |
| Games | `alpha_game_projects` | Project and host/owner IDs, name, repository/attachments/output roots, settings revision | Name and all three absolute paths; revision and ownership unchanged |

The host-policy tables are optional in older Alpha databases. Absent tables, failed readers and other unavailable data are explicitly listed in the final Database review rather than fabricated. Unknown columns and tables are not silently migrated. Raw host runtime JSON, host owner identity, effect workflows, job execution state, sessions, credential hashes, grants and ledgers remain excluded from editing. Only explicitly allowlisted runtime metadata is displayed; credentials and arbitrary config keys are not returned to the UI. The reader is not yet a complete inventory of every persisted platform object.

**Before enabling migration:** use a transactionally consistent, revalidated source snapshot with verified source identity and schema compatibility; define the destination mapping for *all* persisted tables, preservation of sensitive authorization data, operator confirmation, atomic backup/restore and rollback behavior. Cross-category frontend review does not satisfy these requirements. `migration_enabled` and `execution_enabled` remain false.

Frontend correction guards have Node regression tests in `legacy-record-review.test.js` and `alpha-user-review.test.js`; Tauri reader tests verify available/missing schemas and source preservation. A green CI run proves only automated checks; a real DB migration and installation acceptance test remains outstanding.

## Verified migration rehearsal (dry-run only)

The **Data Review → Migration rehearsal** action now uses a backend-enforced preflight, not only a frontend summary:

1. Select and integrity-check a source Alpha SQLite/SQLCipher database and load the Login, Hosts, Effects, Jobs and Games review.
2. Stage supported changes (user or Agent disabled flag; effect description or activation; game name and three directory paths). Select an **existing destination directory**, which may be the source directory, and a **different, unused filename**. The source filename and potential SQLite sidecar filenames cannot be reused. The installer checks the path through the shared `migration_destination` module. It does not create that file.
3. Enter the existing source database password again when requested. It is cleared from the form following the request.
4. The Rust core snapshots the current source transactionally, verifies SQLite integrity and foreign keys, checks the seven mandatory Alpha authentication/job tables and their required columns, and inventories **row counts for every table**, including sensitive and extension tables without returning their contents.
5. The core revalidates staged original values against the newly checked snapshot, rejects duplicate/unrecognized/oversized changes, rejects databases with unreviewed triggers when corrections are requested, and simulates the changes inside a **temporary in-memory transaction**. Row counts, `quick_check` and foreign-key checks must still pass. The transaction is rolled back. No records are written back to the source.
6. The final preview displays the checked destination, all source table row counts, schema-object count and staged-correction count. Editing a value or switching the source invalidates prior verification.

This is an actionable **rehearsal of the supported record corrections**, but **not** a complete or executable data migration. A matching set of Alpha table names is not publisher identity or provenance. No SQLCipher destination is generated or tested; all original records (including host runtime configuration, grants, sessions, workflows, game projects, and opaque extensions) must still be transferred and verified by a future executor. Transactionally consistent source identity and destination encryption/integrity checks must be repeated immediately at actual execution time. Application installation and Host provisioning remain disabled.

Regression tests:

```powershell
cd installer
cargo test --workspace --locked
cargo test --manifest-path gui/src-tauri/Cargo.toml --locked
cd gui
node --test
```

The portable GUI build is reserved for **significant manual acceptance milestones**, not every code change on the feature branch.

**2026-11-05 field coverage milestone:** Runtime details are displayed as metadata, not edited. Game project directory paths and effect/Agent enablement can be staged and rehearsed against fresh original values. Nothing is applied to the source or to an installation. The same-directory destination allowance is checked in the shared Rust preflight, with exclusive-file creation and live SQLite sidecar exclusion reserved for the eventual executor.


## Full schema-field inventory (next migration readiness milestone)

The verified migration rehearsal now returns `fieldCoverage` for **every** application table in the inspected, consistent source snapshot, not just tables rendered in the editor. Each entry lists column **names only**, the explicitly allowlisted staged-editable columns and all remaining protected columns. No stored values, credential hashes, session tokens, arbitrary host JSON, or raw BLOBs are returned in this inventory. The final review includes total column and protected-column counts. An unknown table is never silently dropped from the inventory and all of its columns are protected by default.

This is a **coverage and readiness report**, not proof that every column is understood or mapped to a future destination schema. No schema transformation, persistent export, SQLCipher destination creation, installation or Host claim is authorized. A subsequent migration implementation must account for all original tables and objects and prove that no data was discarded before execution is enabled.

## Git profiles and visible field-coverage review (2026-11-05)

The existing **Hosts** tab now also reads the real `alpha_git_profiles`
records from the same integrity-checked, bounded source snapshot as other
legacy records. It displays the host/profile/owner IDs, authentication
method and Git executable **read-only**. Only the non-secret profile `label`,
`author_name` and `author_email` fields can be staged. The existing
`save_git_profile` API is the source of their 120/256-character constraints.
No executable command is evaluated, no Git profile is activated, and no Git
credential or private key is loaded.

Each staged Git text change is verified in the independent Rust rehearsal
against the exact original value **and** original host/profile/owner identity.
The change is applied only to a temporary in-memory transaction that is
rolled back, with no source mutation or destination creation. Incorrect
owners, duplicated fields, oversized values and stale values are denied.

After a successful rehearsal, the **Data Review** page displays an expandable
table-by-table summary. Each table shows its verified row count plus all
`stagedEditableColumns` and `protectedColumns`, checked for missing or
double-classified fields before display. This report includes unknown tables
as protected by default, but never reads or displays stored credential,
session, job, or runtime JSON contents. These source field names are an
inventory of the current Alpha database, **not** a versioned migration
mapping. Unknown schema revisions and destination encryption remain future
execution blockers. The installer continues to report `executionEnabled=false`.

Regression suite: `cargo test --workspace --locked`,
`cargo test --manifest-path gui/src-tauri/Cargo.toml --locked`,
and `cd gui && node --test`. CI must pass on all three operating systems
before triggering the milestone-only portable packaging workflow.

## Complete in-memory data-fidelity gate (next milestone)

After the existing SQLite integrity, Alpha-schema and per-column review, the
installer now creates **a second independent, disposable in-memory copy**
using SQLite's backup API. Its Rust fidelity gate checks:
- source-versus-copy schema objects, indexed constraints, triggers and views,
  plus application ID, user version and encoding;
- every SQL table, **including sqlite_sequence and any extension tables**;
- complete row values, including arbitrary BLOBs, with a typed SHA-256
  fingerprint for each row and a multiplicity-sensitive multiset comparison
  that detects changed duplicate records even if table row counts match;
- source and staged-copy integrity and foreign-key constraints.
No per-record fingerprints, BLOBs, passwords, session tokens or raw values are
returned in the GUI response or logs.

Only after this full equality check does the dry-run apply allowlisted staged
corrections to the **second in-memory copy**. It checks table counts, integrity
and foreign keys, rolls back the transaction, and repeats the complete
content/schema comparison. The source snapshot itself is no longer used as
the staging transaction target. Rehearsal errors do not create partial
destination files. The GUI now includes full-data-copy verification and the
checked row/table/schema counts in the final preview.

This is a strong **in-memory data fidelity rehearsal**, not an encrypted SQLCipher
output and not a production migration. The response explicitly sets
`encryptedDestinationVerified=false`, `destinationCreated=false` and
`executionEnabled=false`. The future encrypted executor still requires
exclusive target creation, a strong confirmed password for **every new
installation**, integrity and content checks after reopening the encrypted
file, schema-version rules, failure cleanup/rollback, and operator acceptance.
The fidelity implementation currently refuses tables exceeding 1,000,000
rows, tables exceeding 1024 columns, or individual encoded rows over 128 MiB,
rather than silently checking only part of the data.

## Temporary encrypted SQLCipher disk-copy acceptance (separate explicit action)

After a **successful zero-change memory-only** migration rehearsal, the GUI
offers **Test encrypted temporary disk copy (create, verify, delete)**. The
user enters a strong, confirmed *test-only* SQLCipher key. The existing
Alpha unlock password is entered separately; it is optional for plaintext
SQLite. Neither password is stored in the installation review.

The backend revalidates the source and destination preview, verifies the
full in-memory source snapshot, generates an unguessable private OS-temporary
directory (Unix mode 0700), and exports the snapshot to an actually encrypted
on-disk SQLCipher file using bound parameters and `sqlcipher_export`.
The SQLite backup API is not used for plaintext-to-encrypted conversion:
SQLCipher explicitly disallows that transition through backup. The export
restores application/user schema version metadata. The backend independently
checks the encrypted file header, proves an unrelated key is rejected,
reopens with the new key, and compares **all schema and row values** against
the in-memory source. It closes its handles and deletes the entire temporary
directory before returning success. Failure paths attempt best-effort cleanup
and never write to the proposed final destination.

The result is deliberately named `temporaryEncryptedCopyVerified` and
`temporaryFilesRemoved`. It is a verification of **ephemeral ciphertext on
disk**, not the final Minglefield migrated destination: the final preview
still reports `encryptedDestinationVerified=false`,
`destinationCreated=false`, `migrationEnabled=false` and
`executionEnabled=false`. The temporary copy currently tests the
**unchanged database only**; staged user/Agent/Git/Game changes continue
to be verified separately by the memory rehearsal and cannot be included
in this disk test. The real executor still requires a trusted schema
mapping, source identity binding, an exclusive target with atomic
publication, rollback/backups and an explicit user-approved destination
password. No Host provisioning occurs.

Regression tests cover plaintext and encrypted sources, different keys,
wrong-key rejection, byte-identical original source, integer schema version
preservation, AUTOINCREMENT sequences, BLOB and duplicate rows, cleanup
on failure and the GUI refusal to promote ephemeral success into live
migration authorization. No encrypted-file bytes or keys are uploaded.
