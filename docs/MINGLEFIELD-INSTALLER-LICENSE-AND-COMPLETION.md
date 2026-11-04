# Installer license acceptance and completion flow

Decision 2026-11-04. Applies to the **Minglefield application installer**, not to third-party game installation.

## Mandatory pre-install license step

- Display the complete license text shipped with the exact Minglefield release, including its identifier/version and source. The user must be able to scroll/read it before deciding.
- An unchecked-by-default, explicit acceptance control gates **all installation writes**, including runtime provisioning, package extraction, migration and application installation. A preview may remain available without acceptance.
- Declining, closing or skipping the license step must not install anything. The accepted license must match the release being installed; a changed release or changed license invalidates prior acceptance for this attempt.
- An unattended invocation requires a separate explicit license acceptance argument bound to the release/license identifier and digest. Neither `--silent`, `--defaults` nor a general optional-component consent implies license acceptance. Missing/mismatched acceptance fails before installation writes with a deterministic error.
- Record only the minimum audit metadata (license ID, SHA-256 digest, selected release, acceptance timestamp and installation transaction identifier) when a real installation transaction exists. Never treat a preview as accepted.
- The project has **decided on the GNU GPL framework + separate 5% marketplace-service terms model** (see [binding licensing decision](LICENSING-AND-MARKETPLACE-DECISION.md)). The actual canonical GPL text and copyright notices are not yet published in this repository. Do **not** invent license text or enable release installation while required license artifacts are missing. The proposed explicit installer acknowledgement is a product workflow step, **not** a new restriction on GPL use, copying or redistribution; marketplace terms must be handled separately.

## Post-install completion

After a **successful** installation, present two independent unchecked-by-default options: **Show README** and **Launch Minglefield**. Both are optional, can be selected together or separately, and can be skipped. README must be the local file from the installed release; the launcher must use the verified installed application entry point rather than a guessed executable or shell command.

If the README is missing, report that without converting installation success into failure. If launch fails, report the launch error separately while preserving installation success. Never launch or open a README as a consequence of an installation failure or cancelled transaction. Do not trigger these actions during plan-only preview.

## Acceptance tests

- License absent, unreadable, altered or not explicitly accepted: installation blocked.
- Unattended missing/mismatched acceptance: deterministic failure, no writes.
- Preview works without accepting and cannot persist acceptance.
- Successful install: both post-install options can be selected independently; neither runs unless selected.
- Failed/cancelled install: no README opening or application launch.
- Windows/macOS/Linux: verify correct release license, installed README and actual installed launch target.

Current implementation status: requirements documented; the Rust core and Tauri GUI are still **non-installing previews**. No claim of a working acceptance gate or completion launcher is made.
