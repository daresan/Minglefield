# Minglefield installer — binding wizard and database migration requirements

Status: product decisions recorded 2026-11-04. **This is a requirements contract, not a claim that the functions are already implemented.** Applies to the existing six-page Tauri installer wizard. Do not replace it with a second installer or reset the current workflow.

## Non-negotiable database policy

- **Every new Minglefield installation uses an encrypted SQLCipher operational database**, regardless of Standard/Advanced mode and regardless of whether a legacy database is imported. There is no unencrypted new-installation option.
- A **new database encryption password and matching confirmation are mandatory in both paths**. The installer must enforce the agreed policy (currently UI: minimum 8 characters, >=1 uppercase letter, >=1 digit, >=1 special character). Enforce in the Rust/backend execution boundary as well as the GUI; do not rely on the status text. Do not allow Next/execute while invalid. Do not log or persist plaintext passwords.
- Two installation paths: (A) fresh installation without a legacy database, creates an encrypted database with new/default editable settings; (B) **database import including migration**, reads a selected legacy database, presents imported settings for correction, creates a separate encrypted destination and migrates and verifies data.
- Unencrypted SQLite is allowed **only as a legacy migration source**, never as the operational destination. A source SQLCipher DB may require its existing unlock password, distinct from the mandatory new destination password.
- The legacy source must remain unchanged. Do not overwrite existing destination files. Require schema recognition, verified mapping, integrity and foreign-key checks, transactional/atomic destination handling and failure recovery. Compare expected record counts and relevant data/relationships, not merely SQLite headers. Fail closed on unknown or incompatible schema. Never silently discard data.
- Migration execution stays disabled until these guarantees exist and are tested. Lockfile updates and successful read-only inspection do not constitute migration execution.

## Existing installer pages — retain all six and their navigation

### 1. Welcome / project information
- Retain the bundled **full framework GPL-3.0-or-later license** and **Minglefield README**, available offline and read-only in both setup modes.
- Keep framework license distinct from marketplace/service commercial terms. Reading is not consent to marketplace terms or permission to install.
- Retain Back/Next navigation and previously entered state.

### 2. Configuration
- Retain **Standard (recommended)** and **Advanced** as explicit user choices; never silently switch modes on navigation or on the review page.
- Standard uses safe per-user defaults and does not silently enable optional runtimes/components.
- Advanced retains the **Custom paths** and **Versioned configuration** submodes (key=value, v1/v2), including their existing values and explicit runtime consent.
- Retain install and persistent-data directory controls, with native folder picker; ensure review edits actually affect the final effective plan, not merely an inactive input. If the selected configuration source cannot represent an edit, present a clear choice rather than silently changing modes or ignoring it.
- Keep runtime/host-specific configuration under the selected **Host**; do not hardcode ComfyUI or other host runtime paths globally.

### 3. Optional installations (inserted 2026-11-05)
- Dedicated page before source and database discovery. Present previously planned optional Git, GitHub CLI, GitHub login offer, Conda and ComfyUI choices, all disabled by default.
- Explicit, independent consent is required before including optional components in a plan. Selection does not itself execute an installation or authenticate a user.
- Reuse the existing strict v2 configuration contract. Never silently overwrite a user-supplied versioned configuration; require a clear resolution if choices conflict.
- Preserve selection across Back/Next. ComfyUI runtime settings remain per Host.

### 4. Existing source and data discovery
- Retain independent **existing source checkout inspection** and **existing user-data discovery**; application data must be found even when no source checkout exists.
- Retain native browse dialogs for source folder, database file, install folder and data folder, plus the ability to rescan default application data.
- Detect multiple database candidates and allow an explicit selection. Display provisional header detection separately from completed integrity/schema inspection.
- **Exactly one** visible “Inspect selected database (read-only)” action, whether the candidate was auto-discovered or chosen manually.
- Source inspection is read-only; source recognition alone is not publisher verification or permission to install.
- Existing DB unlock password only when required; **new destination DB password and confirmation are always required**, even for a fresh install. Gate Next on the new password policy; errors must be actionable.
- Never alter the source DB during inspection. Display a concise inspection status and actionable blockers, not a raw schema or database JSON dump. An unversioned legacy schema needs an explicit registered migration mapping, not a guessed version.

### 5. Data review — editable application database records
- **Always show this page**, for both fresh installs (editable defaults) and DB imports (detected values prefilled).
- Show **actual editable Minglefield application configuration**, grouped by the corresponding application's sections/tabs, rather than only Paths/Database/Security metadata. Use tabs corresponding to **Anmeldung, Hosts (including per-host runtimes/settings), Effekte, Jobs and Games**. Show actual database values as editable fields, not migration metadata or installation paths. The exact fields and mapping must be grounded in the application schema and actual GUI, not invented.
- Distinguish **editable configuration values** from historical/transactional records and credentials. Do not expose or edit password hashes, session tokens, private credentials, audit journals or job history as ordinary settings. Do not silently rewrite identities/foreign keys.
- Corrected settings must feed the effective migration/install plan and be validated before execution. Editing review values must not change setup mode or discard versioned config.
- If source schema is unsupported, display a precise blocker; do not pretend all records can be safely edited or migrated.

### 6. Final review / installation summary
- Present the **Paths, Database and Security** tabs moved from the previous Data Review page, then a single complete installation-plan check including the database migration, without a separate migration-summary output box.
- Show **the effective settings** (mode, selected source, installation/data paths, per-host configuration, DB import vs fresh creation, encryption requirement, validation/migration readiness), not stale or ignored input values.
- Provide explicit validation and errors before installation; do not expose secrets in the summary or logs.
- On actual execution, show migration/install outcome, verification and rollback/failure status; do not claim installation succeeded from a preview alone.
- Optional runtimes and host provisioning remain opt-in and require the previously agreed trust/consent checks.

## State, UX and safety invariants
- Forward/back navigation preserves all selected modes, submodes, paths, imported corrections and other inputs. No implicit resets.
- Passwords may be deliberately cleared for security when appropriate, but must not silently allow proceeding with invalid/empty destination credentials.
- No duplicated action buttons. Native picker controls and review sections remain part of the **existing wizard**.
- Keep read-only inspection and actual migration/installation execution clearly distinguished.
- Preserve cross-platform Windows/Linux/macOS behavior and CI. Prioritize executable migration, configuration mapping, validation and a real Shadow test over cosmetic refactors.

## Current implementation gaps as observed 2026-11-04
- Source SQLite integrity inspection succeeds on Shadow (27 tables; application_id=0, user_version=0; migrationEnabled=false). This is **not** migration execution.
- New DB password currently has only advisory JavaScript feedback; wizard Next does not enforce it, and there is no execution-boundary enforcement.
- The data review page currently exposes only Paths/Database/Security metadata, not the required actual editable application settings.
- The duplicate SQLite inspect button was removed in commit `3a02f23`.
- SQLCipher-related lockfiles and CI are green per Shadow report, but encrypted destination creation, full legacy mapping, verified import and execution remain to be completed.

## Completion criteria
1. Fresh install cannot proceed without compliant confirmed password and creates **only** SQLCipher DB.
2. Legacy import cannot proceed without compliant confirmed destination password and successfully migrates a known schema to **a new encrypted DB**, preserving the source byte-for-byte.
3. Inspection/preview/editable configuration and final summary work in both paths; effective values are honored.
4. Unknown schema, wrong passwords, existing target, integrity mismatch, or migration failure safely blocks completion without corrupting source or claiming success.
5. CI and a real Shadow end-to-end test confirm these paths.
