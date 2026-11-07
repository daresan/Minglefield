# Minglefield Platform Installer & First-Run Onboarding — active next phase

Status: **approved priority; Tauri 2 and experimental M2.06–M2.08 slices implemented, M2.08 manual acceptance FAILED/pending, M2.09–M2.11 unaccepted** (updated 2026-11-07). Historical requirements below retain their original approval dates.
Scope: installing, configuring, launching, updating and recovering **Minglefield itself**, not installing third-party games. This phase takes precedence over unfinished roadmap features; previous work remains planned and is sequenced after this phase, except blocking security fixes and prerequisites.

## Product outcome and acceptance target

A first-time, non-technical user can download an OS-appropriate graphical installer, choose a destination, install Minglefield and its necessary runtime, provision the **computer running the installer** as their local Host, configure optional runtimes, and launch Minglefield without knowing Python, Conda, Git, shell commands, or environment variables. Aim for **at least 80%** of representative first-time target users completing defined core onboarding tasks unaided. This is a **target**, not a measured achievement; establish task definitions, test participants, observations and completion criteria.

Support Windows, macOS and Linux with self-starting installers that require no preinstalled Python/Conda. Use **one shared cross-platform installer GUI** with platform-specific distributable builds. **Tauri 2 and directly runnable Windows EXE, Linux AppImage and macOS app are the adopted portable approach**; historic exploration requirements below are not still-open toolkit decisions.

## Installer journeys

- **Standard:** safe OS-specific defaults, clear progress, minimal choices, automatic detection, install/reuse required Python runtime, local Host creation, launch.
- **Advanced:** destination and data locations, detected installations and manual path selection, Python/Conda/ComfyUI options, installation and connection options, local Host registration, and optional Host-owned runtime configuration; job authorization/scheduling rules remain exclusively in Hosts. All installer-set Host settings remain visible/editable in Minglefield's existing Hosts UI.
- **Existing installation:** detect and offer safe reuse/repair/update without silently replacing an existing environment, Host ownership, settings, SQLite database, user data, or unrelated files.
- **No installation detected:** provision the local Host during first run; do not require the user to manually copy or enter a Host claim token.

## Shared GUI and unattended CLI installation (binding decision, 2026-11-03)

- One Tauri 2 cross-platform installer GUI codebase for Windows, macOS and Linux, with verified OS/architecture-specific portable artifacts (Windows executable, Linux AppImage, macOS application). Apple signing/notarization is **out of current scope**, per the portable-manager decision; never treat it as an acceptance blocker.
- The same installer application must also start from a terminal with documented parameters, including `--silent`, `--config <path>`, and `--defaults` (proposed CLI spelling), with a versioned default configuration and explicit overrides. GUI and CLI call the **same installation engine**, validation, trust checks, lifecycle and Host APIs; no duplicate or weaker headless installation path.
- Unattended mode has no interactive prompts, uses deterministic exit codes, machine-readable result/log output, supports idempotent re-runs, and fails safely when required consent, ownership proof, credentials, network access or conflict resolution is missing. Never infer consent for optional Conda/ComfyUI or destructive data actions from `--silent` or `--defaults` alone.
- Default configuration contains no credentials, tokens, or machine-specific paths. Resolve OS-specific install/data defaults at runtime. Distinguish unattended **application installation** from account-authenticated local Host provisioning: missing authenticated authorization may defer provisioning to first-run GUI, but must never silently claim a Host.
- Add focused tests for GUI/CLI config parity, precedence and validation, headless non-interactivity, exit codes, missing authorization/consent, no unexpected optional components, and per-OS packaged entrypoint behavior.

## Windows installation destination (binding default)

For Windows, the **default installation scope is current-user only**, without administrator privileges. Install application binaries under `%LOCALAPPDATA%\\Programs\\Minglefield` (or the OS-recommended per-user application location when packaging requires it); keep persistent application data separately under `%LOCALAPPDATA%\\Minglefield` or an explicitly versioned user-data location. Never use `Program Files` as the default destination, modify system-wide Python/Conda installations, or request elevation for the standard path. A user-selected custom destination remains supported, with explicit permissions checks. Discovery must still find **existing** Minglefield installations in system-wide locations, even though new installs default to per-user scope. Uninstall must not silently delete persistent user data.

## Existing Minglefield discovery — platform defaults and manual location

