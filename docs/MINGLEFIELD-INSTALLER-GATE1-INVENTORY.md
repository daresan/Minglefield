# Minglefield Installer — Gate 1 repository inventory (in progress)

Status: source-backed architecture inventory; **not** a completed dependency audit, packaging decision or implementation. Branch: `feat/game-integration-updates`. Scope is product interfaces, **not** the developer's personal environment.

## Verified repository structure and entry points

- Root contains `server/`, `scripts/`, `sdk/`, `services/`, `apps/`, `integrations/`, `requirements-ci.txt` and GitHub Actions workflows. Root inspection did **not** reveal a top-level `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt`, or a prebuilt platform installer. This is not proof that no nested packaging metadata exists.
- `apps/README.md` identifies graphical universe clients as future scope; the existing browser Alpha UI is embedded in `server/private_alpha_gateway.py`.
- Current Python reference entry point is `server/private_alpha_gateway.py:run_local()`; it uses `ThreadingHTTPServer` on `127.0.0.1:8767` by default, starts `AlphaAuthStore` and `HostCommitPolicy`, and prints a local bootstrap code. Its own banner says local simulation only. This is **not** a supported production desktop launch contract.
- `scripts/minglefield_environment.py` requires an existing Python 3.10+ interpreter and creates a venv; optional `--install-ci` installs only `requirements-ci.txt`. `scripts/minglefield_platform_preflight.py` is Python-dependent and read-only. Neither is a self-starting GUI installer.
- `.github/workflows/map-conformance.yml` sets up Python 3.11 and installs `requirements-ci.txt` for conformance tests. It is **not** a release-packaging or installer-build workflow. Existing `game-install*` workflows concern third-party game integration and must not be mistaken for platform installation.

## Verified Host and local authorization boundaries

- `server/private_alpha_gateway.py` exposes `/api/host/claim`, `/api/host/settings`, `/api/host/runtimes`. Claim requires an authenticated principal plus local bootstrap proof; the bootstrap is generated per gateway start and printed to console. The current mechanism is not a one-time, installation-bound installer handshake.
- `server/sec01_host_commit_policy_sim.py` persists owners, settings and runtime configurations in `sec01_host_owners`, `sec01_host_settings`, `sec01_host_runtimes` SQLite tables. `claim_local_host()` refuses a different existing owner and is idempotent for the same owner. Installer provisioning must reuse this authority boundary, not write directly to tables.
- The existing Host settings API accepts only the current validated fields; the full installer settings UX must be mapped against actual Host API capabilities rather than assuming all advanced settings are already supported.
- Current ComfyUI runtime validation is loopback-only. Only the official standard ComfyUI distribution may be optionally installed; **no** additional models, custom nodes, extensions, workflows or imports.

## Installation discovery and data separation

- Windows default new installation: `%LOCALAPPDATA%\\Programs\\Minglefield` for app binaries, user scope without elevation. Persisted data is separate, currently `%LOCALAPPDATA%\\Minglefield\\alpha.sqlite3` in the Alpha gateway.
- Existing app discovery searches OS-standard per-user/system locations, registrations and user-selected directories; must recognize **source-only checkouts** and **packaged-executable-only installations** independently.
- `default_alpha_database()` currently uses `~/.local/share/Minglefield/alpha.sqlite3` on all non-Windows systems. macOS application-support directory policy is **not yet implemented** and needs explicit lifecycle design.
- Existing Minglefield installations and persistent data must not be overwritten by detection or by repair/update.

## Gap and compatibility matrix

| Area | Existing evidence | Missing before implementation |
| --- | --- | --- |
| Windows / macOS / Linux packaged launch | Python Alpha gateway only | Stable product launch contract and OS-specific signed package layout |
| Standalone GUI installer | None established in inspected root/scripts | GUI and distribution framework evaluation |
| Runtime dependency declaration | `requirements-ci.txt` only covers conformance | Complete, versioned runtime manifest and per-release resolution/validation |
| Source checkout detection | Recognizable repo structure | Version/provenance checks and explicit runnable/not-ready classification |
| Executable-only detection | No release executable contract found in inspected root | Product metadata, signature/integrity and platform architecture verification |
| Local Host onboarding | Existing authenticated claim + owner persistence | Single-use, installer-bound, authenticated local provisioning |
| Host runtime configuration | Existing SQLite owner-scoped APIs | UI field coverage, defaults, migration and optional ComfyUI discovery |
| Update and recovery | Platform-update UI currently informational placeholder | Verified release source, transactional update, rollback and data retention |
| CI | Python conformance workflow exists | Per-release installer builds and clean-machine launch tests on all three OSes |

## Gate 1 dependency pass — confirmed source imports (partial, 2026-11-03)

