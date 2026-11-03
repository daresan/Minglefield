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

## Next Gate 1 verification tasks

1. Traverse nested `sdk/`, `services/`, `integrations/`, workflows and packaging metadata; enumerate actual Python runtime imports and optional import boundaries. Compare with declared requirements.
2. Trace local login/session creation and claim request validation to specify a one-time provisioning handshake without weakening authentication.
3. Verify all Host settings currently available in UI/API versus promised installer Advanced fields; record missing fields explicitly.
4. Identify current release/version metadata, update APIs, filesystem/data migration strategy and relevant regression tests.
5. Complete the matrix with specific acceptance criteria; **then** proceed to Gate 2 framework evaluation.

No production installer, full dependency closure, platform signing plan, or clean-machine test is claimed.
