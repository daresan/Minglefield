# Minglefield Platform Installer & First-Run Onboarding — active next phase

Status: **approved priority and requirements; design/implementation not yet verified** (2026-11-03).
Scope: installing, configuring, launching, updating and recovering **Minglefield itself**, not installing third-party games. This phase takes precedence over unfinished roadmap features; previous work remains planned and is sequenced after this phase, except blocking security fixes and prerequisites.

## Product outcome and acceptance target

A first-time, non-technical user can download an OS-appropriate graphical installer, choose a destination, install Minglefield and its necessary runtime, provision the **computer running the installer** as their local Host, configure optional runtimes, and launch Minglefield without knowing Python, Conda, Git, shell commands, or environment variables. Aim for **at least 80%** of representative first-time target users completing defined core onboarding tasks unaided. This is a **target**, not a measured achievement; establish task definitions, test participants, observations and completion criteria.

Support Windows, macOS and Linux with self-starting installers that require no preinstalled Python/Conda. Select the packaging/GUI technology **after** repository, OS packaging, licensing and dependency inventory; do not prematurely commit to a framework.

## Installer journeys

- **Standard:** safe OS-specific defaults, clear progress, minimal choices, automatic detection, install/reuse required Python runtime, local Host creation, launch.
- **Advanced:** destination and data locations, detected installations and manual path selection, Python/Conda/ComfyUI options, installation and connection options, local Host registration, and optional Host-owned runtime configuration; job authorization/scheduling rules remain exclusively in Hosts. All installer-set Host settings remain visible/editable in Minglefield's existing Hosts UI.
- **Existing installation:** detect and offer safe reuse/repair/update without silently replacing an existing environment, Host ownership, settings, SQLite database, user data, or unrelated files.
- **No installation detected:** provision the local Host during first run; do not require the user to manually copy or enter a Host claim token.

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

## Existing repository boundaries and evidence to inspect

- `server/private_alpha_gateway.py`: current local gateway and web UI, local Host claim flow, Host settings/runtimes, and placeholder platform-update dialog; its current local bootstrap is not an installer provisioning API.
- `server/host_runtime_config.py`: ComfyUI runtime validation, currently loopback-only; the registry class is in-memory and is **not** durable storage.
- Existing host/auth persistence and API methods must be traced and reused; don't assume the in-memory registry is the persisted implementation.
- `scripts/minglefield_environment.py` and `scripts/minglefield_platform_preflight.py`: Python-dependent **developer alpha tools**, not a first-install GUI.
- `requirements-ci.txt` is **not** a complete runtime dependency manifest.
- Existing SQLite user data and configured Hosts must survive install, repair, update, and failed migration; platform update must be distinguished from game/integration updates.

## Ordered implementation gates

1. **Product architecture inventory (not operator environment replication):** trace the supported application launch contract, Host claim/auth/persistence interfaces, update UI/API, dependency declarations, OS-specific data paths, licensing and existing tests. Produce a gap/compatibility matrix before choosing installer tooling. Do **not** derive installer defaults from the developer's personal launch commands, local Conda environment or machine paths; use that machine only as a preexisting-installation detection test case.
2. **Installer architecture decision:** evaluate GUI/packaging candidates, OS signing/notarization/distribution, permissions, bundled/managed Python, optional Conda/ComfyUI acquisition, and lifecycle/rollback. Record alternatives and rationale.
3. **First runnable GUI slice:** on supported OS builds, select destination, detect existing install, install/reuse verified Python and Minglefield, show progress/errors, launch local application. No hidden developer prerequisites.
4. **Local Host onboarding:** implement reviewed, authenticated, single-use local provisioning and complete Host settings through existing persistence/API; preserve remote claim workflow.
5. **Optional components:** detect, verify, select manually or explicitly install Conda and ComfyUI; configure chosen runtime(s) per Host; exercise existing local ComfyUI connection test.
6. **Lifecycle:** idempotent update/repair/uninstall, explicit data-retention choice, verified artifacts, backups/migration/rollback, offline/failure handling, platform-update UI integration.
7. **Per-release dependency gate:** on **every installer build** for a Minglefield release, determine/validate required Python runtime dependencies against the packaged application, separate optional integrations, resolve compatible versions and generate/verify reproducible OS-specific manifests or locks. Build must fail on missing or inconsistent dependency declarations. Exercise clean-install and launch in isolated CI environments; `requirements-ci.txt` alone is not a complete runtime dependency source.
8. **Acceptance:** clean-machine, preexisting-environment, non-PATH Conda, manual-location, missing-dependency, optional-install, remote-claim, reinstall, tamper, failure/recovery and upgrade scenarios on Windows/macOS/Linux. Measure the 80% usability target with representative nontechnical participants.

## Explicit non-goals and open decisions

Not part of this phase: third-party game installer expansion, federated marketplaces, any additional ComfyUI models, custom nodes, extensions or workflows, remote-host ownership bypass, or mandatory central trust service. Exact GUI toolkit, OS distribution formats, Python packaging strategy, optional Conda distribution/license, ComfyUI acquisition policy and security design for local provisioning remain **open** until inventory and review. No production-ready installer, complete runtime dependency list, security review, or usability measurement is claimed yet.

## Updated product decision: alpha release and reusable repackaging (2026-11-03)

- **Ship the present functional Alpha as the first installable product release**, explicitly labeled experimental/local Alpha, rather than delaying the installer until a production-ready server exists. The release version `0.1.0-alpha.1` is a **proposal**, not an assigned tag.
- **Installer must be release-agnostic**: separate packaging/build logic and signed/versioned release metadata from installer UI and installation lifecycle; future releases are produced by repackaging new application artifacts, not rewriting the installer.
- First package includes only the current Minglefield Alpha app/backend and mandatory runtime dependencies. Optional standard ComfyUI remains opt-in; no models or custom extensions. Do not confuse third-party game install with platform install.
- Alpha status and known limitations must be disclosed in installer and release notes. Local-only gateway must not be advertised as a production network service.
- Define a stable package manifest with product ID, semantic version/channel, OS/architecture, application entry point, dependency lock/hash inventory, payload checksums, data schema/migration compatibility, source license/attribution and publisher/update provenance.
- **Open-source licensing direction:** user selected a Blender-like GPL family model, with `GPL-3.0-or-later` proposed for Minglefield-owned core code. This is a *project licensing decision in principle*, not a claim that Blender itself uses GPLv3-only or that legal rights are already cleared. Final adoption requires copyright-holder authorization, dependency license review, notices and the actual LICENSE/SPDX changes.
- The Minglefield marketplace/service 5% commercial rule must **not** be imposed as a condition on GPL code use, copying, modification or redistribution. Any marketplace/service commission belongs to separate voluntary contractual transactions and requires legal review; do not silently rewrite existing policy.
- Do not block internal Alpha packaging engineering on production-readiness or a future product release. Public distribution remains subject to confirming redistribution rights, attribution and dependency compatibility.

