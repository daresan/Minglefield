# Optional Git and GitHub CLI integration — installer contract

Status: approved architecture decision; **installation and authentication are not implemented**. Scope: the Minglefield platform installer, not the third-party game installer.

## Separate optional capabilities

| Component | Default | Dependency | Purpose |
| --- | --- | --- | --- |
| Git executable | Off | None at installer selection time | Git repository operations |
| GitHub CLI (`gh`) | Off | Git may be needed for specific gh Git operations, but not all API calls | GitHub API and authenticated workflows |
| GitHub sign-in | Off | A working `gh` executable | User-initiated interactive authentication |

The three selections must remain independent. Selecting `gh` must not silently select or install Git. Selecting Git must not imply GitHub access. No GitHub account is required for core Minglefield operation. Optional ComfyUI and Conda settings remain independent.

## Discovery and installation safety

1. Inspect `git --version` and `gh --version` with bounded subprocess timeouts, and record resolved executable paths. A PATH hit is **not** proof of a trustworthy installation or an authenticated session.
2. Detect existing per-user and machine-wide installations without modifying them. Preserve explicit user-selected paths. Avoid automatic upgrades, PATH mutation, credential-manager changes and replacement of pre-existing executables.
3. Offer verified platform/architecture-specific downloads or documented package-manager paths only after the user explicitly selects each component. Verify provenance, artifact hashes and applicable platform trust controls before executing any installer. Never pipe remote scripts to a shell.
4. Prefer per-user, least-privilege installation. Any system-wide installation, privilege elevation, repository change or credential configuration needs separate consent.
5. On Windows, macOS and Linux, detect tools per selected Host; different Hosts can have different executable paths and authentication. Remote Host operations must be authorized through the Host security boundary, not silently executed on the UI client.
6. A successful install only proves the executable is available. GitHub login is a separate user action, with its own result and failure handling. Never print, store or transfer tokens in installer logs or diagnostics.
7. Preserve support for HTTPS, SSH, Git Credential Manager and other Git providers through provider-specific adapters; do not hardwire `gh` into the Minglefield core.

## Authentication contract

The user may opt into an interactive `gh auth login` flow **after** a verified `gh` executable is available. Do not initiate it merely because `gh` was installed. Existing sessions and credentials must not be overwritten, copied or exported by the installer. A status check such as `gh auth status` is a separate, explicitly initiated diagnostic and its output must be redacted before logging. An authenticated CLI on one Host does not authorize another Host.

## Versioned configuration

Current installer configuration schema is version 1. It does **not** accept Git/`gh` selections. Introduce these options in a separately reviewed **version 2** schema with independent opt-ins, migration tests and explicit consent. Do not silently add new keys to version 1, weaken unknown-key rejection or reuse the Conda/ComfyUI consent flag as authentication permission.

## Outstanding acceptance gates

- Source-backed audit of all Git/`gh` executable invocation sites and their required capabilities.
- Independent install/detect/test on Windows, macOS and Linux.
- Authenticated versus unauthenticated behavior, existing credentials and multi-Host isolation tests.
- Verified download provenance, offline/failed installation and rollback tests.
- End-user consent UI and the actual installer execution path.

**No Git, gh, login, package manager, Host claim or installation is executed by this document.**

## Implemented read-only capability probe

Run manually on a selected machine (not during CI and not automatically on every Host):

```powershell
python -B installer/scripts/probe_git_tools.py --json
```

The probe independently locates `git` and `gh` via PATH and invokes only their `--version` commands with a five-second timeout and no shell. Its results distinguish `missing`, `available` and `unverified`; it does not claim trusted binary provenance or that a particular Git operation is supported. No GitHub authentication check, token inspection, installation, network request or Host modification occurs. The result describes **only the machine running the probe**, not remote Hosts.

Source audit finding: `sec01_host_commit_policy_sim.py` invokes Git via a **configured executable path** (`profile[0]`) for project initialization. Literal-only command scanners cannot prove the full executable dependency graph. The earlier Python import audit's `__import__("os")` at line 758 is a standard-library import, not another third-party package. This does not eliminate the need for broader invocation analysis and host-specific authorization checks.

The probe is a diagnostic foundation, not a shipped installer or a substitute for provenance validation.
