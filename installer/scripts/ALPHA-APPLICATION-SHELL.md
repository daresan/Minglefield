# M2.09 — independent managed Alpha shell development adapter

**Status:** developer/CI entrypoint only. This is not the finished native
`Minglefield.exe`, Linux application, macOS `Minglefield.app`, or the headless
Setup Manager installer CLI. No user is expected to install Python or enter
shell commands to start a released Minglefield application.

From the repository's `installer/` directory, using an explicitly selected
developer Python 3.11 environment and a disposable test database:

```sh
python -B scripts/build_managed_alpha_runtime.py --output /absolute/new-managed-alpha
python -B scripts/alpha_application_shell.py --installation /absolute/new-managed-alpha --database /absolute/existing-encrypted.sqlite3 --verify-only
python -B scripts/alpha_application_shell.py --installation /absolute/new-managed-alpha --database /absolute/existing-encrypted.sqlite3
```

The **build** command downloads pinned platform-specific CPython, SQLCipher
and audited application dependencies, verifies them and smoke-tests a real
SQLCipher/Host/login process in disposable fixtures. The output path must not
exist. The **verify-only** command checks the installed managed inventory and
that a selected existing DB has an encrypted header; it does not test the
password or claim trusted publisher provenance.

The **launch** command prompts for the SQLCipher key without echo, sends it
directly to the existing `application/server/installed_alpha_launch.py` process
through an anonymous stdin pipe, opens the local web UI at its verified
127.0.0.1-only port, and shuts down with the invoking shell. It does **not**
provision/reassign Host rights, reset any user or token, migrate/re-encrypt the
DB or depend on a running Setup Manager. No password argument/environment
variable or plaintext key file is accepted. It requires an interactive
terminal for the development adapter; a later native application provides
an application-owned graphical key prompt.

**Security and acceptance boundaries:** the self-declared runtime manifest
and hash inventory detect local changes but do not establish publisher
identity. Release packaging must bind a verified digest to an independently
built native app. M2.09 developer-shell green CI is not M2.10 native
application acceptance and not M2.11 GUI/headless installation parity.
The source-build mode from official or compatible user-fork templates remains
a **mandatory later installer capability**, not an implied source execution
by selecting a DB or checkout for inspection.
