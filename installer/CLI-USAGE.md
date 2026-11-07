# Minglefield installer CLI — current executable contract (M2.11 in progress)

The headless CLI and the Tauri GUI now use the **same**
`installer-core::managed_alpha_install` Rust implementation to validate a
managed Alpha file inventory and copy exactly its declared files. The headless
CLI operation is **currently file installation only**. A successful result
does **not** mean database migration, database creation, local Host setup,
application launch or a finished Minglefield OS-native product. Those are
separate, pending M2.09–M2.11 integration steps.

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

## Unfinished required CLI parity

The **binding Bee-like credential contract** is documented in
[the installer phase](../docs/MINGLEFIELD-INSTALLER-AND-ONBOARDING-PHASE.md#binding-target-bee-style-cli-and-unattended-credential-configuration-approved-2026-11-07):
CLI values, password files, administrator-authored configuration, environment
variables, prompt and private stdin. These inputs, native app startup,
SQLCipher migration/new-db creation and first Host/account setup **are not yet
implemented in the Rust CLI**. Do not infer a complete unattended installation
from the working file-copy action. The eventual CLI, Tauri UI and native
Minglefield application must use the same versioned installation/config
contract and respect existing Host ownership.

The next Alpha accepts **prebuilt official OS application packages**; a later
mandatory installer expansion will also execute complete native builds from
the official repository or a compatible user-selected fork, using the chosen
source's versioned build template and declared dependencies.
