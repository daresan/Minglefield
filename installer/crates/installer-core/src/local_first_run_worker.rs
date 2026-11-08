//! Shared private worker invocation for a strictly installation-bound local
//! Host-first-run transaction. This code does NOT mint an authorization permit:
//! GUI or CLI callers must independently establish a verified new DB, a
//! verified locally installed application and exact operator consent.
use serde::Deserialize;
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

pub const LOCAL_ADMIN_CONFIRMATION: &str = "ACTIVATE LOCAL HOST ADMIN";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LocalFirstRunResult {
    pub login_user_id: String,
    pub local_host_id: String,
    pub remote_host_authority_granted: bool,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct WorkerResponse {
    status: String,
    login_user_id: String,
    local_host_id: String,
    remote_host_authority_granted: bool,
}

pub fn valid_login_name(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 128
        && name
            .bytes()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, b'.' | b'_' | b'-'))
}

pub fn validate_local_credentials(
    login_user_id: &str,
    login_password: &str,
    database_password: &str,
    confirmation: &str,
) -> Result<(), &'static str> {
    if confirmation != LOCAL_ADMIN_CONFIRMATION
        || !valid_login_name(login_user_id)
        || !(12..=256).contains(&login_password.len())
        || login_password == database_password
        || database_password.is_empty()
        || database_password.len() > 4096
    {
        return Err("Separate local Host account credentials and consent required");
    }
    Ok(())
}

pub fn runtime_paths(installed: &Path) -> (PathBuf, PathBuf) {
    let python = if cfg!(windows) {
        installed.join("runtime/python/python.exe")
    } else {
        installed.join("runtime/python/bin/python3.11")
    };
    let worker = installed.join("application/server/installed_alpha_first_run.py");
    (python, worker)
}

/// Call the real existing Python admission/Host policy over one private pipe.
/// IMPORTANT: never call this function on an IPC-supplied DB/path/password
/// without a same-process native application+new-db authorization permit.
pub fn run_verified_local_first_run_worker(
    installed: &Path,
    database: &Path,
    database_password: &str,
    login_user_id: &str,
    login_password: &str,
    local_host_id: &str,
) -> Result<LocalFirstRunResult, String> {
    call_local_admin_worker(
        installed,
        database,
        database_password,
        login_user_id,
        login_password,
        local_host_id,
        false,
    )
}

/// Installation-only, append-or-reuse account operation. May be used with a
/// newly migrated database that already contains other users or Host owners.
/// Only the trusted native installer may call it on its selected SQLCipher
/// destination after one explicit installation consent.
pub fn ensure_verified_installer_local_admin(
    installed: &Path,
    database: &Path,
    database_password: &str,
    login_password: &str,
    local_host_id: &str,
) -> Result<LocalFirstRunResult, String> {
    call_local_admin_worker(
        installed,
        database,
        database_password,
        "mingleadmin",
        login_password,
        local_host_id,
        true,
    )
}

