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