On Windows, macOS and Linux, search the operating system's standard application installation locations and applicable installation registrations/metadata, including system-wide and per-user locations. Do not assume the developer's personal directory structure, shell PATH, or Conda setup. The user can always browse to a **custom directory**, especially when automatic discovery finds nothing or misses the intended installation.

Classify both supported input forms independently:
- **Source checkout:** a directory containing only a cloned Minglefield repository (or source tree). Recognize using validated project-specific structure/metadata; do not require an existing executable, Python environment, or even `.git` metadata. Detect version/source identity where possible and report unknown provenance honestly.
- **Packaged application:** a directory containing only the platform-specific Minglefield executable or application bundle, with no repository. Recognize via platform-appropriate application metadata and verifiable product identity, not executable filename alone; validate architecture, platform, version and integrity/signature when applicable.
- **Both forms present:** detect both, distinguish them in the UI, and let the user choose the intended target. A recognized source checkout may still need provisioning before it is runnable; detection is not proof of launch readiness.

Never silently overwrite or relocate a discovered installation or change its user data. Treat manual path selection as a normal supported flow, not an exceptional developer workaround. Maintain clear separation between detecting a Minglefield application, choosing an installation target, and discovering optional Python/Conda/ComfyUI runtimes.

## Component acquisition and discovery

For **Python, Conda and ComfyUI**: search known platform-specific locations, verify compatibility and actual functionality, offer user-selected directory/executable as a fallback, and offer a clearly disclosed automatic installation if absent. Explicit consent is required for optional/heavy components. The installer must explain source, version, destination, approximate size and consequences; verify downloaded artifacts and trusted release provenance before execution. Handle unavailable network, cancellation, incomplete installation, upgrade, and retry without corrupting other installations.

- **Python:** mandatory runtime, preferably isolated from system Python and unrelated environments; reuse an existing compatible environment only with explicit informed selection and no uncontrolled mutation. Do not require Conda for Minglefield.
- **Conda:** optional; detect/reuse, let user locate, or install if selected. Never assume the `conda` shell command is on PATH; an installed environment may be valid without shell initialization.
- **ComfyUI:** optional, detect/reuse, let user locate, or install **only the official standard distribution** if selected; can also connect to a running instance. Runtime and integration settings are **Host-owned**, not global. The installer must **never** install additional models, checkpoints, LoRAs, custom nodes, extensions, workflows, or import workflows. Existing ComfyUI models, workflows, extensions and user data must be preserved. Remote connections require an independently reviewed authenticated and secure networking design; the current ComfyUI runtime validator only permits loopback.
- Keep package/application files, managed runtimes, and persistent user data logically separate.

## Local Host first-run security boundary

The installer knows which computer it is running on; this is **not by itself proof of authorization** to claim an account's Host. Reuse the existing authenticated Host persistence and configuration API rather than creating a second settings store or privileged bypass. Design a **one-time, narrowly scoped, locally authorized provisioning handshake** bound to the intended local installation and authenticated operator/account. The setup flow should perform the Host claim automatically, without requiring manual token entry; secrets must be ephemeral and invalidated after use, and the flow must resist unrelated local processes. Reinstall/repair must not silently seize a Host already owned by another account. Preserve the existing manual token/confirmation mechanism for **remote Host claims**.

The installer/first-run flow may register the local Host and configure only the minimal installation-related Host connection and optional runtime settings through existing authorized APIs. Host job-approval rules, scheduling, resource limits, rule priority and enablement belong to the Hosts/job-policy UI, not the installer; the installer must neither create nor modify them. The existing alpha gateway's local bootstrap code and current Host-claim route require security and persistence review **before** reuse or extension.

### Binding decision: first local Host administrator (approved 2026-11-06)

A new Minglefield installation must **automatically prepare the first local Host
administrator during the explicitly authorized first-run setup**, without
requiring a manual invitation or the current console-bootstrap-token entry.
This is not automatic ownership merely because a process runs on a computer:

- **Identity:** propose the editable login name `mingleadmin`. Create an
  ordinary local Minglefield user in the **operational encrypted database**,
  with its independently salted password verifier in the existing
  `alpha_users` / `alpha_passwords` model. A user account is not a
  Minglefield-wide superuser. Do not invent a global admin role.
