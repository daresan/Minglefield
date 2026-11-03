# Tauri 2 installer GUI — non-installing proof of concept

This GUI calls the existing Rust `minglefield-installer-core::plan` function, the same one used by `installer-cli`. It only previews plans. It does not copy files, download dependencies, verify publisher signatures, install runtimes, authenticate, or claim Hosts. Do not distribute as a functional installer.

On a trusted developer workstation with Node.js/npm, Rust and Tauri OS prerequisites:

```powershell
cd installer/gui
npm install
npm run dev
```

This is a development command, **not** an end-user prerequisite. Do not commit `node_modules` or `src-tauri/target`. Before release, pin dependencies with a lockfile, establish a fully offline verified asset/build pipeline, add platform packaging, and test the packaged entrypoints. The workspace root `installer/Cargo.toml` deliberately excludes this separate Tauri crate for now, so existing Rust CI remains independent of Tauri OS prerequisites.

Both GUI and CLI use the same Rust planning function, but this does not yet establish a common packaged executable or silent installation. Those are still required by the phase specification.
