# P1.4f.2a — Game integration metadata contract (draft)

Status: design contract for **read-only inspection**; not a published package format, migration or release.

## Existing boundaries

- `.minglefield/project.json` is the implemented local workspace manifest (`schema_version: 1`, `project_id`). Existing files are preserved.
- MAP's `game-manifest.schema.json` describes game discovery and capability negotiation; its `manifest_version` and `map_versions` are not package versions.
- The proposed `minglefield.yaml` / `minglefield.lock` package format is not implemented. Do not introduce a competing package manager.
- A GitHub release is not proof of a Minglefield integration's identity or installed version.

## Identities and trust

- `integration_id`: stable, namespaced, provider-independent identifier. Unique within a project. An ID does **not** imply that the package is installed.
- `installed_version`: a separately recorded, explicitly verified package version; never derived from MAP version, manifest schema version, release tag or Git commit alone.
- `release_source`: provider and repository resolved from **trusted integration definitions** maintained by Minglefield. Never accept a game-supplied URL or query parameter as authoritative for installation.
- `source_revision`: optional verified immutable revision/hash for provenance; distinct from the human-readable version.
- `status`: `verified`, `unverified` or `unknown`. Only a verified installation record may be used to assert that an update is available.
- Multiple independently versioned integrations per game are supported; zero is valid.

## Proposed conceptual records (not yet persisted)

Trusted definition:
```json
{"integration_id":"minglefield.game.core",
 "release_source":{"provider":"github","repository":"example/official-integration"}}
```

Installed record:
```json
{"integration_id":"minglefield.game.core",
 "installed_version":"1.0.0",
 "source_revision":null,
 "status":"verified"}
```

These are **illustrative placeholders**, not claims that the package or release exists. The final manifest/lockfile placement is pending the package-format decision.

## Read-only state rules

1. Missing or legacy workspace manifest: installed integrations **unknown**, not an empty verified set.
2. Compatible v1 manifest without explicit integration metadata: **unknown**; never infer installed packages.
3. Explicit verified empty set (future format): no installed integrations; distinct from unknown.
4. Duplicate IDs, malformed records, unknown IDs or conflicting provenance: report validation errors, not silent deduplication or automatic source selection.
5. Missing trusted release source or inaccessible provider: availability **unknown**, not `up_to_date`.
6. Release comparison requires a verified installed version, a trusted source and a standard SemVer implementation; draft/prerelease policy is separate.
7. No implicit filesystem writes, Git operations, dependency installs or network access during local inspection.

## Acceptance gates

- Read-only inspection and owner isolation tested with legacy and malformed data.
- Confirm source definitions and version metadata against the eventual portable package/lockfile format before persisting anything.
- Preserve existing Game projects, MAP schemas, repository remotes and files.
- Add release comparison, UI display and opt-in installation only in later stages.

## P1.4f.2 version-policy clarification (2026-11-03)

The provisional SemVer wording above is superseded for read-only discovery by the
[PEP 440 stable-channel and separate comparison-state contract](GAME-INTEGRATION-UPDATE-DISCOVERY.md).
Declaration comparison never promotes installation or artifact verification.
