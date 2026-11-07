# Portable Minglefield Setup Manager — binding product requirements

Decision 2026-11-04. Applies **only** to the Minglefield application installer, not community-game installation. See [scope boundary](PLATFORM-VS-GAME-INSTALLATION-BOUNDARY.md).

1. The Tauri **Setup Manager is a portable, precompiled tool** downloaded for Windows, Linux and macOS. Users start it without installing the Setup Manager itself and without needing Python, Conda, Git, Node or Rust in advance.
2. The Setup Manager installs/configures/updates/repairs the **separate Minglefield application**. Closing or deleting the downloaded Setup Manager must not affect the installed application or persistent user data.
3. **All three operating systems** must offer the same functional setup choices: Standard and Advanced; installation and data locations; detect/reuse existing components; explicit opt-in for optional runtimes; and first-run local Host configuration. Platform-specific controls may differ.
4. **Both the full GNU GPL framework license and the Minglefield application README must be available within the GUI**, in Standard and Advanced, offline, bundled at build time. They are readable without installing anything, and reading them is not a consent gate or marketplace agreement.
5. **Apple code signing and notarization are expressly outside the current project scope.** Do not suggest, schedule, block on, or add CI acceptance requirements for them unless the maintainer explicitly changes this decision.
6. The current NSIS, DEB and DMG *installer-of-the-Setup-Manager* preview artifacts are **not** proof of portable delivery. Replace the release packaging goal with a directly runnable Windows executable, portable Linux executable distribution (e.g. AppImage), and runnable macOS app distribution (e.g. app in DMG). Verify actual launch without installing the Setup Manager on each platform.
7. **Updated status (2026-11-07):** experimental native verified application-file copy and local Host-first-run operations now exist, but the downloaded Windows M2.08 package failed operator installation (reported hidden-file omission); no completed, independently accepted app launch/install is claimed. The portable manager must still prove that the separately installed application starts and persists after the manager is removed.

Acceptance: launch portable manager without installing manager; view full bundled GPL and README offline in both modes; select/configure app installation; verify app persists and launches after manager removal. Test Windows, Linux, macOS separately. Keep application/game installer tests separate.

**Separation of entrypoints (2026-11-07):** The Setup Manager GUI, actual headless **installer CLI** (`--silent --defaults`, due M2.11) and Minglefield **application shell startup** (due M2.09) are distinct. The independent application launch may not require the manager after installation. The first Alpha uses the verified official package; explicit source-checkout builds are deferred. Migration preserves existing local/remote Host ownership and `mingleadmin` credentials; active Remote Host claiming and client-only installations are not part of portable manager acceptance. A fresh local Host is established on the installer machine with approved local scope, not through remote claiming.

## Linux delivery channels — additive, not exclusive

**AppImage is one portable graphical distribution channel, not the sole supported Linux installation method.** Do not remove or forbid terminal-based operation or native package formats when adding AppImage CI. Maintain a common Rust installer core and separate distribution packaging from actual application installation.

- Portable graphical Setup Manager: AppImage, launched without installing the manager.
- Headless/terminal installation: a standalone CLI using the same installer core; an optional Bash bootstrapper may download/verify and invoke that CLI, but must not be the only terminal option.
- Native package-manager installation of the **Minglefield application**: Debian/Ubuntu `.deb` and Fedora/RHEL `.rpm` as planned alternative delivery channels; packaging must not silently install the Setup Manager as the target application.
- Manual/offline delivery: versioned `.tar.gz` containing the application and documented install/launch entrypoints, with the same configuration semantics.

These are **target channels**, not implemented or tested deliverables. The current Linux AppImage CI only builds the portable GUI preview. Bash, CLI execution, application DEB/RPM and tarball installation remain separate future implementation tasks. For any channel, preserve optional-component consent and the framework license/README availability; for headless use, provide readable bundled documents and explicit commands rather than a GUI-only panel.
