# Minglefield installer CLI — current executable contract (M2.11 in progress)

The headless CLI and the Tauri GUI now use the **same**
`installer-core::managed_alpha_install` Rust implementation to validate a
managed Alpha file inventory and copy exactly its declared files. The headless
CLI now exposes four standalone actions (verified files, read-only
SQLCipher verification, reviewed encrypted copy, fresh SQLCipher creation)
and a **fifth, explicitly confirmed same-process first-run action** joining
file installation, new-only encrypted DB creation and local Host setup. They are not yet
composed into a complete installation. A successful individual action does
**not** mean local Host setup, independent native application launch or
M2.11 acceptance.

## Actual file-install invocation (explicit local package)

From `installer/` on a development machine with Rust:

```sh
cargo run -p minglefield-installer-cli -- --silent --defaults \
  --install-alpha-files \
  --package-dir /absolute/path/to/managed-alpha \
  --inventory-sha256 THE_64_CHARACTER_BUILD_BOUND_INVENTORY_DIGEST \
  --install-dir /absolute/new/application-target \
  --confirm-install "INSTALL MINGLEFIELD ALPHA FILES" \
  --json
```

`--package-dir` points to the **full extracted managed-alpha directory**,
containing `managed-file-inventory.json`, `runtime-manifest.json`, the
`application/` files and the `runtime/` interpreter tree. The 64-character
inventory digest must be independently obtained from the trusted build/release
record. **A user-supplied digest alone is integrity pinning, NOT proof of the
publisher, nor permission to run untrusted source.** A discovered repository
or a DB selected for migration never implicitly supplies executable source.

The operation requires all four action flags, checks the package before
creating target paths, uses exclusive file creation, verifies every copied
file, and does not overwrite existing managed files. It permits a selected
application directory containing other user data, provided the managed paths
are still unoccupied. On a partial failure it leaves the new incomplete target
for inspection, not silent overwrite/cleanup, so use a new destination for
retry. The CLI rejects optional Git, GitHub CLI, Conda and ComfyUI installation
requests when used with `--install-alpha-files` until those operations exist.

Without `--install-alpha-files`, `--silent --defaults` (or
`--silent --config /absolute/file`) stays a **read-only plan preview**.
`--data-dir` and `--install-dir` can override config paths, and `--json`
emits bounded structured results. Errors use nonzero exit codes and do not
serialize raw package source paths or credential values in JSON error fields.

## Actual encrypted database actions (new CLI development slice)

The installer CLI also invokes the *existing*, shared SQLCipher Rust
inspection/export paths. These are separate actions: the CLI does **not**
yet orchestrate one complete file + DB + Host + application installation.

**Read-only verification of an existing encrypted database:**

```sh
cargo run -p minglefield-installer-cli -- --silent --defaults \
  --verify-encrypted-db --database /absolute/path/user.db \
  --db-password 'ExistingCipherPass9!' --json
```

**Create a genuinely new SQLCipher database without an existing source:**

```sh
cargo run -p minglefield-installer-cli -- --silent --defaults \
  --create-new-encrypted-db \
  --database /absolute/existing-directory/new-encrypted.sqlite3 \
  --new-db-password 'FreshCipherPass9!' \
  --confirm-new-db 'CREATE NEW ENCRYPTED DATABASE' \
  --json
```

The parent directory must already exist; the chosen database file must **not**
exist. This operation exclusively creates and verifies an encrypted SQLCipher
container, with no Alpha application schema, login user, password hash,
Host owner/grant, or automatic Host activation. Existing targets are never
overwritten. An interrupted or invalid creation leaves its occupied target
for explicit review rather than automatically deleting or reusing it.
The application's existing first-run initialization will create its own
canonical schema and local Host/user records in a **separately authorized**
step. `--new-db-password-file`, `MINGLEFIELD_NEW_DB_PASSWORD`, administrator-
authored version-3 `new_db_password` / `new_db_password_file` and bounded
`--secrets-stdin` can supply the new key; the exact approval is also available
as version-3 `confirm_new_db`. This is not yet a full installer transaction.

**Create a verified encrypted copy from an original and its independent backup:**

