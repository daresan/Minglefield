//! Local installation-bound, single-use first-run Host administrator activation.
//! The HTTP gateway must never expose this capability. Only verified outcomes
//! from this process's native encrypted-copy and application-file writers can
//! arm an activation; neither an IPC-supplied path nor a DB password alone can.
use minglefield_installer_core::integrity::sha256_reader_hex;
use serde::{Deserialize, Serialize};
use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::Manager;

#[derive(Default)]
pub struct FirstRunState {
    inner: Mutex<FirstRunPending>,
}

#[derive(Default)]
struct FirstRunPending {
    database: Option<VerifiedDatabase>,
    application: Option<PathBuf>,
    spent: bool,
}

struct VerifiedDatabase {
    path: PathBuf,
    digest: String,
    operation_id: String,
}

struct ActivationPermit {
    database: VerifiedDatabase,
    application: PathBuf,
}

impl FirstRunState {
    pub fn record_encrypted_copy(&self, path: &Path, operation_id: &str) -> Result<(), String> {
        let valid = operation_id.len() == 32
            && operation_id
                .bytes()
                .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase());
        if !valid {
            return Err("Invalid verified encrypted-copy operation identity".to_owned());
        }
        let meta = fs::symlink_metadata(path)
            .map_err(|_| "Verified encrypted destination unavailable".to_owned())?;
        if meta.file_type().is_symlink() || !meta.is_file() {
            return Err("Verified encrypted destination is not a regular file".to_owned());
        }
        let canonical = fs::canonicalize(path)
            .map_err(|_| "Cannot identify the new encrypted destination".to_owned())?;
        let (digest, bytes) = sha256_reader_hex(
            File::open(&canonical).map_err(|_| "Cannot reopen new encrypted destination")?,
        )
        .map_err(|_| "Cannot fingerprint verified encrypted destination")?;
        if bytes < 16 {
            return Err("Verified encrypted destination is incomplete".to_owned());
        }
        let mut state = self
            .inner
            .lock()
            .map_err(|_| "First-run authorization state unavailable".to_owned())?;
        if state.spent || state.database.is_some() {
            return Err("First-run copy authorization already used or reserved".to_owned());
        }
        state.database = Some(VerifiedDatabase {
            path: canonical,
            digest,
            operation_id: operation_id.to_owned(),
        });
        Ok(())
    }

    pub fn record_installed_application(&self, path: &Path) -> Result<(), String> {
        let meta = fs::symlink_metadata(path)
            .map_err(|_| "Installed Alpha directory unavailable".to_owned())?;
        if meta.file_type().is_symlink() || !meta.is_dir() {
            return Err("Installed Alpha directory is not a real directory".to_owned());
        }
        let canonical = fs::canonicalize(path)
            .map_err(|_| "Cannot identify installed Alpha directory".to_owned())?;
        let mut state = self
            .inner
            .lock()
            .map_err(|_| "First-run authorization state unavailable".to_owned())?;
        if state.spent || state.application.is_some() {
            return Err("First-run application authorization already reserved".to_owned());
        }
        state.application = Some(canonical);
        Ok(())
    }

    fn consume(&self) -> Result<ActivationPermit, String> {
        let mut state = self
            .inner
            .lock()
            .map_err(|_| "First-run authorization state unavailable".to_owned())?;
        if state.spent || state.database.is_none() || state.application.is_none() {
            return Err("Verified current-session copy and installation required".to_owned());
        }
        state.spent = true;
        Ok(ActivationPermit {
            database: state
                .database
                .take()
                .ok_or("Missing current-session database")?,
            application: state
                .application
                .take()
                .ok_or("Missing current-session application")?,
        })
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct WorkerResponse {
    status: String,
    login_user_id: String,
    local_host_id: String,
    remote_host_authority_granted: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FirstRunActivation {
    status: &'static str,
    login_user_id: String,
    local_host_id: String,
    remote_host_authority_granted: bool,
    application_launch_enabled: bool,
}

fn valid_login_name(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 128
        && name
            .bytes()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, b'.' | b'_' | b'-'))
}

fn runtime_paths(installed: &Path) -> (PathBuf, PathBuf) {
    let python = if cfg!(windows) {
        installed.join("runtime/python/python.exe")
    } else {
        installed.join("runtime/python/bin/python3.11")
    };
    let worker = installed.join("application/server/installed_alpha_first_run.py");
    (python, worker)
}

