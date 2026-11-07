# Native Minglefield Alpha application — M2.09/M2.10 implementation slice

**Status (2026-11-07):** Native OS executable and real bundled runtime
startup are implemented and Ubuntu CI tested; Windows/macOS native CI
acceptance is pending. **Not a finished user-facing M2.10/M2.11 release.**

## What was built

The separate \`Minglefield\` Rust binary (on Windows \`Minglefield.exe\`)
is produced from \`installer/crates/installer-cli/src/minglefield_app.rs\`.
It is a different entrypoint from \`minglefield-installer-cli\` and does
not require the Setup Manager, a running installer process, user-installed
Python, Conda, Git, Cargo, or a source checkout at application launch.

The single developer/CI command for this OS-native application package is:

```sh
cd installer
python -B scripts/build_native_alpha_application.py --output /absolute/new-native-minglefield
```

The **build machine**, not the end user's machine, uses Rust and Python to
compile the OS-native executable and assemble exact pinned CPython 3.11,
SQLCipher, audited package dependencies and the existing Alpha application.
All managed files, **including the native binary**, are SHA-256 inventoried.
The native application manifest records the binary and the OS-specific
runtime paths. An unrecognized, missing or modified managed file prevents
application launch. At this stage the inventory hash is self-declared in
the package and is **not** a publisher signature.

Windows places \`Minglefield.exe\` at the package root. Linux and macOS
currently place \`Minglefield\` at that root; Linux desktop packaging and
the macOS Finder \`.app\` bundle/signing remain separate M2.10 tasks.
The runtime directory and its managed files must remain together.

## Direct native launch, without the installer

For an **existing, individually owned encrypted Alpha database** that has
already completed normal first-run account initialization:

```sh
# On Windows PowerShell (inside the installed application directory):
.\Minglefield.exe --database "D:\private-data\minglefield.db" --db-password "owner-chosen-key"

# On Linux/macOS (inside the installed application directory):
./Minglefield --database /absolute/private-data/minglefield.db --db-password 'owner-chosen-key'
```

The administrator may supply the SQLCipher key using \`--db-password\`,
\`--db-password-file\`, \`MINGLEFIELD_DB_PASSWORD\`, a full version-3
installer-compatible \`--config\` text file, or \`--secrets-stdin\` with a
bounded \`{"db_password":"..."}\` JSON frame. If the owner **chooses** to
provide a file called \`minglefield.conf\` next to the executable, the
application loads that version-3 configuration automatically. The
installer never generates a plaintext-password config by default.
As with the approved Bee-style contract, owner-supplied argv, environment,
configuration files and password files are permitted but do not appear in
Minglefield-generated logs, readiness messages or error diagnostics.

The executable validates its own inventory and the encrypted database
using the shared Rust SQLCipher inspection, then starts the existing
\`application/server/installed_alpha_launch.py\` worker via a **private
stdin request**, entirely inside the installed runtime. It refuses
plaintext/invalid databases and does **not** create, claim or reset any
user/Host. The worker must return exactly the approved loopback readiness
frame for \`127.0.0.1\`; the remote Host claim bootstrap remains disabled.
The native app then opens the installed Alpha web UI in the OS browser.
The user still logs in normally with a **separate account password**.

Developer/CI-only checks: \`--verify-only\` validates inventory and
SQLCipher key without launching the gateway; \`--probe-exit --no-browser\`
starts and probes the gateway over 127.0.0.1 and stops its worker before
exiting. The cross-OS integration script
\`scripts/verify_cli_local_setup.py --package <managed-root> --require-native\`
installs the real package, creates a **disposable** encrypted DB/Host,
verifies normal and invalid login credentials, launches the native
executable, checks its loopback contract, restarts using an
owner-authored config, refuses setup replay and refuses tampered app
payloads. It does not access private user DBs.

## Remaining required product acceptance

The default double-click UX still lacks an application-owned **graphical
SQLCipher password prompt** and database chooser when there is no
owner-provided config. The current native binary is a first real native
execution target, **not** the final desktop user flow. macOS \`.app\`,
Linux desktop packages, application process shutdown/restart UX, publisher
signature/release integrity, independent portable artifacts, GUI/silent
installer integration and installed-user acceptance on Shadow remain
unfulfilled. The official/fork source-build mode remains a mandatory
**later** installer expansion. None of these gaps grants permission to
bypass database ownership or the original Host-first-run policy.
