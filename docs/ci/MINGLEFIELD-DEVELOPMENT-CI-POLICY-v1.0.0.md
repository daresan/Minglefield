# Minglefield Development CI Policy (MDCI) v1.0.0

**Status:** implementation committed on `feat/game-integration-updates`; first optimized CI acceptance pending.
**Previous behavior / rollback baseline:** `c1bfd5a26f01444de4349836c463eaa5bd4f65be`.
**Scope:** GitHub Actions, automated code checks, engineering gates and portable
Minglefield application setup-manager packaging. Not the application runtime,
not the Minglefield Agent Protocol (MAP) version, and **not ComfyUI workflows**.

## Terminology / Begriffsabgrenzung

| Term | Meaning |
| --- | --- |
| **MDCI / Minglefield Development CI** | Versioned engineering test and release policy; GitHub Actions runs for Minglefield source code |
| **CI check / Prüfjob** | `cargo fmt/check/clippy/test`, Node tests, Python conformance or security verification; may compile test executables, but does not produce portable distribution artifacts |
| **Milestone acceptance build / Abnahme-Build** | An explicitly requested Windows portable EXE, Linux AppImage and macOS app bundle; produces downloadable GUI artifacts |
| **ComfyUI workflow / ComfyUI-Workflow** | A graph of nodes for generative image/video/3D execution on a configured Host; NEVER a reference to GitHub CI |
| **M2.nn** | Product/installer subgoal identifier, independent of the MDCI version |

Use **CI pipeline**, **GitHub Actions run**, **MDCI check**, or **acceptance
build** in engineering discussions; reserve the unqualified phrase
"ComfyUI workflow" for ComfyUI node graphs. Do not create a new Minglefield
effect or job to represent a GitHub CI action.

## Versioning, scope and rollback

- MDCI follows `MAJOR.MINOR.PATCH`: major for breaking CI/required-check or
  packaging-trigger changes, minor for new check classes or acceptance
  contracts, patch for compatible trigger/test corrections.
- The current source-of-truth is the active Git-tracked `.github/workflows/`
  YAML plus this policy. The version **does not clone runnable workflows** or
  start a second CI infrastructure.
- `v0` means the historical **unversioned baseline**, commit
  `c1bfd5a26f01444de4349836c463eaa5bd4f65be`, not an invented
  old tagged release. The baseline is immutable in Git history.
- Roll back with a **new reviewed commit on the authorized existing branch**
  (no force-push, no branch switching or rewriting published history):
  restore the three changed baseline workflow files from the SHA above,
  remove the three new v1 workflow files, remove/adjust the v1 policy
  regression gate and references, then run the required checks. For example,
  from an authorized checkout, after reviewing the diff:

  ```sh
  git restore --source=c1bfd5a26f01444de4349836c463eaa5bd4f65be -- \
    .github/workflows/installer-rust.yml \
    .github/workflows/installer-tauri-packaging.yml \
    .github/workflows/game-installation-security.yml
  git rm .github/workflows/installer-gui-frontend.yml \
    .github/workflows/installer-gui-native.yml \
    .github/workflows/installer-native-security.yml
  # Reconcile scripts/test_minglefield_ci_policy.py and the AGENTS guard
  # invocation; retain later unrelated changes and review the complete diff.
  git diff --check
  ```

- The operator explicitly approves a rollback; restoring file contents is
  not permission to bypass branch protection or to roll back product code.
- Before changing required-status contexts or merging to `main`, inspect the
  GitHub branch ruleset. The existing `rust (OS)` and `Tauri GUI / OS`
  names are retained when those matrix jobs run, but path-scoped/skipped
  workflows **cannot safely be required for every commit** without an
  appropriate aggregate required check. No ruleset change is performed by
  this policy.

## Three operating stages (aligned with docs/TEST-STRATEGY.md)

### A. Routine development / T1

- Ordinary, relevant core changes: `installer-rust.yml` runs **Ubuntu only**
  with Rust formatting, locked check, clippy, Rust unit tests, the genuine
  Rust-to-Python SQLCipher interoperability test, offline installer scripts
  and the established audit scripts.
- GUI browser/frontend changes: `installer-gui-frontend.yml` runs Node
  tests and the frontend build on **Ubuntu only**.
- Native Tauri Rust/bridge changes: `installer-gui-native.yml` runs the
  existing GUI and Tauri Rust checks on **Ubuntu only**.
