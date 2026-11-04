# Portable Minglefield Setup Manager — binding product requirements

Decision 2026-11-04. Applies **only** to the Minglefield application installer, not community-game installation. See [scope boundary](PLATFORM-VS-GAME-INSTALLATION-BOUNDARY.md).

1. The Tauri **Setup Manager is a portable, precompiled tool** downloaded for Windows, Linux and macOS. Users start it without installing the Setup Manager itself and without needing Python, Conda, Git, Node or Rust in advance.
2. The Setup Manager installs/configures/updates/repairs the **separate Minglefield application**. Closing or deleting the downloaded Setup Manager must not affect the installed application or persistent user data.
3. **All three operating systems** must offer the same functional setup choices: Standard and Advanced; installation and data locations; detect/reuse existing components; explicit opt-in for optional runtimes; and first-run local Host configuration. Platform-specific controls may differ.
4. **Both the full GNU GPL framework license and the Minglefield application README must be available within the GUI**, in Standard and Advanced, offline, bundled at build time. They are readable without installing anything, and reading them is not a consent gate or marketplace agreement.
5. **Apple code signing and notarization are expressly outside the current project scope.** Do not suggest, schedule, block on, or add CI acceptance requirements for them unless the maintainer explicitly changes this decision.
6. The current NSIS, DEB and DMG *installer-of-the-Setup-Manager* preview artifacts are **not** proof of portable delivery. Replace the release packaging goal with a directly runnable Windows executable, portable Linux executable distribution (e.g. AppImage), and runnable macOS app distribution (e.g. app in DMG). Verify actual launch without installing the Setup Manager on each platform.
7. No application install execution exists yet. Do not claim this requirement document or a preview build provides a functional Minglefield installation.

Acceptance: launch portable manager without installing manager; view full bundled GPL and README offline in both modes; select/configure app installation; verify app persists and launches after manager removal. Test Windows, Linux, macOS separately. Keep application/game installer tests separate.