```sh
cargo run -p minglefield-installer-cli -- --silent --defaults \
  --create-encrypted-copy \
  --source-db /absolute/original.db \
  --backup-db /absolute/separate-backup.db \
  --database /absolute/new-encrypted.db \
  --db-password 'ExistingCipherPass9!' \
  --new-db-password 'NewCipherPass9!' \
  --confirm-db-copy 'CREATE EXPERIMENTAL ENCRYPTED COPY' \
  --json
```

The copy action does not modify its original or verified backup, refuses
an occupied destination, writes a separate recovery receipt, verifies the
result under the **new** SQLCipher key and returns a non-secret operation
identity. It does **not** create a fresh Host, alter existing owner records,
perform a local user login, or install/launch the application. A **plaintext
legacy source** may omit `--db-password`; an encrypted source cannot be
opened without its key. Both the actual migration and native application
startup must be accepted independently for M2.11.

**Bee-like password sources already available for these DB operations:**
`--db-password VALUE`, `--db-password-file PATH`,
`MINGLEFIELD_DB_PASSWORD`, an explicit `db_password=VALUE` or
`db_password_file=PATH` in an administrator-authored **version 3** config,
and `--secrets-stdin` with a single bounded JSON frame
`{"db_password":"...","new_db_password":"..."}`. Equivalent `new_db_password`
sources exist for new SQLCipher destination keys. Explicitly conflicting
source types are rejected rather than silently chosen; an explicit flag
overrides the **same** config field. Plaintext passwords in administrator-chosen
CLI arguments and configs are accepted by design. Minglefield never writes
those values into generated plans, receipts or logs.

Application launch retains its private stdin pipe between the eventual
native launcher and its SQLCipher worker; the **Rust CLI database operations**
use the shared Rust SQLCipher API directly. Public administrator input
methods do not need to match the internal transport.
A terminal prompt with confirmation for a **new** key remains a required
future interactive-CLI/native application behavior. Current `--silent`
operations never prompt.

Version-3 configuration also supports `source_db_path`, `backup_db_path`,
`new_db_password`, `new_db_password_file`, `schema_additions` (comma-separated
registered object identifiers) and `confirm_db_copy` (the exact approved
confirmation phrase), making an authorized encrypted copy fully scriptable
without repeating flags. An ordinary CLI `--schema-add ID` may override
the configured list.

Example version-3 config is a UTF-8 `key=value` text file (the project
does not yet parse Bee's YAML syntax):

```ini
version=3
install_optional_conda=false
install_optional_comfyui=false
explicit_optional_consent=false
install_optional_git=false
install_optional_gh=false
offer_gh_login=false
consent_git=false
consent_gh=false
consent_login=false
database_path=/absolute/path/user.db
db_password_file=/absolute/private/sqlcipher-password.txt
```

Use this with `--silent --config /absolute/path/config.conf --verify-encrypted-db`. The text config is authored and protected by the
Host administrator; generated defaults never silently persist a password.

## Same-process first-time local Host setup (tested across Ubuntu, Windows and macOS)

The CLI provides an **explicitly approved one-process** operation that
joins its existing shared verified file installation, **new-only** encrypted
database creation, and the **existing installed application's** private
`installed_alpha_first_run.py` admission/Host policy. It does not authorize
taking over any previous/imported DB. No generic CLI command exists for
replaying first-run against a selected pre-existing database.

```sh
cargo run -p minglefield-installer-cli -- --silent --defaults \
  --install-alpha-files \
  --package-dir /absolute/trusted/managed-alpha \
  --inventory-sha256 VERIFIED_BUILD_INVENTORY_SHA256 \
  --install-dir /absolute/new-or-compatible/application-root \
  --confirm-install 'INSTALL MINGLEFIELD ALPHA FILES' \
  --create-new-encrypted-db \
  --database /absolute/existing-data-directory/new-minglefield.db \
  --new-db-password 'NewCipherPass9!' \
  --confirm-new-db 'CREATE NEW ENCRYPTED DATABASE' \
  --setup-local-host \
  --login-user-id mingleadmin \
  --login-password 'DifferentLoginPass9!' \
  --confirm-local-admin 'ACTIVATE LOCAL HOST ADMIN' \
  --json
```

The administrator is responsible for trusting the selected package source
and its build-bound inventory digest; a matching SHA-256 is not independently
a publisher signature. The directory containing the database must already
exist and the DB filename must be unused. A collision, wrong key,
incomplete/modified managed source, missing consent or identity conflict is
rejected. A partially completed interrupted installation is **not silently
deleted, overwritten or retried**; select a new unused target after review.

`mingleadmin` is the default login ID; `--login-user-id` and optional
`--local-host-id` allow explicit valid IDs. Otherwise the local Host ID is
derived from the new SQLCipher file's random header salt (an identifier,
**not a Host authorization token** and not a recovery operation ID). The
SQLCipher key and account login password must be **different**. The
administrator may provide the account secret using `--login-password`,
`--login-password-file`, `MINGLEFIELD_LOGIN_PASSWORD` or the
`login_password` / `login_password_file` fields in version-3 config.
The bounded `--secrets-stdin` JSON accepts `login_password` alongside
`new_db_password`, in one frame. Config version 3 also accepts
`login_user_id`, `local_host_id` and `confirm_local_admin`; CLI flags
override matching fields without silently resolving conflicting secret
source types.

