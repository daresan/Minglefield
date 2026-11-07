# Minglefield installer CLI — current executable contract (M2.11 in progress)

The headless CLI and the Tauri GUI now use the **same**
`installer-core::managed_alpha_install` Rust implementation to validate a
managed Alpha file inventory and copy exactly its declared files. The headless
CLI now exposes **four separate, executable actions**: verified file
installation, read-only encrypted database verification, reviewed encrypted
database copy, and creation of a fresh SQLCipher database. They are not yet
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
step. \`--new-db-password-file\`, \`MINGLEFIELD_NEW_DB_PASSWORD\`, administrator-
authored version-3 \`new_db_password\` / \`new_db_password_file\` and bounded
\`--secrets-stdin\` can supply the new key; the exact approval is also available
as version-3 \`confirm_new_db\`. This is not yet a full installer transaction.

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

## Unfinished required CLI parity

The **binding Bee-like credential contract** is documented in
[the installer phase](../docs/MINGLEFIELD-INSTALLER-AND-ONBOARDING-PHASE.md#binding-target-bee-style-cli-and-unattended-credential-configuration-approved-2026-11-07):
CLI values, password files, administrator-authored configuration, environment
variables, prompt and private stdin. **The noninteractive credential sources
are now implemented for the focused SQLCipher verification/encrypted-copy
actions**, not for every future application/installer operation. Interactive
prompt, local Host/user initialization and verification against the newly
created database, a separately launched native app, and end-to-end silent
installation **remain unfinished**. Do not infer
the complete acceptance from a successful file-copy or encrypted-copy
action. The eventual CLI, Tauri UI and native
Minglefield application must use the same versioned installation/config
contract and respect existing Host ownership.

The next Alpha accepts **prebuilt official OS application packages**; a later
mandatory installer expansion will also execute complete native builds from
the official repository or a compatible user-selected fork, using the chosen
source's versioned build template and declared dependencies.
