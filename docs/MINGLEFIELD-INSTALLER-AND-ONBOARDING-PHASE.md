# Minglefield Platform Installer & First-Run Onboarding — active next phase

Status: **approved priority and requirements; design/implementation not yet verified** (2026-11-03).
Scope: installing, configuring, launching, updating and recovering **Minglefield itself**, not installing third-party games. This phase takes precedence over unfinished roadmap features; previous work remains planned and is sequenced after this phase, except blocking security fixes and prerequisites.

## Product outcome and acceptance target

A first-time, non-technical user can download an OS-appropriate graphical installer, choose a destination, install Minglefield and its necessary runtime, provision the **computer running the installer** as their local Host, configure optional runtimes, and launch Minglefield without knowing Python, Conda, Git, shell commands, or environment variables. Aim for **at least 80%** of representative first-time target users completing defined core onboarding tasks unaided. This is a **target**, not a measured achievement; establish task definitions, test participants, observations and completion criteria.

Support Windows, macOS and Linux with self-starting installers that require no preinstalled Python/Conda. Use **one shared cross-platform installer GUI** with platform-specific distributable builds. Select the actual GUI toolkit and package formats after comparing feasibility, OS packaging, licensing and dependency inventory; do not prematurely commit to a framework.

## Installer journeys

- **Standard:** safe OS-specific defaults, clear progress, minimal choices, automatic detection, install/reuse required Python runtime, local Host creation, launch.
- **Advanced:** destination and data locations, detected installations and manual path selection, Python/Conda/ComfyUI options, installation and connection options, local Host registration, and optional Host-owned runtime configuration; job authorization/scheduling rules remain exclusively in Hosts. All installer-set Host settings remain visible/editable in Minglefield's existing Hosts UI.
- **Existing installation:** detect and offer safe reuse/repair/update without silently replacing an existing environment, Host ownership, settings, SQLite database, user data, or unrelated files.
- **No installation detected:** provision the local Host during first run; do not require the user to manually copy or enter a Host claim token.

## Shared GUI and unattended CLI installation (binding decision, 2026-11-03)

- One cross-platform installer GUI codebase for Windows, macOS and Linux; **build and distribute separate signed/verified OS/architecture-specific installer artifacts**. The GUI toolkit and precise native package formats remain to be selected through Gate 2 evidence.
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

The already verified portable setup-manager GUI and dry-run migration
remain read-only until the separate operational-runtime packaging,
exclusive atomic encrypted publication, one-time local handshake and
recovery gates are finished. **No implementation-only helper counts as
proof that first-run authorization is complete.**

## Existing repository boundaries and evidence to inspect

- `server/private_alpha_gateway.py`: current local gateway and web UI, local Host claim flow, Host settings/runtimes, and placeholder platform-update dialog; its current local bootstrap is not an installer provisioning API.
- `server/host_runtime_config.py`: ComfyUI runtime validation, currently loopback-only; the registry class is in-memory and is **not** durable storage.
- Existing host/auth persistence and API methods must be traced and reused; don't assume the in-memory registry is the persisted implementation.
- `scripts/minglefield_environment.py` and `scripts/minglefield_platform_preflight.py`: Python-dependent **developer alpha tools**, not a first-install GUI.
- `requirements-ci.txt` is **not** a complete runtime dependency manifest.
- Existing SQLite user data and configured Hosts must survive install, repair, update, and failed migration; platform update must be distinguished from game/integration updates.

## Ordered implementation gates

1. **Product architecture inventory (not operator environment replication):** trace the supported application launch contract, Host claim/auth/persistence interfaces, update UI/API, dependency declarations, OS-specific data paths, licensing and existing tests. Produce a gap/compatibility matrix before choosing installer tooling. Do **not** derive installer defaults from the developer's personal launch commands, local Conda environment or machine paths; use that machine only as a preexisting-installation detection test case.
2. **Installer architecture decision:** implement one shared GUI and CLI over a common installation engine, with OS/architecture-specific distributable builds. Evaluate toolkit/package candidates, OS signing/notarization/distribution, permissions, bundled/managed Python, optional Conda/ComfyUI acquisition, and lifecycle/rollback. Record alternatives and rationale.
3. **First runnable GUI slice:** on supported OS builds, select destination, detect existing install, install/reuse verified Python and Minglefield, show progress/errors, launch local application. No hidden developer prerequisites.
4. **Local Host onboarding:** implement reviewed, authenticated, single-use local provisioning and complete Host settings through existing persistence/API; preserve remote claim workflow.
5. **Optional components:** detect, verify, select manually or explicitly install Conda and ComfyUI; configure chosen runtime(s) per Host; exercise existing local ComfyUI connection test.
6. **Lifecycle:** idempotent update/repair/uninstall, explicit data-retention choice, verified artifacts, backups/migration/rollback, offline/failure handling, platform-update UI integration.
7. **Per-release dependency gate:** on **every installer build** for a Minglefield release, determine/validate required Python runtime dependencies against the packaged application, separate optional integrations, resolve compatible versions and generate/verify reproducible OS-specific manifests or locks. Build must fail on missing or inconsistent dependency declarations. Exercise clean-install and launch in isolated CI environments; `requirements-ci.txt` alone is not a complete runtime dependency source.
8. **Acceptance:** clean-machine, preexisting-environment, non-PATH Conda, manual-location, missing-dependency, optional-install, remote-claim, reinstall, tamper, failure/recovery and upgrade scenarios on Windows/macOS/Linux. Measure the 80% usability target with representative nontechnical participants.

## Explicit non-goals and open decisions

Not part of this phase: third-party game installer expansion, federated marketplaces, any additional ComfyUI models, custom nodes, extensions or workflows, remote-host ownership bypass, or mandatory central trust service. Exact shared GUI toolkit, OS distribution formats, Python packaging strategy, optional Conda distribution/license, ComfyUI acquisition policy and security design for local provisioning remain **open** until inventory and review. No production-ready installer, complete runtime dependency list, security review, or usability measurement is claimed yet.

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