fn activate_with_permit(
    permit: ActivationPermit,
    login_user_id: String,
    login_password: String,
    database_password: String,
) -> Result<FirstRunActivation, String> {
    let db_meta = fs::symlink_metadata(&permit.database.path)
        .map_err(|_| "New encrypted database missing at activation")?;
    if db_meta.file_type().is_symlink() || !db_meta.is_file() {
        return Err("New encrypted database changed before activation".to_owned());
    }
    let (current_digest, size) = sha256_reader_hex(
        File::open(&permit.database.path).map_err(|_| "Cannot reopen new encrypted database")?,
    )
    .map_err(|_| "Cannot verify new encrypted database")?;
    if size < 16 || current_digest != permit.database.digest {
        return Err("New encrypted database changed since current-session copy".to_owned());
    }
    let expected = option_env!("MINGLEFIELD_ALPHA_INVENTORY_SHA256")
        .ok_or("Native setup manager is not bundled with a managed Alpha runtime")?;
    crate::alpha_application_install::verify_installed_application(&permit.application, expected)?;
    let (python, worker) = runtime_paths(&permit.application);
    for path in [&python, &worker] {
        let meta =
            fs::symlink_metadata(path).map_err(|_| "Managed Alpha first-run executable missing")?;
        if !meta.is_file() || meta.file_type().is_symlink() {
            return Err("Managed Alpha first-run executable is not a regular file".to_owned());
        }
    }
    let host_id = format!("local.{}", permit.database.operation_id);
    let request = serde_json::json!({
        "version": 1,
        "databasePath": permit.database.path,
        "sqlcipherKey": database_password,
        "loginUserId": login_user_id,
        "loginPassword": login_password,
        "localHostId": host_id,
    });
    let mut child = Command::new(&python)
        .arg("-I")
        .arg("-B")
        .arg(&worker)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "Could not start trusted local first-run worker")?;
    let payload =
        serde_json::to_vec(&request).map_err(|_| "Could not prepare first-run request")?;
    let write_ok = child
        .stdin
        .take()
        .ok_or("No private first-run input pipe")
        .and_then(|mut input| {
            input
                .write_all(&payload)
                .map_err(|_| "Could not deliver private first-run input")
        });
    if write_ok.is_err() {
        let _ = child.kill();
        let _ = child.wait();
        return Err("Could not deliver private first-run input".to_owned());
    }
    let deadline = Instant::now() + Duration::from_secs(150);
    let success = loop {
        match child.try_wait() {
            Ok(Some(result)) => break result.success(),
            Ok(None) if Instant::now() < deadline => {
                std::thread::sleep(Duration::from_millis(50));
            }
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("Local first-run worker did not finish successfully".to_owned());
            }
        }
    };
    if !success {
        return Err("Local first-run Host activation was refused".to_owned());
    }
    let mut response = Vec::new();
    child
        .stdout
        .take()
        .ok_or("Missing first-run worker result")?
        .take(8193)
        .read_to_end(&mut response)
        .map_err(|_| "Cannot read first-run worker result")?;
    if response.len() > 8192 {
        return Err("First-run worker result is oversized".to_owned());
    }
    let receipt: WorkerResponse = serde_json::from_slice(&response)
        .map_err(|_| "Unrecognized first-run activation result")?;
    if receipt.status != "local_host_admin_created"
        || receipt.login_user_id != login_user_id
        || receipt.local_host_id != host_id
        || receipt.remote_host_authority_granted
    {
        return Err("First-run activation did not match local authorization".to_owned());
    }
    Ok(FirstRunActivation {
        status: "local_host_admin_created",
        login_user_id,
        local_host_id: host_id,
        remote_host_authority_granted: false,
        application_launch_enabled: false,
    })
}

#[tauri::command]
pub async fn activate_first_run_local_admin(
    app: tauri::AppHandle,
    login_user_id: String,
    login_password: String,
    database_password: String,
    confirmation: String,
) -> Result<FirstRunActivation, String> {
    if confirmation != "ACTIVATE LOCAL HOST ADMIN"
        || !valid_login_name(&login_user_id)
        || !(12..=256).contains(&login_password.len())
        || login_password == database_password
        || database_password.is_empty()
        || database_password.len() > 4096
    {
        return Err(
            "Valid separate local first-run credentials and consent are required".to_owned(),
        );
    }
    let permit = app.state::<FirstRunState>().consume()?;
    tauri::async_runtime::spawn_blocking(move || {
        activate_with_permit(permit, login_user_id, login_password, database_password)
    })
    .await
    .map_err(|_| "Local first-run activation worker failed".to_owned())?
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn no_password_or_unverified_path_can_grant_activation() {
        let state = FirstRunState::default();
        assert!(state.consume().is_err());
        assert!(state
            .record_installed_application(Path::new("missing-dir"))
            .is_err());
        assert!(!valid_login_name("../admin"));
        assert!(!valid_login_name(""));
        assert!(valid_login_name("mingleadmin"));
        assert!(valid_login_name("local.user-1"));
        assert!(!valid_login_name("spaces are denied"));
    }

    #[test]
    fn first_run_session_proof_is_consumed_only_once() {
        let base = std::env::temp_dir().join(format!("mf-first-run-{}", std::process::id()));
        let _ = fs::remove_dir_all(&base);
        fs::create_dir(&base).unwrap();
        let database = base.join("new-cipher.sqlite3");
        fs::write(&database, b"disposable-test-not-real-encrypted-data").unwrap();
        let installed = base.join("installed");
        fs::create_dir(&installed).unwrap();
        let state = FirstRunState::default();
        assert!(state
            .record_encrypted_copy(&database, "0123456789abcdef0123456789abcdef")
            .is_ok());
        assert!(state.record_installed_application(&installed).is_ok());
        let permit = state.consume().unwrap();
        assert_eq!(
            permit.database.operation_id,
            "0123456789abcdef0123456789abcdef"
        );
        assert_eq!(permit.database.path, fs::canonicalize(&database).unwrap());
        assert_eq!(permit.application, fs::canonicalize(&installed).unwrap());
        assert!(state.consume().is_err());
        assert!(state.record_installed_application(&installed).is_err());
        assert!(state
            .record_encrypted_copy(&database, "fedcba9876543210fedcba9876543210")
            .is_err());
        fs::remove_dir_all(base).unwrap();
    }
}
