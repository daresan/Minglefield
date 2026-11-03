# P1.4f.2 — Read-only integration update discovery

## Architecture and state contract

The existing owner-scoped `alpha_game_projects` lookup and `inspect_game_integrations`
remain the authority boundary. Discovery reuses the validated curated registry and
both existing read-only lock readers. Root `minglefield.lock` is the unified target;
the alpha lock is legacy input. Collision, malformed and missing locks are never
silently merged, repaired or interpreted as a verified empty installation.

`GET /api/game/integration/releases?host_id=…&project_id=…` invokes the existing
`discover_integration_update` engine separately for each declared integration.
Authorization precedes registry, filesystem and remote discovery. Missing identity
returns 401; another owner's project returns 404 without fetching releases.
Client-selected sources, including empty query parameters, are rejected with 400.
The legacy `update-status` route retains its manifest report but no longer fetches
client-provided repositories, including through direct policy calls.

Each integration has `comparison_basis: declared_version`, `version_scheme: pep440`
and one `comparison_state`:

| Value | Meaning |
| --- | --- |
| `update_available` | A stable published version exceeds the lock declaration. |
| `up_to_date` | No stable version in the complete bounded response exceeds the declaration. This includes a declaration ahead of published releases. |
| `unknown` | Missing/untrusted source, unsupported declaration, empty/noncomparable catalog or explicitly incomplete catalog. |
| `error` | Invalid input/catalog/metadata or failed provider request (offline, timeout, HTTP failure, oversized or paginated response). |

The separate existing `state` and `verification_state` remain `unknown`.
`installation_allowed` is always false. An editable lock never establishes the
installed version: the response now labels it `declared_version`, not
`installed_version`. Existing `version_comparison` remains for compatibility.
No aggregate current-status claim is made across integrations; one offline source
does not suppress another integration's successful comparison.

## Version decision: PEP 440, not strict SemVer

Use the existing `packaging.version.Version` dependency (`requirements-ci.txt`),
with no handwritten parser or new dependency. This is explicitly a PEP 440 stable
public-version channel, not a claim of SemVer compatibility. It supersedes earlier
provisional SemVer requirements for this read-only milestone.

- Library normalization accepts a leading `v`, whitespace, and equivalent numeric
  releases (`1.2` equals `1.2.0`). Numeric ordering makes `1.10` newer than `1.9`.
- PEP 440 epochs and post releases retain their library-defined ordering.
- Drafts, GitHub prereleases and parsed pre/development releases are excluded.
  Pre/development declarations return unknown rather than crossing release channels.
- Local suffixes (`+build`) are excluded on both sides: PEP 440 local ordering differs
  from SemVer build metadata. Invalid or unsupported release tags are not guessed.
- Original release tags are retained for display and the existing comparison URLs.
  Normalized versions do not manufacture Git refs. Missing comparison refs keep
  changed-file preview unknown without invalidating the version comparison.

