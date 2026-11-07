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
    validate_local_credentials(
        login_user_id,
        login_password,
        database_password,
        LOCAL_ADMIN_CONFIRMATION,
    )
    .map_err(str::to_owned)?;
    if !valid_login_name(local_host_id) || !local_host_id.starts_with("local.") {
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
    let request = serde_json::json!({
        "version": 1,
        "databasePath": database,
        "sqlcipherKey": database_password,
        "loginUserId": login_user_id,
        "loginPassword": login_password,
        "localHostId": local_host_id,
    });
    let mut child = Command::new(&python)
        .arg("-I")
        .arg("-B")
        .arg(&worker)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "Could not launch installed local first-run worker")?;
    let payload = serde_json::to_vec(&request)
        .map_err(|_| "Could not encode private first-run request")?;
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
    if receipt.status != "local_host_admin_created"
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
            "mingleadmin", "SeparateLogin123!", "DatabaseCipher123!", LOCAL_ADMIN_CONFIRMATION
        ).is_ok());
        assert!(validate_local_credentials(
            "mingleadmin", "SharedPassword123!", "SharedPassword123!", LOCAL_ADMIN_CONFIRMATION
        ).is_err());
        assert!(validate_local_credentials(
            "mingleadmin", "SeparateLogin123!", "DatabaseCipher123!", "WRONG"
        ).is_err());
        assert!(!valid_login_name("../mingleadmin"));
        assert!(valid_login_name("mingleadmin"));
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
