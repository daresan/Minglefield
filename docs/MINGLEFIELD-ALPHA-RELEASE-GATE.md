# Minglefield Alpha — release readiness gate (structural preflight)

The existing local Alpha UI is the initial product surface. **No public release is created by this gate**, and no installation, download, migration, Host claim or application launch occurs.

Run the read-only check from a checkout with Python 3.10+:

```powershell
python -B installer/scripts/check_alpha_release_readiness.py --json
```

Exit code `3` means prerequisites are missing. Exit code `0` means only that the listed **structural checks** pass; it is **not** legal license approval, dependency-resolution proof, binary provenance, platform compatibility, or permission to ship. The JSON always reports `execution_enabled=false`.

Current expected blockers:

1. **Final LICENSE**: the repository's README explicitly states that licensing is pending. Do not insert a fake license or change the licensing decision merely to satisfy this gate. Complete the rights/dependency review and publish the agreed actual license first.
2. **Product runtime dependency lock**: `requirements-ci.txt` is for conformance, not a reproducible product runtime. Build and test a platform-aware dependency lock.
3. **Packaged launch contract**: the current browser Alpha UI is served by a Python reference gateway, not a standalone desktop application. Specify versioned launcher and data paths before packaging.
4. **End-to-end release evidence**: the separate GitHub source ancestry checker confirms source identity, not artifact/build equivalence. Build artifact hashes, reproducible or independently attested build provenance, actual release binding and clean-machine tests remain required.

The Alpha UI's **README & Lizenz** tab reads `README.md` and `LICENSE` from the running source tree and clearly reports the absent license. This read-only document viewer is **not** an installation license-acceptance gate. The eventual installer must show the exact packaged license and require explicit acceptance before any installation writes, then optionally offer README and app launch on successful completion.

Release order: finish rights/license review; declare and lock runtime; establish packaged launcher; build cross-platform Alpha artifacts; bind source/release/artifact evidence; test clean installs and upgrade/rollback; only then publish an Alpha release. No paid code-signing certificate is a Minglefield policy requirement, and OS security warnings must be communicated honestly.

The stricter game installation policy remains separate.
