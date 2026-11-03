# Minglefield Platform Installer & First-Run Onboarding — active next phase

Status: **approved priority and requirements; design/implementation not yet verified** (2026-11-03).
Scope: installing, configuring, launching, updating and recovering **Minglefield itself**, not installing third-party games. This phase takes precedence over unfinished roadmap features; previous work remains planned and is sequenced after this phase, except blocking security fixes and prerequisites.

## Product outcome and acceptance target

A first-time, non-technical user can download an OS-appropriate graphical installer, choose a destination, install Minglefield and its necessary runtime, provision the **computer running the installer** as their local Host, configure optional runtimes, and launch Minglefield without knowing Python, Conda, Git, shell commands, or environment variables. Aim for **at least 80%** of representative first-time target users completing defined core onboarding tasks unaided. This is a **target**, not a measured achievement; establish task definitions, test participants, observations and completion criteria.

Support Windows, macOS and Linux with self-starting installers that require no preinstalled Python/Conda. Select the packaging/GUI technology **after** repository, OS packaging, licensing and dependency inventory; do not prematurely commit to a framework.

## Installer journeys

- **Standard:** safe OS-specific defaults, clear progress, minimal choices, automatic detection, install/reuse required Python runtime, local Host creation, launch.
- **Advanced:** destination and data locations, detected installations and manual path selection, Python/Conda/ComfyUI options, full relevant Host settings including scheduling, enabled state, resource limits and runtime configuration. All installer-set Host settings remain visible/editable in Minglefield's existing Hosts UI.
- **Existing installation:** detect and offer safe reuse/repair/update without silently replacing an existing environment, Host ownership, settings, SQLite database, user data, or unrelated files.
- **No installation detected:** provision the local Host during first run; do not require the user to manually copy or enter a Host claim token.

## Component acquisition and discovery

For **Python, Conda and ComfyUI**: search known platform-specific locations, verify compatibility and actual functionality, offer user-selected directory/executable as a fallback, and offer a clearly disclosed automatic installation if absent. Explicit consent is required for optional/heavy components. The installer must explain source, version, destination, approximate size and consequences; verify downloaded artifacts and trusted release provenance before execution. Handle unavailable network, cancellation, incomplete installation, upgrade, and retry without corrupting other installations.

- **Python:** mandatory runtime, preferably isolated from system Python and unrelated environments; reuse an existing compatible environment only with explicit informed selection and no uncontrolled mutation. Do not require Conda for Minglefield.
- **Conda:** optional; detect/reuse, let user locate, or install if selected. Never assume the `conda` shell command is on PATH; an installed environment may be valid without shell initialization.
- **ComfyUI:** optional, detect/reuse, let user locate, or install if selected; can also connect to a running instance. Runtime and integration settings are **Host-owned**, not global. Do not install models, custom nodes, or heavyweight dependencies without separate disclosure/consent. Remote connections require an independently reviewed authenticated and secure networking design; the current ComfyUI runtime validator only permits loopback.
- Keep package/application files, managed runtimes, and persistent user data logically separate.

## Local Host first-run security boundary

The installer knows which computer it is running on; this is **not by itself proof of authorization** to claim an account's Host. Reuse the existing authenticated Host persistence and configuration API rather than creating a second settings store or privileged bypass. Design a **one-time, narrowly scoped, locally authorized provisioning handshake** bound to the intended local installation and authenticated operator/account. The setup flow should perform the Host claim automatically, without requiring manual token entry; secrets must be ephemeral and invalidated after use, and the flow must resist unrelated local processes. Reinstall/repair must not silently seize a Host already owned by another account. Preserve the existing manual token/confirmation mechanism for **remote Host claims**.

The installer should expose the relevant Host controls already available in the alpha UI, with approachable defaults and an Advanced section; both surfaces must read/write the same authoritative Host model. The existing alpha gateway's local bootstrap code and current Host-claim route require security and persistence review **before** reuse or extension.

## Existing repository boundaries and evidence to inspect

- `server/private_alpha_gateway.py`: current local gateway and web UI, local Host claim flow, Host settings/runtimes, and placeholder platform-update dialog; its current local bootstrap is not an installer provisioning API.
- `server/host_runtime_config.py`: ComfyUI runtime validation, currently loopback-only; the registry class is in-memory and is **not** durable storage.
- Existing host/auth persistence and API methods must be traced and reused; don't assume the in-memory registry is the persisted implementation.
- `scripts/minglefield_environment.py` and `scripts/minglefield_platform_preflight.py`: Python-dependent **developer alpha tools**, not a first-install GUI.
- `requirements-ci.txt` is **not** a complete runtime dependency manifest.
- Existing SQLite user data and configured Hosts must survive install, repair, update, and failed migration; platform update must be distinguished from game/integration updates.

## Ordered implementation gates

1. **Repository inventory:** trace gateway runtime imports, Host claim/auth/persistence, setup/start paths, update UI/API, dependencies, OS-specific data paths, licensing and existing tests. Produce a gap/compatibility matrix before choosing installer tooling.
2. **Installer architecture decision:** evaluate GUI/packaging candidates, OS signing/notarization/distribution, permissions, bundled/managed Python, optional Conda/ComfyUI acquisition, and lifecycle/rollback. Record alternatives and rationale.
3. **First runnable GUI slice:** on supported OS builds, select destination, detect existing install, install/reuse verified Python and Minglefield, show progress/errors, launch local application. No hidden developer prerequisites.
4. **Local Host onboarding:** implement reviewed, authenticated, single-use local provisioning and complete Host settings through existing persistence/API; preserve remote claim workflow.
5. **Optional components:** detect, verify, select manually or explicitly install Conda and ComfyUI; configure chosen runtime(s) per Host; exercise existing local ComfyUI connection test.
6. **Lifecycle:** idempotent update/repair/uninstall, explicit data-retention choice, verified artifacts, backups/migration/rollback, offline/failure handling, platform-update UI integration.
7. **Acceptance:** clean-machine, preexisting-environment, non-PATH Conda, manual-location, missing-dependency, optional-install, remote-claim, reinstall, tamper, failure/recovery and upgrade scenarios on Windows/macOS/Linux. Measure the 80% usability target with representative nontechnical participants.

## Explicit non-goals and open decisions

Not part of this phase: third-party game installer expansion, federated marketplaces, automatic ComfyUI model/custom-node installation, remote-host ownership bypass, or mandatory central trust service. Exact GUI toolkit, OS distribution formats, Python packaging strategy, optional Conda distribution/license, ComfyUI acquisition policy and security design for local provisioning remain **open** until inventory and review. No production-ready installer, complete runtime dependency list, security review, or usability measurement is claimed yet.