fn call_local_admin_worker(
    installed: &Path,
    database: &Path,
    database_password: &str,
    login_user_id: &str,
    login_password: &str,
    local_host_id: &str,
    allow_existing: bool,
) -> Result<LocalFirstRunResult, String> {
    if !allow_existing {
        validate_local_credentials(
            login_user_id,
            login_password,
            database_password,
            LOCAL_ADMIN_CONFIRMATION,
        )
        .map_err(str::to_owned)?;
    } else if login_user_id != "mingleadmin"
        || database_password.is_empty()
        || database_password.len() > 4096
        || login_password.len() > 256
        || (!login_password.is_empty() && login_password == database_password)
    {
        return Err("Invalid separate installer administrator credentials".into());
    }
    // A new Host must use a freshly generated local.* ID. An installer
    // migration may instead attach mingleadmin to an already verified Host
    // with its original ID (e.g. host.local). The trusted Python worker
    // rejects non-local IDs unless they exist and are active in the target DB.
    if !valid_login_name(local_host_id)
        || (!allow_existing && !local_host_id.starts_with("local."))
    {
        return Err("First-run Host ID must be local and well formed".into());
    }
    let (python, worker) = runtime_paths(installed);
    for path in [&python, &worker] {
        let meta = fs::symlink_metadata(path)
            .map_err(|_| "Managed local first-run worker is unavailable")?;
        if meta.file_type().is_symlink() || !meta.is_file() {
            return Err("Managed local first-run worker is not a regular file".into());
        }
    }
    let mut request = serde_json::json!({
        "version": if allow_existing { 2 } else { 1 },
        "databasePath": database,
        "sqlcipherKey": database_password,
        "loginUserId": login_user_id,
        "loginPassword": login_password,
        "localHostId": local_host_id,
    });
    if allow_existing {
        request["mode"] = serde_json::json!("ensure_local_admin");
    }
    let mut child = Command::new(&python)
        .arg("-I")
        .arg("-B")
        .arg(&worker)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "Could not launch installed local first-run worker")?;
    let payload =
        serde_json::to_vec(&request).map_err(|_| "Could not encode private first-run request")?;
    let delivered = child
        .stdin
        .take()
        .ok_or("Private first-run input pipe unavailable")
        .and_then(|mut input| {
            input
                .write_all(&payload)
                .map_err(|_| "Could not deliver private first-run input")
        });
    if delivered.is_err() {
        let _ = child.kill();
        let _ = child.wait();
        return Err("Could not deliver private first-run input".into());
    }
    let deadline = Instant::now() + Duration::from_secs(150);
    let success = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status.success(),
            Ok(None) if Instant::now() < deadline => {
                std::thread::sleep(Duration::from_millis(50));
            }
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("Installed local first-run worker did not finish".into());
            }
        }
    };
    if !success {
        return Err("Installed local first-run Host activation was refused".into());
    }
    let mut response = Vec::new();
    child
        .stdout
        .take()
        .ok_or("Installed local first-run result unavailable")?
        .take(8193)
        .read_to_end(&mut response)
        .map_err(|_| "Could not read installed local first-run receipt")?;
    if response.len() > 8192 {
        return Err("Installed local first-run receipt is oversized".into());
    }
    let receipt: WorkerResponse = serde_json::from_slice(&response)
        .map_err(|_| "Unrecognized installed first-run receipt")?;
    if !matches!(
        receipt.status.as_str(),
        "local_host_admin_created" | "local_host_admin_existing"
    ) || (!allow_existing && receipt.status != "local_host_admin_created")
        || receipt.login_user_id != login_user_id
        || receipt.local_host_id != local_host_id
        || receipt.remote_host_authority_granted
    {
        return Err("Installed first-run receipt does not match local approval".into());
    }
    Ok(LocalFirstRunResult {
        login_user_id: login_user_id.to_owned(),
        local_host_id: local_host_id.to_owned(),
        remote_host_authority_granted: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn explicit_approval_and_separate_passwords_required() {
        assert!(validate_local_credentials(
            "mingleadmin",
            "SeparateLogin123!",
            "DatabaseCipher123!",
            LOCAL_ADMIN_CONFIRMATION
        )
        .is_ok());
        assert!(validate_local_credentials(
            "mingleadmin",
            "SharedPassword123!",
            "SharedPassword123!",
            LOCAL_ADMIN_CONFIRMATION
        )
        .is_err());
        assert!(validate_local_credentials(
            "mingleadmin",
            "SeparateLogin123!",
            "DatabaseCipher123!",
            "WRONG"
        )
        .is_err());
        assert!(!valid_login_name("../mingleadmin"));
        assert!(valid_login_name("mingleadmin"));
    }

    #[test]
    fn installer_can_reuse_existing_legacy_host_id_but_new_host_stays_local_scoped() {
        let installed = Path::new("/path/that/cannot/exist/managed-alpha");
        let database = Path::new("/path/that/cannot/exist/secret.db");

        // The installation path must reach the worker-file check for an
        // existing legacy ID instead of failing at local.* validation.
        let existing = ensure_verified_installer_local_admin(
            installed,
            database,
            "DatabaseCipher123!",
            "SeparateLogin123!",
            "host.local",
        );
        assert_eq!(
            existing.unwrap_err(),
            "Managed local first-run worker is unavailable"
        );

        // Only the trusted installed worker can verify whether this existing
        // Host ID really belongs to the selected encrypted database.
        let invalid = ensure_verified_installer_local_admin(
            installed,
            database,
            "DatabaseCipher123!",
            "SeparateLogin123!",
            "../remote",
        );
        assert_eq!(
            invalid.unwrap_err(),
            "First-run Host ID must be local and well formed"
        );

        // The original first-run path may not invent a new legacy/non-local ID.
        let fresh = run_verified_local_first_run_worker(
            installed,
            database,
            "DatabaseCipher123!",
            "mingleadmin",
            "SeparateLogin123!",
            "host.local",
        );
        assert_eq!(
            fresh.unwrap_err(),
            "First-run Host ID must be local and well formed"
        );
    }

    #[test]
    fn uninstalled_worker_cannot_be_launched() {
        let outcome = run_verified_local_first_run_worker(
            Path::new("/path/that/cannot/exist/managed-alpha"),
            Path::new("/path/that/cannot/exist/secret.db"),
            "DatabaseCipher123!",
            "mingleadmin",
            "SeparateLogin123!",
            "local.0123456789abcdef0123456789abcdef",
        );
        assert!(outcome.is_err());
    }
}
