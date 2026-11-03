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

## Next Gate 1 verification tasks

1. Traverse nested `sdk/`, `services/`, `integrations/`, workflows and packaging metadata; enumerate actual Python runtime imports and optional import boundaries. Compare with declared requirements.
2. Trace local login/session creation and claim request validation to specify a one-time provisioning handshake without weakening authentication.
3. Verify all Host settings currently available in UI/API versus promised installer Advanced fields; record missing fields explicitly.
4. Identify current release/version metadata, update APIs, filesystem/data migration strategy and relevant regression tests.
5. Complete the matrix with specific acceptance criteria; **then** proceed to Gate 2 framework evaluation.

No production installer, full dependency closure, platform signing plan, or clean-machine test is claimed.