- **Two independent secrets:** the SQLCipher passphrase unlocks the
  *database locally*; the separately chosen Minglefield sign-in password
  authenticates `mingleadmin`. Neither password is copied to the other;
  their values must not be identical. The sign-in password can change
  without database rekeying. The SQLCipher key must never be a remote
  login credential or a host-claim authorization token. Do not persist
  either plaintext secret in the database, plan, logs, command line, or
  installer configuration.
- **Per-Host authority:** register the new user as owner/administrator
  **only of the positively identified local Host**, using existing
  `alpha_executor_hosts`, `sec01_host_owners`, and, where warranted,
  `sec01_host_admins` associations. Being a Host owner already confers
  host-admin rights under current policy; avoid redundant global grants.
  Neither Minglefield-wide administration nor OS-level administrator
  privileges follow from the user name.
- **Existing database import:** preserve *all* existing users, password
  verifiers, sessions, delegated agents, Hosts and Host ownership.
  Do not reset a password, seize an existing Host, silently reuse an
  existing `mingleadmin` identity, or modify existing credentials.
  Identity/Host conflicts require explicit authenticated resolution,
  rather than an automatic INSERT/UPDATE/overwrite.
- **Remote Hosts:** `mingleadmin` can administer a remote Host **only**
  after an authenticated, owner-authorized, host-scoped remote claim or
  delegated Host-admin grant. Proof must bind the intended Host and
  identity, enforce expiry/single-use/revocation as applicable, and
  prevent cross-Host replay. No possession of a local database key or
  an arbitrary remote token implies global or remote ownership.
- **Provisioning trust:** installer and first-run application must use
  one authenticated **local-only, single-use** provisioning handshake
  with verified process/installation identity and explicit owner consent.
  Never expose the trusted database-creation primitive as an unguarded
  HTTP endpoint or reuse the current console secret as a permanent token.
  Setup may create the account directly in an isolated, verified encrypted
  target without an invite, but Host claim/activation must be completed
  only under that verified local authorization. On partial failure,
  roll back all first-run identity/Host writes together.
- **Unattended installation:** `--silent --defaults` must not fabricate
  an account password, consent or ownership proof. If required
  authorization is unavailable, defer the account/Host claim to
  authenticated first run, never silently elevate privileges.
- **Lifecycle:** fresh install has a clear creation path; upgrades and
  repairs are non-destructive and do not recreate accounts. A failed
  migration never alters the source or publishes a partially provisioned
  target. All first-run inserts are included in final post-migration
  verification, with no user secrets in the report.

**Current experimental M2.08 implementation (2026-11-07):** The
portable Setup Manager now performs three independently approved steps:
(1) a non-overwriting, backup-verified encrypted destination copy;
(2) a separately consented native installation of the bundled,
digest-pinned Python/SQLCipher and Minglefield Alpha application files into
a previously absent destination; and (3) a native current-session,
single-use activation of the first local Host administrator with an
independent login password and no invite token. The Rust process records
the verified database-copy operation ID and the successful application
install in a private in-memory permit. The permit is consumed once and
cannot be forged by supplying paths, keys or JavaScript booleans. The
installed private first-run Python worker reuses the atomic existing
HostCommitPolicy transaction, denies identity/Host conflicts and refuses
remote Host power. The verified original source and independent backup
remain untouched. **What is still unimplemented:** an entirely fresh
database with no source to migrate, native launch of the separately installed
application, repair/update, and end-user acceptance of a portable M2.08
build. Green engineering CI does not stand in for those product checks.

## Binding clarification — local Host preservation, application shell and M2 sequence (2026-11-07)

The portable **Setup Manager GUI**, the **headless installer CLI**, and the independently launched **Minglefield application** are three distinct interfaces. GUI and installer CLI must share the same native installation core; application shell startup is not an installer mode. M2.09 first validates the SQLCipher-backed **application process** independently of setup GUI; M2.10 packages/install-tests its runtime and adds fresh encrypted DB creation; M2.11 wires the existing GUI and actual installer CLI to the common engine. Do not reinterpret M2.09 as a second encryption pass on every launch. The first Alpha uses the verified official application package; building/installing a chosen checkout or fork is postponed. A checkout selected for data migration is **not** an executable payload.

**Fresh local Host setup:** The OS-authorized local installation creates the first local Host and editable default `mingleadmin` identity in a new encrypted database, without invite code or remote Host claim. Preserve the native, scoped, once-per-operation setup boundary; do not equate a database-copy operation ID with durable physical Host identity.

