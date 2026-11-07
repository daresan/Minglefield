# M2.08 — authorized local Host administrator and real Alpha application files: single portable acceptance build

**Gate:** 2026-11-07; the M2.08 user-visible implementation and its focused native Windows/Linux/macOS checks have finished. The existing single milestone marker is updated **only now**, after CI, not on an ordinary code commit.
**Branch:** `feat/game-integration-updates`.
**Last verified implementation/documentation HEAD before marker update:** `5462af840637eb12a23baa5426ce43f9165666d6`.
**Actual packaging source:** the new marker commit itself (all three platforms must check out its exact SHA).
**Build workflow:** `.github/workflows/installer-portable-milestone.yml`, invoking the existing `installer-tauri-packaging.yml`. Do not create or trigger another packaging workflow.
**Artifacts:** directly runnable Windows Setup Manager EXE **plus its sibling managed-alpha folder**, portable Linux AppImage and runnable macOS application zip (not an installer of the Setup Manager). The bundled Alpha application includes pinned Python 3.11.18, SQLCipher 0.6.4, exact runtime dependency wheels, Minglefield application code and standalone README + GPL license. No system Python, Conda, Node or Cargo should be required merely to start the Setup Manager.

## Verified engineering evidence before this build

- [Ubuntu installer Rust checks — 42320729192](https://github.com/daresan/Minglefield/actions/runs/42320729192): **success**, including real managed-Python + SQLCipher Alpha process, actual HTTP login/Hosts/Games, locally authorized first-run worker and source/backup isolation fixtures.
- [Windows + macOS native security checks — 42320729241](https://github.com/daresan/Minglefield/actions/runs/42320729241): **both success**, checking actual per-OS managed binaries, isolated first-run/replay rejection, and no remote Host grant.
- [MAP/Python Conformance — 42319929885](https://github.com/daresan/Minglefield/actions/runs/42319929885): **success** for existing database integration and first-run tests.
- [Installer GUI frontend checks — 42320390401](https://github.com/daresan/Minglefield/actions/runs/42320390401): **success**, including independent application-file installation approval, editable `mingleadmin`, separate login password and UI rejection of unexpected response authority.
- [Tauri native full three-OS checks — 42320859781](https://github.com/daresan/Minglefield/actions/runs/42320859781): **Ubuntu, Windows and macOS success** for compiled Tauri code and unit tests at `dda30f7a27ca06508beee8bf7622b0b6d55298b0`.
- [AGENTS security guard — 42320859780](https://github.com/daresan/Minglefield/actions/runs/42320859780): **success**.

These are engineering CI results, **not** portable packaged-GUI acceptance. Require the new packaging run to report all three jobs successful **and** actually uploaded artifacts with expected contents before asking the maintainer to test. The same signed-off code path must be present on all OSes.

## M2.08 manual acceptance (disposable source/backup and NEW paths ONLY)

1. Extract/launch the portable Setup Manager on Shadow without installing the manager. For Windows keep `minglefield-installer-gui.exe` and `managed-alpha/` siblings from the **same** workflow artifact. Confirm offline GNU GPL and the Minglefield README display correctly; verify all six wizard steps and Standard/Advanced modes still work.
2. Use a **disposable** existing Alpha SQLite database with a separate real verified backup. Never use a production DB in this milestone. Run the existing full-data migration review, temporary encrypted SQLCipher copy test, and the explicit `CREATE EXPERIMENTAL ENCRYPTED COPY` action to a **previously unused absolute destination filename**. Source and independent backup must remain unchanged. Record operation ID without credentials or private paths.
3. Review the install destination (must be a new **unoccupied** directory). Type the separate `INSTALL MINGLEFIELD ALPHA FILES` confirmation and choose **Geprüfte Alpha-Anwendungsdateien installieren**. Expect exactly the files-only native completion response; there must be **no** automatic Host claim or application start. Check new directory contains Python, SQLCipher, `application/server/installed_alpha_launch.py`, private `installed_alpha_first_run.py`, README and GPL.
4. For the first local Host, accept proposed editable login name `mingleadmin` (or another unused safe local ID), choose a **different** login password than the SQLCipher destination password and repeat it. Explicitly check the local Host setup consent and run **Lokalen Host und Administrator einrichten**. Expect only `local.<verified-operation-id>` Host ownership; no invitation, console bootstrap token, global admin or remote Host privileges. Passwords must not appear in status output or logs. The old source database/backup and imported users/Host ownership must be preserved.
5. Negative cases on separate disposable fixtures: no staged database/app install, missing explicit consent, mismatched/short login password, password identical to SQLCipher, wrong database key, repeated first-run action, preexisting `mingleadmin`/Host conflict, occupied install target. Each must deny without overwriting the original/backup or granting remote Host rights. Do not try to reuse an occupied/partly completed output; select another fresh target if an operation was interrupted.
6. After closing/relaunching the manager, no previous *unconsumed* local first-run permit must still be available; a successful Host admin remains saved in the new encrypted DB. The encrypted Alpha process's actual login/Host/Game persistence has separate automated evidence. The Setup Manager **does not yet launch** the installed application; that is the next milestone's user-visible acceptance.
7. Verify on Linux and macOS that the same portable GUI starts directly and that its managed resources are really bundled. A green packaging job alone is not manual desktop acceptance.

## Security limits and next work

- First-run authorization is a **single-use, same-Setup-Manager-process proof** of the newly created encrypted DB copy and native installed application files. Entering an arbitrary path/password in Tauri IPC cannot create a Host. Native and Python layers validate independently; no HTTP provisioning route exists.
- SQLCipher key and separate Minglefield sign-in password enter the private first-run worker through stdin; neither is accepted from persistent runtime config, command-line options or environment variables.
- Installation and account activation are **not** an update/repair operation. No overwriting existing application directories, occupied database targets, receipts or credentials. No auto-recovery/rollback is authorized; M2.07 deeper crash recovery remains deferred at maintainer direction.
- The runtime/source-file checksum inventory is artifact **integrity**, not a publisher signature/release provenance claim. No Apple signing/notarization requirement is introduced.
- **Completed slice to test:** usable portable Alpha app-files installation + local first-run `mingleadmin` Host activation. **Still open:** new empty encrypted DB from scratch, installed application launch in the native manager, update/repair and user-observed three-OS acceptance; no full GA release.
- Do **not** merge, publish or mark the next milestone accepted without independent maintainer feedback. Do **not** trigger additional portable packages for ordinary development changes.