Reference: [packaging Version documentation](https://packaging.pypa.io/en/stable/version.html).
A future strict SemVer channel requires an explicit contract/dependency decision;
never silently reinterpret existing declarations or mutate lockfiles.

## Untrusted metadata and bounded I/O

The existing GitHub adapter uses an eight-second timeout and a 1 MiB response cap.
The first page contains at most 30 releases. A next-page Link causes an unavailable
result rather than a false current result; pagination is deliberately not followed
in this bounded slice. Malformed records and non-boolean release flags fail closed.
Release links must belong to the registry repository on HTTPS github.com.

The existing Game dialog displays comparison state, reason, version scheme, release
URL, timestamp and notes through `textContent`. Release text is never executed,
rendered as HTML, or interpreted as compatibility, artifact or installation evidence.
The indicator remains grey for unverified current declarations, yellow for a newer
release requiring review. There is no new install action or release-source field.

## Changed files and verification

- `server/game_integration_updates.py`: explicit comparison states and PEP 440 policy.
- `server/game_release_metadata.py`: incomplete/malformed response safeguards.
- `server/sec01_host_commit_policy_sim.py`: disable legacy arbitrary-source fetching.
- `server/private_alpha_gateway.py`: strict discovery queries and text-only UI fields.
- Five focused test modules cover comparison, adapter failures, policy/HTTP owner
  isolation, multiple independent integrations, unchanged repository bytes and UI
  rendering. No actual Game repository, manifest, lock, remote or branch is changed.
- Roadmap, continuity and integration contracts link this decision.

Validation on 2026-11-03:
- Full conformance discovery: 501 tests passed (172.221 seconds).
- The UI rendering test was added during that run; the final JavaScript module
  was separately rerun: 3 tests passed, including syntax and text-only rendering.
- MAP v0.1: 13 schemas, 6 action messages, 5 negotiation cases, 3 negative controls
  and shared-agent authorization checks passed.
- `git diff --check` passed.

Environment limitation: these runs used PATH Python, subsequently identified as
`hermes-agent/venv/Scripts/python.exe`, not the confirmed Minglefield environment.
Repeat the complete suite and MAP validator with the Minglefield interpreter before
closing the milestone. The user was asked for its location. Initial sandbox attempts
failed on temporary-directory/socket access; a workspace-local temp attempt also
triggered Git nesting checks. Those failed attempts are not acceptance results.
No dependency installation, production-server restart or live GitHub request was
performed for testing.

## Remaining P1.4f.3 and P1.4f.4 work

P1.4f.3: the existing release-note/tag-diff preview is advisory. Complete trusted
compatibility and migration assessments, local conflict analysis, clear manual-review
paths and real browser interaction coverage. Registry admission of a real integration
is still pending; the production registry remains intentionally empty.

P1.4f.4: bind independently verified installed bytes and authorized release/artifact
evidence to the existing journal, then explicit owner approval, conflict detection,
audited installation, rollback/recovery and post-install reinspection. Test tampering,
partial failures and recovery end-to-end. No installer or new update engine is added
by P1.4f.2. The full P1.4f delivery gate remains open.


## P1.4f.4 implementation sequence (2026-11-03)

The read-only `game_integration_install_preflight.py` is an **internal contract**, not an installation API. It requires independent server-side evidence for release binding, expected and observed artifact digests, installed-byte verification, project revision, filesystem conflict analysis and explicit owner confirmation. Even with all gates satisfied it returns `ready_for_transaction` with `installation_allowed: false` until a transactional executor and recovery journal exist. Tests are in `test_game_integration_install_preflight.py`; execution is pending on Shadow.

Next implementation slices, in order:

1. Specify a provider-neutral, server-attested installation plan and path containment policy; reject symlinks, traversal, duplicate destinations and concurrent revision changes. A lockfile declaration is never proof of installed bytes.
2. Introduce a durable host/project-scoped journal with states `prepared`, `applying`, `committed`, `rollback_required`, `rolled_back` and `manual_recovery_required`. Recovery must be idempotent and fail closed after interrupted writes.
3. Implement staging, independent digest checks, collision detection, owner confirmation, atomic replacement where possible and deterministic rollback, preserving unrelated files and the game's Git history.
4. Expose preview/confirm/recovery status through existing Games and Hosts architecture, with an actual browser test before milestone acceptance. Do not introduce a central approval requirement or hardcoded local machine paths.

Do not claim P1.4f.4 complete until tampering, partial failures, crash recovery and UI confirmation have been exercised.

## Cross-platform verification policy (2026-11-03)

Minglefield targets **Windows, Linux and macOS**. The Windows Shadow workstation
is the currently available **manual** testing environment; neither Linux nor
macOS hardware is currently available to the project operator. This does not
justify Windows-only filesystem semantics or platform-specific runtime paths.

For P1.4f.4:
- Use portable forward-slash relative installation paths and reject traversal,
  symlink escapes, Windows-reserved names, case-folding collisions and existing
  destinations until explicit backup/replacement handling exists.
- Isolate platform-sensitive file operations (atomic rename/replacement,
  filesystem sync, locking, directory metadata) behind an explicit adapter.
  Never assume identical durability guarantees across filesystems or OSes.
- Add a **small GitHub Actions matrix** with `windows-latest`, `ubuntu-latest`
  and `macos-latest` for focused installation and recovery tests. Keep the
  broad conformance suite on its existing cadence. Monitor Actions consumption,
  particularly macOS runner cost.
- Treat green hosted CI as **automated compatibility evidence**, not as a
  substitute for manual installation testing on Linux/macOS. Record skipped
  symlink tests and any OS-specific skips instead of counting them as coverage.
- Do not mark the matrix verified until the actual GitHub Actions jobs run and
  pass. A committed workflow alone is not a passing result.

This policy preserves operator-controlled source trust and does not add a
central registry or central installation approval service.