The **private worker**, not the CLI, creates the local account's password
verifier and Host owner/operator records using the canonical Alpha
authorization/Host policy. It grants **no remote Host authority** and
requires no legacy invitation code for this narrowly approved first run.
The GUI retains its independent same-session current-copy and installation
permit before invoking the **same** shared Rust worker launcher. For an
explicitly selected post-first-run test, the GUI and CLI now also share
`installer-core::native_application_probe`: the native starter must be a
regular file in the verified managed inventory, and its real SQLCipher-backed
loopback start is checked with a private stdin key frame. The probe exits
without launching a browser, keeps no installer process running, and creates
no additional Host authority. A failed post-provision probe does not erase
the newly initialized Host or permit first-run replay.

Successful completion reports `local_host_admin_created`, with
`application_files_installed=true` and
`encrypted_database_created=true`. Without the optional native probe,
`native_application_launch_enabled=false`. Add
`--verify-native-start` **only alongside** the approved fresh
`--setup-local-host` operation to launch the inventory-bound installed
`Minglefield` binary, verify its SQLCipher-backed loopback readiness and
stop it without opening a browser. The CLI forwards the new database
password over the existing private JSON stdin protocol, not on the child
process command line. A successful requested probe reports
`native_application_launch_enabled=true`; it does **not** keep the
application running or establish complete GUI/silent installation acceptance.
The flag is rejected without the fresh first-run operation, and a missing
native executable is rejected before new installation writes. A failed
post-setup launch probe leaves the already-created files, encrypted database
and Host unchanged for manual inspection; first-run is never replayed.

This operation may be invoked non-interactively, but **all required
consents and distinct credentials must be supplied**;
`--silent --defaults` never invents a login password. No complete
end-user desktop or portable Setup Manager acceptance is implied.

## Unfinished required CLI parity

The **binding Bee-like credential contract** is documented in
[the installer phase](../docs/MINGLEFIELD-INSTALLER-AND-ONBOARDING-PHASE.md#binding-target-bee-style-cli-and-unattended-credential-configuration-approved-2026-11-07):
CLI values, password files, administrator-authored configuration, environment
variables, prompt and private stdin. Noninteractive sources are implemented
for the focused SQLCipher verification/copy and fresh local Host CLI path;
the optional native launch probe is shared with the Tauri GUI. **Still
unfinished:** interactive CLI password prompts, migration of an existing
user database as part of one complete installation transaction, a persistent
application launch/desktop UX after setup, full Standard/Advanced/silent
parameter parity, and manual native end-user acceptance. A verified probe
is not a persistent running application and never replaces account login.
Do not infer complete M2.11 acceptance from green focused CI. The CLI,
Tauri UI and independently launched Minglefield application must continue
to respect existing Host ownership and the single versioned config contract.

The next Alpha accepts **prebuilt official OS application packages**; a later
mandatory installer expansion will also execute complete native builds from
the official repository or a compatible user-selected fork, using the chosen
source's versioned build template and declared dependencies.