- Documentation-only commits do **not** trigger installer cargo/Tauri
  builds; `AGENTS security guard` stays inexpensive and unconditional.
- Jobs do not upload a portable EXE, AppImage or macOS app.
- Superseded ordinary push runs for the same workflow/ref can be cancelled
  by GitHub concurrency. Manual acceptance runs are a different event group
  and are **not intentionally cancelled** by new ordinary pushes.

### B. Integration, native security and merge / T2–T3

- Edits to native SQLCipher, migration, path/snapshot fidelity and local
  Host trust boundaries additionally trigger
  `installer-native-security.yml`: Windows + macOS core/security
  integration tests. Together with the regular Ubuntu core job this gives
  three-OS evidence **without packaging artifacts**.
- Pull requests touching installer core run the full three-OS
  `installer-rust.yml` matrix; pull requests touching native GUI or shared
  core dependencies run the full three-OS `installer-gui-native.yml`
  matrix. This is an intentional pre-merge security/compatibility gate.
- `game-installation-security.yml` remains three-OS but triggers only for
  Game installation, shared Alpha/Host/security, or corresponding test/
  dependency files. Unrelated installer commits no longer start it.
- The separate MAP and general platform-manifest workflows remain in place.
  They are not deleted or claimed as Minglefield-installer acceptance.
  Further scoping of their broad Python test suites is a **separate
  measured optimization**, not a silent reduction of coverage here.
- `workflow_dispatch` on core/native-GUI checks selects a three-OS gate
  (default true). Use it for a completed high-risk subgoal if its normal
  change set did not already produce the required evidence.
- Record exact commit SHA, each OS/job conclusion, skipped checks, and
  failed or unavailable runners separately. An attempted job is not a pass.

### C. User-visible acceptance / T4

- Portable packaging `installer-tauri-packaging.yml` has **only**
  `workflow_call` and `workflow_dispatch`: no automatic push or PR
  artifact builds (including on `main`).
- `installer-portable-milestone.yml` is the existing explicit gate:
  a deliberately updated `installer/gui/PORTABLE-TEST-REQUEST.md` on the
  current feature branch calls packaging once. The owner may also
  intentionally dispatch packaging.
- **One acceptance build per completed, user-visible named subgoal**, after
  necessary checks, unless a specific failed-build repair must be retested.
  Technical-only subgoals are accepted with T1–T3 and are bundled into the
  next user-visible build. Do not generate a portable build merely to
  inspect documentation or to demonstrate a unit test.
- Capture milestone ID, exact source SHA, required T1–T3 evidence,
  functional GUI/CLI steps, negative security cases, OS artifact list,
  observed results, owner acceptance and remaining limitations.
- Do not assume a built bundle proves the installed **Minglefield
  application** exists or launches. The portable Setup Manager is distinct
  from the application being installed.

## Workflow map (v1.0.0)

| File | Automatic scope | OS on ordinary push | Can produce portable artifacts? |
| --- | --- | --- | --- |
| `agents-security.yml` | every authorized push/PR | Ubuntu | No |
| `installer-rust.yml` | installer-core, relevant shared runtime and installer scripts | Ubuntu | No |
| `installer-gui-frontend.yml` | HTML/JS/CSS/SVG/Node package metadata | Ubuntu | No |
| `installer-gui-native.yml` | Tauri backend, native GUI dependencies, selected core API changes | Ubuntu | No |
| `installer-native-security.yml` | native encryption, migration, path and Host security changes | Windows + macOS | No |
| `game-installation-security.yml` | Game installation and shared Alpha/Host security changes | Windows + Linux + macOS | No |
| `installer-portable-milestone.yml` | explicit marker or manual dispatch | Windows + Linux + macOS | **Yes** |
| `installer-tauri-packaging.yml` | manual dispatch or reusable call only | Windows + Linux + macOS | **Yes** |

Changes that touch several domains can legitimately run multiple independent
suites. Branch protection and third-party API limitations mean that a
"single run for every possible change" would otherwise conceal skipped
security evidence. Prefer the smallest meaningful number of runs instead
of a false universal green status.

## Under-goal acceptance map: active M2 installer milestone

