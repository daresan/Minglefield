# Binding boundary: platform installer vs community game integration

**Decision reaffirmed 2026-11-04.** This is an implementation and review invariant for Minglefield contributors and coding agents. See [installer/onboarding phase](MINGLEFIELD-INSTALLER-AND-ONBOARDING-PHASE.md) and [licensing/marketplace decision](LICENSING-AND-MARKETPLACE-DECISION.md).

## A. Minglefield application setup (current priority)

**Owner:** `installer/` (shared Rust installer core, CLI, Tauri GUI) and application first-run/Hosts integration.

**Subject:** Minglefield **itself**. **First Alpha application payload: official, verified package only.** An explicitly chosen fork/source checkout is a possible **later** install source, not an Alpha acceptance gate; a checkout selected for *data migration* is never implicitly executed. Responsibilities: OS-specific packages/locations; detecting existing source and installed application; install/launch/update/repair/uninstall; required runtime; non-destructive existing-data/ownership preservation; and approved provisioning of the *local computer* as a Host.

**Applicable requirements:** published framework GNU GPL license and notices; application release integrity and source/publisher provenance; OS packaging and safe filesystem operations; explicit consent for optional runtimes; application configuration and Host authentication. A Minglefield installation is **not** a marketplace transaction and does **not** incur a 5% platform fee.

**Not prerequisites:** community game manifests, game developer licenses, game marketplace agreements, third-party game sandbox approval, game integration evidence, game-installation trust rules, or game marketplace payment logic.

## B. Community games and integrations (separate, deferred workstream)

**Owner:** game integration and game installation modules, their own workflows and security policies.

**Subject:** games, assets, extensions and integrations authored or published by independent parties. Their separate provenance, compatibility, sandbox and game-installation checks remain intact but **must not be imported into the platform installer**.

**Commercial terms:** separate marketplace agreements govern defined transactions conducted through Minglefield-operated services; the platform share is 5% on the contractually defined transaction basis. The share is not a GPL redistribution royalty, not a fee for installing Minglefield, and not a requirement for independently distributed GPL-covered code.

## Engineering and CI rules

- `Installer Rust checks` and `Tauri native package smoke builds` are the relevant CI gates for application installer work.
- `Game installation cross-platform security` and other game-installation workflows are separate; a green game test **does not prove** the application installer works, and an unfinished game-installation feature does not block application setup.
- Cross-platform compile and package smoke tests do not prove interactive installer operation or actual Minglefield installation. Report these evidence levels separately.
- When naming files, functions, tickets, reviews or requirements, always qualify **platform/app installer** versus **community game installer**.
- Do not reopen the GPL framework + separate 5% marketplace-service model as a generic prerequisite. Escalate only a specific, demonstrated conflict.
- Work on the public feature branch; do not merge into `main` or touch the private repository without explicit authorization.

## Current state

**Updated 2026-11-07:** The portable Tauri manager can execute experimental verified Alpha SQLCipher-copy, installed-file and once-per-operation local Host-first-run paths, but M2.08 operator acceptance **FAILED** on an incomplete delivered Windows package; full installed application launch, fresh encrypted DB creation, repair/update and installer-CLI execution remain open. The application's separate shell-start path is M2.09; GUI and installer-CLI parity is M2.11. Source structural recognition is neither package provenance nor permission to execute the data source. **Remote Host acquisition/management and client-only installations are future application capabilities**, not installer acceptance; preserving existing imported remote Host references, grants and owners remains mandatory.