**Imported database:** Preserve all existing users, salts/password verifiers, operator and Host owner/admin assignments, local and remote Host references/grants, agents, sessions, settings and recognized data. An existing, *positively matched* `mingleadmin` plus local Host owner is already configured: no duplicate account, password change, unnecessary second Host or error. A different/unverifiable assignment needs authenticated resolution before any **change of ownership**; OS filesystem permission alone does not authenticate an imported application account. The present `HostCommitPolicy.provision_first_run_local_host_admin_trusted` only supports new identities and returns `first_run_identity_conflict` / `first_run_host_conflict` on pre-existing references; native setup currently chooses `local.<operation-id>`. Non-destructive re-recognition and persistent local Host identity remain explicitly unimplemented, without relaxing present collision protection.

**Remote Host boundary:** Preserve imported remote Host records/rights as data. Real remote discovery, remote claim/management, client-only installations and active remote-host connection acceptance belong to future **application** work and are **not** installer admission criteria. This does not authorize altering imported remote ownership.

**Current M2.08 blocker:** The latest Windows artifact [42329947124](https://github.com/daresan/Minglefield/actions/runs/42329947124) was reported to omit two hidden, zero-byte runtime inventory entries (`setuptools/_vendor/.lock`, `Scripts/.empty`) after artifact upload; all delivered members otherwise matched the pinned inventory in the previous review. The exact delivered artifact must be reverified after packaging repair. Green three-OS package jobs are not Shadow operator acceptance. Retain M2.07 Alpha fresh-target retry, source/backup protection and one-time Host consent; do not expand crash-recovery development as a prerequisite.

**Testing separation:** Native installer core/security, post-upload package inventory, independently shell-started application runtime, GUI/headless installer parity and actual OS/user acceptance are separate evidence classes. MDCI v1.0.0 controls triggers; `PORTABLE-TEST-REQUEST.md` is not changed for documentation-only commits.

## Existing repository boundaries and evidence to inspect

- `server/private_alpha_gateway.py`: current local gateway and web UI, local Host claim flow, Host settings/runtimes, and placeholder platform-update dialog; its current local bootstrap is not an installer provisioning API.
- `server/host_runtime_config.py`: ComfyUI runtime validation, currently loopback-only; the registry class is in-memory and is **not** durable storage.
- Existing host/auth persistence and API methods must be traced and reused; don't assume the in-memory registry is the persisted implementation.
- `scripts/minglefield_environment.py` and `scripts/minglefield_platform_preflight.py`: Python-dependent **developer alpha tools**, not a first-install GUI.
- `requirements-ci.txt` is **not** a complete runtime dependency manifest.
- Existing SQLite user data and configured Hosts must survive install, repair, update, and failed migration; platform update must be distinguished from game/integration updates.

## Binding owner correction: simple restart at a new target, resume real installation (2026-11-07)

The operator rejected further development of crash recovery as a prerequisite
for the **experimental/local Alpha installation**. The already verified
SQLCipher-copy design leaves the original database and the independent backup
unchanged and publishes only an explicitly selected new target without
overwriting existing files. A power cut may leave a receipt, staging file
or incomplete attempt: **do not interpret it as a successful installation,
reuse its occupied/reserved target, delete it automatically, or assume the old
target is free**. On restart the operator may choose a *different, unused
destination filename* and execute the already verified migration procedure
again after the normal backup/source/consent checks. An optional old-target
diagnostic may be useful for troubleshooting but must **never be a mandatory
preflight gate** for retrying on a fresh target.

**Execution order now:** stop extending M2.07 read-only recovery, journal,
automatic rollback or power-loss testing for speculative scenarios. Preserve
implemented recovery code and its successful tests; defer general crash-durable
recovery to the appropriate lifecycle/release work. Advance directly to
**M2.08: single-use, installation-bound authorization and first local Host
administrator `mingleadmin`**, then M2.09–M2.11 operational SQLCipher
runtime, actually installed Minglefield application payload and launch.
The separate sign-in password, owner-scoped Host authority, no-silent-claim,
replay resistance, occupied-target protection, independent verified backup,
and unchanged original data **remain mandatory**. Never treat the
database-only experimental copy as a completed Minglefield installation.

This scope correction supersedes previous M2.07-first sequencing wherever
present in earlier milestone documentation. M2.07 historic CI evidence remains
valid; its unimplemented full rollback/power-loss goals remain explicitly
deferred, not silently declared complete. No new portable testbuild follows
from this decision alone.

## M2.06 priority correction: executable migration before further hardening (2026-11-06)

**Approved development direction:** A true SQLCipher migration must be exercised
by the installer and tested on an **explicitly chosen, disposable destination**.
GitHub Actions runners can create, close, reopen and delete real fixture
databases within isolated runner workspaces. GitHub infrastructure does not
prevent such integration tests. The existing proof of encrypted staging,
full-value/schema comparison, wrong-key rejection, Rust-to-Python opening,
source preservation and exclusive temporary publication should be reused
rather than indefinitely extending standalone preflight checks.

**Next smallest end-to-end slice:** Connect the existing verified export to
an explicitly requested, **non-overwriting final filename in a controlled
test directory**; read the resulting SQLCipher file using the operational
Python runtime and confirm integrity, metadata, exact rows and unchanged
source bytes. On CI use only freshly created disposable fixtures. Test
pre-existing target collision, bad key, invalid paths and failed verification
without modifying the original or an unrelated file. Reject unattended
implicit destructive actions and ensure logs contain no credentials.

**Alpha Setup Manager acceptance:** Once the controlled file-writing path,
minimum atomic/non-overwrite and failure-safety checks, explicit user
approval, and current CI platform tests succeed, an **explicit milestone
testbuild** may expose the migration behind an unmistakable
experimental/fixture-or-backed-up-data gate. The test must be able to use
the user-selected destination path where OS permissions permit, report
exact success/failure and leave the original database intact. Before anyone
uses a non-disposable source, require an independent backup and explicit
risk acknowledgement. A portable testbuild is **not** automatic permission
to migrate a real installation or advertise general production readiness.

**Separate hardening/release gate:** Handle-relative native publication on
all supported OSs, malicious concurrent path-swap defenses, crash-durable
directory synchronization, full interruption/recovery matrix and
installation-bound first-run Host authorization remain required for the
appropriate general-release acceptance. They are not prerequisites for
proving ordinary database creation in an isolated runner or for evaluating
a clearly bounded Alpha fixture migration. Existing first-run account and
Host ownership security must never be bypassed; a database-only test does
not implicitly activate the installed runtime. Maintain the present
`destinationCreated=false` / `migrationEnabled=false` /
`executionEnabled=false` contract for **existing rehearsal APIs**;
a future separately gated execution API must report its actual state
truthfully rather than repurposing a rehearsal success as real publication.

**MDCI:** Use narrowly triggered T1–T3 Rust/Python conformance for this
slice; request platform package builds only after the named Alpha test
acceptance gate, never on routine commits. Return to the approved installer
roadmap immediately after this slice; do not let speculative adversarial
hardening grow into an unrelated permanent workstream.

## Ordered implementation gates

1. **Historical original gate — Product architecture inventory (not operator environment replication):** trace the supported application launch contract, Host claim/auth/persistence interfaces, update UI/API, dependency declarations, OS-specific data paths, licensing and existing tests. Produce a gap/compatibility matrix before choosing installer tooling. Do **not** derive installer defaults from the developer's personal launch commands, local Conda environment or machine paths; use that machine only as a preexisting-installation detection test case.
2. **Historical original gate — Installer architecture decision (Tauri 2 now selected):** implement one shared GUI and CLI over a common installation engine, with OS/architecture-specific distributable builds. Evaluate toolkit/package candidates, OS signing/notarization/distribution, permissions, bundled/managed Python, optional Conda/ComfyUI acquisition, and lifecycle/rollback. Record alternatives and rationale.
3. **First runnable GUI slice:** on supported OS builds, select destination, detect existing install, install/reuse verified Python and Minglefield, show progress/errors, launch local application. No hidden developer prerequisites.
4. **Local Host onboarding:** implement reviewed, authenticated, single-use local provisioning and complete Host settings through existing persistence/API; preserve remote claim workflow.
5. **Optional components:** detect, verify, select manually or explicitly install Conda and ComfyUI; configure chosen runtime(s) per Host; exercise existing local ComfyUI connection test.
6. **Lifecycle:** idempotent update/repair/uninstall, explicit data-retention choice, verified artifacts, backups/migration/rollback, offline/failure handling, platform-update UI integration.
7. **Per-release dependency gate:** on **every installer build** for a Minglefield release, determine/validate required Python runtime dependencies against the packaged application, separate optional integrations, resolve compatible versions and generate/verify reproducible OS-specific manifests or locks. Build must fail on missing or inconsistent dependency declarations. Exercise clean-install and launch in isolated CI environments; `requirements-ci.txt` alone is not a complete runtime dependency source.
8. **Acceptance:** clean-machine, preexisting-environment, non-PATH Conda, manual-location, missing-dependency, optional-install, **preservation of imported remote-Host data (not implementation of remote claims)**, reinstall, tamper, failure/recovery and upgrade scenarios on Windows/macOS/Linux. Measure the 80% usability target with representative nontechnical participants.

## Explicit non-goals and open decisions

Not part of this phase: third-party game installer expansion, federated marketplaces, any additional ComfyUI models, custom nodes, extensions or workflows, **active remote-Host acquisition/management**, remote-host ownership bypass, source-checkout installation in the first Alpha, or mandatory central trust service. **Decided:** Tauri 2 and the portable Windows/Linux/macOS manager formats, independent local first-Host setup with separate login and database secrets. **Still open/unaccepted:** full application launch, fresh-db creation, source-provenance release contract, optional Conda distribution/license, ComfyUI acquisition and comprehensive release security/usability acceptance. No production-ready installer or measured usability result is claimed.

## Updated product decision: alpha release and reusable repackaging (2026-11-03)

- **Ship the present functional Alpha as the first installable product release**, explicitly labeled experimental/local Alpha, rather than delaying the installer until a production-ready server exists. The release version `0.1.0-alpha.1` is a **proposal**, not an assigned tag.
- **Installer must be release-agnostic**: separate packaging/build logic and signed/versioned release metadata from installer UI and installation lifecycle; future releases are produced by repackaging new application artifacts, not rewriting the installer.
- First package includes only the current Minglefield Alpha app/backend and mandatory runtime dependencies. Optional standard ComfyUI remains opt-in; no models or custom extensions. Do not confuse third-party game install with platform install.
- Alpha status and known limitations must be disclosed in installer and release notes. Local-only gateway must not be advertised as a production network service.
- Define a stable package manifest with product ID, semantic version/channel, OS/architecture, application entry point, dependency lock/hash inventory, payload checksums, data schema/migration compatibility, source license/attribution and publisher/update provenance.
- **Open-source licensing direction:** user selected a Blender-like GPL family model, with `GPL-3.0-or-later` proposed for Minglefield-owned core code. This is a *project licensing decision in principle*, not a claim that Blender itself uses GPLv3-only or that legal rights are already cleared. Final adoption requires copyright-holder authorization, dependency license review, notices and the actual LICENSE/SPDX changes.
- The Minglefield marketplace/service 5% commercial rule must **not** be imposed as a condition on GPL code use, copying, modification or redistribution. Any marketplace/service commission belongs to separate voluntary contractual transactions and requires legal review; do not silently rewrite existing policy.
- Do not block internal Alpha packaging engineering on production-readiness or a future product release. Public distribution remains subject to confirming redistribution rights, attribution and dependency compatibility.


## Marketplace scope and 5% fee clarification (2026-11-03)

**Binding project decision:** The 5% commission applies **only to transactions actually conducted through the future official Minglefield Online Community Marketplace**. It is **not** a license royalty, a framework-wide commerce levy, or a condition for using, modifying, distributing, self-hosting or commercially exploiting GPL-covered Minglefield code.

The official online Marketplace is **planned, not implemented, and not part of this repository or the first installable Alpha package**. No Marketplace backend, marketplace transaction fee enforcement, billing or operator-right restrictions are to be added to the installer or GPL core as part of this phase.

The project founder intends to **reserve operation of the official Minglefield Online Community Marketplace** for themselves for now, to the extent legally available. Distinguish rights in the official service's name/branding, domain, infrastructure, operator accounts, contracts and any separately developed proprietary service code from the GPL rights in the open-source core. Do **not** assert that GPL licensing prohibits third parties from building or operating independent compatible marketplace services. Trademark/service terms, ownership and competition-law implications require jurisdiction-specific legal review.

Future Marketplace terms may specify a 5% commission on transactions processed by that service, with transparent pricing and contractual acceptance. This is outside the current installer, repository distribution and runtime dependency closure.