| ID | Under-goal | Required acceptance evidence | User-visible portable build |
| --- | --- | --- | --- |
| M2.01 | Portable Tauri Setup Manager | offline GPL/README; portable launch without installing manager | Previously accepted |
| M2.02 | Database inspection and editor | verified fields, schema coverage, accepted edits, source untouched | Previously accepted |
| M2.03 | Temporary SQLCipher migration proof | independent full row/schema roundtrip; wrong key rejected; all temporary files cleaned | Previously accepted |
| M2.04 | Rust/Python SQLCipher interoperability | Python reads Rust ciphertext; independent login; no remote Host rights or replay | **No** (three-OS CI) |
| M2.05 | Destination-volume rehearsal | private staging on selected volume; occupied targets preserved; no real publication | **No** (native CI) |
| M2.06 | Atomic encrypted destination publication | explicit approval; exclusive final target; fidelity after publish; no source write | **Yes** when wired into a usable GUI |
| M2.07 | Crash recovery and rollback | interruption matrix before/during/after publish, safe restart and cleanup | **Yes** |
| M2.08 | First-run `mingleadmin` and local Host handshake | single-use authenticated local consent, separate credentials, scoped owner, no invite | **Yes** |
| M2.09 | Encrypted operational runtime | real authenticated login, durable Host/Effects/Jobs/Game persistence, key-unlock failure handling | With M2.10 |
| M2.10 | Python/runtime application packaging | clean-machine app install and launch with pinned runtime; no developer tools | **Yes** |
| M2.11 | Standard, Advanced and CLI installation | safe paths, option consent, GUI/CLI parity, actual installation | **Yes** |
| M2.12 | Optional Conda and ComfyUI | discover/reuse/manual select; explicit opt-in; Host-owned runtime settings | **Yes** |
| M2.13 | Update, repair and uninstall | idempotence, data retention, recovery, no cross-install overwrite | **Yes** |
| M2.14 | Native OS acceptance | Windows/Linux/macOS clean/preexisting installations and negative paths | **Yes**, release candidate |
| M2.15 | Alpha release | verified manifest, payloads, dependency closure, release documentation | **Yes**, release artifact |

These are **acceptance definitions, not claims of completion**. The
previous Shadow approval applies only to its previously tested scope.
The destination-volume rehearsal M2.05 was committed separately and
still needs actual CI evidence at this policy revision.

**Detailed executable acceptance cases:** [M2 Subgoal Acceptance v1.0.0](M2-SUBGOAL-ACCEPTANCE-v1.0.0.md).
This companion contains the positive, negative, recovery and data-preservation
cases for each named M2 subgoal. Its definitions are test targets, not
retroactive proof of completion.

## Mandatory acceptance-build request contents

Update the **existing** `installer/gui/PORTABLE-TEST-REQUEST.md` only when
an under-goal is ready for a new package. Do not update it for engineering
progress notes, CI-only fixes or draft policy revisions.

```text
Milestone/subgoal: M2.nn — <name>
Source branch and exact source commit: <branch> / <SHA>
Reason for new portable packages: <user-visible behavior>
CI acceptance: <required run links, OS jobs, actual status>
Operating systems: Windows EXE / Linux AppImage / macOS app
Manual positive case: <steps, expected observable result>
Manual negative case: <failure/conflict/restart/authorization behavior>
Data-preservation assertions: <source, output, secrets, existing owners>
Known limitations and explicit execution gates: <true/false>
Maintainer acceptance: pending / accepted / rejected with evidence
```

The marker change itself produces a **new** packaging commit; record the
actual packaging SHA/run and verify its source code is the just-accepted
implementation. Do not present the request's previous SHA as the packaged
commit. Always avoid placing passwords or actual database values in notes.

## Run reporting and measurement

- For each code change, report the relevant **single scoped GitHub Actions
  run** where possible; explicitly name additional native security jobs
  if they triggered. Do not wait for an unrelated long-running job to
  continue independent development.
- The existing GitHub connector can inspect jobs/artifacts **given a run
  ID**. Its commit-run lookup may omit push-triggered runs; empty results
  are not proof that CI is green or absent. Prefer GitHub-native read-only
  API/checks retrieval when supported; browser-tab access is an exceptional
  separately disclosed fallback, not an implicit dependency.
- Record the median and p90 queued+run durations, number of runs/runner
  minutes, and number of portable artifacts for at least five ordinary
  changes and two subgoal gates before claiming a numeric speed improvement.
- Fail closed for missing required security checks and for unverified
  releases. Do not auto-merge, deploy or enable migration on a green CI run.