Branch-aware inspection of `server/private_alpha_gateway.py`, `private_alpha_auth.py`, `private_alpha_delete.py`, `sec01_integrated_alpha_admission.py`, `sec01_host_commit_policy_sim.py`, `host_runtime_config.py`, `comfy_workflow_inspection.py`, `game_job_attachments*.py`, `staged_comfy_assets.py`, `action_service.py`, `sqlite_policy_engine.py`, and relevant game integration modules shows extensive Python-standard-library usage. The inspected source also proves **non-stdlib imports in reachable feature modules**:

| Distribution | Evidence in product code | Classification pending package boundary |
| --- | --- | --- |
| `jsonschema` | `server/game_integration_registry.py`, `server/game_integration_lock.py`, `server/game_package_lock.py` import `Draft202012Validator` | Required when integration registry / lockfile validation is included; do not silently treat as test-only |
| `packaging` | `server/game_integration_updates.py` imports `packaging.version.Version` and `InvalidVersion` | Required when integration update discovery is included; distinct from Minglefield platform update |

Current constraints in `requirements-ci.txt`: `jsonschema>=4.18,<5`, `packaging>=24,<27`. They are **not pinned runtime locks**. The local Python 3.10+ floor is documented for the reference gateway; CI runs Python 3.11. Resolve/test supported versions per OS rather than assuming these constraints alone establish cross-platform compatibility.

Directory inspection: `sdk/` and `services/` currently contain README files only; `apps/` contains README only. No executable product client was found in those directories. This **does not** establish a complete distribution architecture.

### Build-time dependency policy proposed for Gate 2 review

1. Declare explicit product runtime requirements separately from conformance/development dependencies. Mark feature-dependent optional extras only when packaging and feature isolation truly permit it.
2. Perform static import checks **and** isolated clean-environment startup / exercised-feature tests. Static imports alone miss dynamic imports and optional code paths.
3. Resolve reproducible OS/Python-specific locks and verify artifact integrity/provenance for each release. Fail installer builds for unresolved or undeclared required imports.
4. Avoid requiring Git, Conda or system Python on a clean end-user machine; do not modify preexisting user environments without consent.
5. Maintain strict separation: game-integration install/update modules and their CI workflows do not implement Minglefield platform installation or updating.

**Still unverified:** exhaustive import closure across every module, runtime-vs-optional feature reachability, complete transitive dependencies, OS packaging/signing, release executable metadata, macOS data location, and clean-machine tests. These are explicit open checks, not assumed successes.

## Gate 1 authentication and Host settings interface audit (2026-11-03)

### Verified Alpha authentication path

- `private_alpha_auth.py:redeem()` exchanges a valid unredeemed invitation for a persisted, expiring session; `login()` issues a session after password verification. `principal()` checks the bearer token against a nonrevoked, unexpired session and an enabled user; `revoke_session()` and `disable_user()` invalidate sessions.
- The gateway's `/api/redeem`, `/api/login`, and `/api/password/set` routes are loopback/Origin/Host constrained and locally throttled; the current UI stores the bearer token only for the browser tab. The current gateway explicitly remains **local simulation only**.
- `/api/host/claim` requires the existing authenticated principal plus a loopback/Host/Origin check and comparison against a bootstrap secret generated on **gateway startup**, then delegates to `HostCommitPolicy.claim_local_host()`. The secret is printed to the console and **not consumed on success**. It must not be reused unchanged for silent installer onboarding.
- `claim_local_host()` atomically checks enabled owner, existing ownership and executor operator binding; it rejects takeover and is idempotent for the same owner. Installer must call an authorization-preserving service path, not write SQLite ownership rows directly.

### Actual Host configuration coverage

| Host control | Current verified interface | Installer requirement / gap |
| --- | --- | --- |
| Owner/claim | `/api/host/claim` + `claim_local_host()` | Add single-use, authenticated, installation-bound local provisioning; preserve remote claims |
| Job attachments root | `/api/host/settings` and SQLite `sec01_host_settings` | Reuse; preserve existing paths |
| Output root | Same settings API | Reuse; preserve existing paths |
| Trusted integration sources | Same settings API | Reuse; no silent trust expansion |
| ComfyUI runtime config | `/api/host/runtimes` and `sec01_host_runtimes` | Reuse host-owned configuration; optional official standard installation only |
| Rule priority / enabled / rule config | `/api/host/rules` and existing Alpha UI | Job policy only; installer must not change these rules |
| Scheduling / resource limits | Existing Host job policy, not installer configuration | Out of installer scope; do not create or change rules |
| Platform update | Alpha `platformUpdateDialog` says no verified update source connected | Separate verified Minglefield platform release/update service from game integration updates |

`HostCommitPolicy.host_settings()` currently returns exactly `job_attachments_root`, `output_root`, `trusted_integration_sources`. `save_host_settings()` rejects unknown fields; therefore installer **must not** insert scheduling, resource limits, or runtime settings into this JSON object. Use the Host runtime APIs only for installation-related connections; Host job-rule APIs remain outside installer scope.

### Security acceptance criteria for Gate 4

- Authenticated enabled user + verified local installer invocation; no trust derived from loopback alone.
- One-time, expiring, narrowly scoped proof bound to installation instance, target Host and intended principal; replay and cross-user attempts fail closed.
- Ownership conflicts remain denied and must require explicit reviewed migration.
- Existing user data and Host/runtime settings remain unchanged on failed provisioning or cancelled install.
- Tests cover login expiry/revocation, concurrent/replayed claim, wrong Host, wrong user, nonlocal caller, origin mismatch, interrupted install and reinstall idempotency.

## Gate 1 responsibility correction — installer versus Host job policy (2026-11-03)

The existing Host rules (`HostCommitPolicy.upsert_rule()`, `/api/host/rules`) govern **job admission, execution approval, scheduling and resource conditions**. They are **not installer settings**. The installer must **not** create, modify, migrate or reset Host job-approval rules as part of installation or first-run onboarding. The earlier proposal to expose these rules in installer Advanced settings is withdrawn.

Installer scope: application installation and discovery, runtime dependency provisioning, update/repair/uninstall, and minimal authorized local Host registration. First-run may configure an optional Host-owned runtime connection (e.g. ComfyUI) through existing runtime APIs with consent. The Hosts UI retains exclusive responsibility for job authorization rules and execution policies.

**Release/update distinction:** `server/game_release_metadata.py`, `server/game_integration_updates.py`, and `server/game_integration_assessment_*.py` implement **game integration release discovery/assessment**; they do not constitute a verified Minglefield platform release feed. The Alpha `platformUpdateDialog` explicitly reports no verified platform update source. Platform version identity, artifact provenance, signing, migration and rollback remain new product contracts.

### Gate 1 remaining verification / Gate 2 entry conditions

- Full transitive runtime import and dynamic import audit, with executable feature boundaries and optional integration classification; source inspection so far is a partial dependency map.
- Version/build metadata and platform distribution identity contract, including source-only versus executable-only recognition.
- Stable packaged application launch, process supervision, startup failure handling, persistent data location on macOS and Linux.
- Explicit framework selection ADR comparing cross-platform GUI installers, Python embedding, per-user install, code signing/notarization, repair/update and rollback.
- CI release-build design distinct from third-party game installer workflows; isolated launch and per-build dependency verification on each supported OS.

Gate 1 is **not yet signed off**. The responsibility boundary is clarified; no installer-specific job-rule implementation is planned.

## Gate 1 product launch, platform distribution and licensing audit (2026-11-03)

### Verified launch contract versus required packaged contract

`README.md` calls Minglefield a concept/foundation project with no playable release or production SDK; `server/README.md` calls the server an experimental reference implementation, not a production server. The current Alpha launch is `python -B server/private_alpha_gateway.py --auth-db <db> --port 8767`, as documented in `docs/MINGLEFIELD-PLATFORM-SETUP-ALPHA.md`.

`run_local()` initializes `AlphaAuthStore` and `HostCommitPolicy`, generates a fresh console bootstrap secret, binds `ThreadingHTTPServer` to `127.0.0.1`, and blocks in `serve_forever()`. It does not define a desktop executable entry point, process supervisor, health/ready handshake, UI window lifecycle, or installer-safe first-run provisioning. The packaged launcher must be a **new explicit contract**, not a claim that this prototype is production-ready.

Proposed launcher acceptance contract for Gate 2 review:
- Run without installed Python, Git, Conda, PowerShell or shell commands; use packaged/managed isolated runtime.
- Resolve installed application resources separately from writable per-user state, logs, caches, optional managed runtimes and secrets.
- Bind local service to loopback only unless a separately reviewed remote service mode exists; choose/validate ports and report collision rather than silently connecting to an unrelated process.
- Establish authenticated process identity/health before opening local UI; cleanly terminate or detach according to documented lifecycle, with no orphaned untrusted privileged process.
- Provide structured startup errors, crash logs and a repair route, without exposing bearer tokens or provisioning secrets.
- Preserve existing SQLite state; require explicit backup and migration policy before schema-changing updates.
- Support source checkout recognition without confusing source detection with a packaged executable; never require Git metadata for source-only recognition.

### Platform paths and lifecycle boundaries

Windows current-user program default: `%LOCALAPPDATA%\\Programs\\Minglefield`; persistent data `%LOCALAPPDATA%\\Minglefield`. Existing gateway uses this data root for `alpha.sqlite3`. Current gateway uses `~/.local/share/Minglefield/alpha.sqlite3` for both macOS and Linux. Gate 2 must define an appropriate macOS per-user Application Support path and Linux XDG data/config/cache conventions, with backward-compatible detection and consented migration. Do not infer these from the developer's machine.

### Release and licensing blockers

- The root `README.md` explicitly states **license selection is pending** and that public visibility does not grant redistribution rights. `server/README.md` identifies AGPL 3.0 as a **candidate**, not an adopted license. Therefore a redistributable installer release must be gated on legal/licensing approval, including dependencies, Python distribution, bundler and optional components.
- The `game-install-portability.yml` and `game-installation-security.yml` workflows run conformance tests for third-party game installation modules, even on Windows/macOS/Linux. They do not build, sign, publish or smoke-test a Minglefield platform installer.
- No platform release feed, signed artifact metadata or production application version identity is established by the inspected entry points and documentation.

### Gate 2 architecture comparison criteria (no technology selected yet)

Compare a native OS-specific installer around a packaged Python launcher, a cross-platform desktop shell around a local backend, and a Python GUI/bundler distribution. Evaluate: zero-prerequisite install; Windows per-user no-elevation path; macOS signing/notarization; Linux packaging variants; trustworthy product identity; independent app/data lifecycle; update rollback; optional ComfyUI standard-only integration; security of local provisioning; reproducible per-OS dependency closure; license compatibility; maintainability and clean-machine CI.

**Gate 1 decision:** existing Alpha gateway is a useful backend reference but **not** itself a production packaged launcher. Implementation of a launcher and release identity is a prerequisite for a genuine end-user installer.

## Next Gate 1 verification tasks

1. Traverse nested `sdk/`, `services/`, `integrations/`, workflows and packaging metadata; enumerate actual Python runtime imports and optional import boundaries. Compare with declared requirements.
2. Trace local login/session creation and claim request validation to specify a one-time provisioning handshake without weakening authentication.
3. Verify only installation-related Host registration and optional runtime connection APIs; keep job policy/rules outside installer scope.
4. Identify current release/version metadata, update APIs, filesystem/data migration strategy and relevant regression tests.
5. Complete the matrix with specific acceptance criteria; **then** proceed to Gate 2 framework evaluation.

No production installer, full dependency closure, platform signing plan, or clean-machine test is claimed.

## Product decision update: first Alpha package and licensing direction (2026-11-03)

The first deliverable is an **installable package of the current Minglefield Alpha**, clearly labeled as experimental. Installer and build pipeline must be **version-agnostic**: a future version is delivered by repackaging new app/runtime artifacts with a validated release manifest, not by changing installer source for each release. `0.1.0-alpha.1` is only a candidate version.

The user has chosen a Blender-like GPL open-source direction. **Proposed** Minglefield core SPDX identifier: `GPL-3.0-or-later`; this is not the same as claiming Blender's exact license is GPL-3.0-or-later. A license file is **not yet present** in the inspected branch; do not claim one has been applied. Before distributing binaries, audit ownership and all bundled third-party components, then publish actual license and notices. Keep marketplace/service transaction fees distinct from GPL software freedoms: the existing 5% revenue policy cannot be an extra condition on redistribution/use of GPL code.

**Revised sequencing:** prototype packaging of the current Alpha now; Gate 2 selects a reusable package format, launch wrapper, release metadata and GUI installer technology; production hardening is a later milestone, while installer-specific security (especially Host provisioning and update integrity) remains a prerequisite for installation release.


## Marketplace scope and 5% fee clarification (2026-11-03)

**Binding project decision:** The 5% commission applies **only to transactions actually conducted through the future official Minglefield Online Community Marketplace**. It is **not** a license royalty, a framework-wide commerce levy, or a condition for using, modifying, distributing, self-hosting or commercially exploiting GPL-covered Minglefield code.

The official online Marketplace is **planned, not implemented, and not part of this repository or the first installable Alpha package**. No Marketplace backend, marketplace transaction fee enforcement, billing or operator-right restrictions are to be added to the installer or GPL core as part of this phase.

The project founder intends to **reserve operation of the official Minglefield Online Community Marketplace** for themselves for now, to the extent legally available. Distinguish rights in the official service's name/branding, domain, infrastructure, operator accounts, contracts and any separately developed proprietary service code from the GPL rights in the open-source core. Do **not** assert that GPL licensing prohibits third parties from building or operating independent compatible marketplace services. Trademark/service terms, ownership and competition-law implications require jurisdiction-specific legal review.

Future Marketplace terms may specify a 5% commission on transactions processed by that service, with transparent pricing and contractual acceptance. This is outside the current installer, repository distribution and runtime dependency closure.

