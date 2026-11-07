//! Local installation-bound, single-use first-run Host administrator activation.
//! The HTTP gateway must never expose this capability. Only verified outcomes
//! from this process's native encrypted-copy and application-file writers can
//! arm an activation; neither an IPC-supplied path nor a DB password alone can.
use minglefield_installer_core::db_operations::verify_encrypted_database;
use minglefield_installer_core::integrity::sha256_reader_hex;
#[cfg(test)]
use minglefield_installer_core::local_first_run_worker::valid_login_name;
use minglefield_installer_core::local_first_run_worker::{
    run_verified_local_first_run_worker, validate_local_credentials,
};
use minglefield_installer_core::managed_alpha_install::verify_installed_application;
use minglefield_installer_core::native_application_probe::{
    ensure_native_starter, probe_installed_application, start_installed_application,
    NativeRunningReceipt,
};
use serde::Serialize;
use std::fs::{self, File};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::Manager;

#[derive(Default)]
pub struct FirstRunState {
    inner: Mutex<FirstRunPending>,
}

#[derive(Default)]
struct FirstRunPending {
    database: Option<VerifiedDatabase>,
    application: Option<PathBuf>,
    // Retain verified launch context after one-time first-run consumption.
    launch_database: Option<PathBuf>,
    launch_in_progress: bool,
    launched: bool,
    active: bool,
    consumed_operations: std::collections::BTreeSet<String>,
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
        if state.active || state.launch_in_progress || state.consumed_operations.contains(operation_id) {
            return Err("First-run copy operation active or already consumed".to_owned());
        }
        if state
            .database
            .as_ref()
            .is_some_and(|v| v.operation_id == operation_id)
        {
            return Err("First-run copy already recorded".to_owned());
        }
        state.launch_database = Some(canonical.clone());
        state.launched = false;
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
        if state.active || state.launch_in_progress {
            return Err("First-run or native launch currently active".to_owned());
        }
        if state.application.as_ref() == Some(&canonical) {
            return Err("Application installation already recorded".to_owned());
        }
        state.application = Some(canonical);
        Ok(())
    }

    fn begin_launch(&self) -> Result<(PathBuf, PathBuf), String> {
        let mut state = self
            .inner
            .lock()
            .map_err(|_| "Native launch state unavailable".to_owned())?;
        if state.active || state.launch_in_progress || state.launched {
            return Err("First-run or native launch already active or completed".to_owned());
        }
        let database = state
            .launch_database
            .clone()
            .ok_or("Verified current-session encrypted copy required")?;
        let application = state
            .application
            .clone()
            .ok_or("Verified current-session application installation required")?;
        state.launch_in_progress = true;
        Ok((application, database))
    }

    fn finish_launch(&self, success: bool) {
        if let Ok(mut state) = self.inner.lock() {
            state.launch_in_progress = false;
            if success {
                state.launched = true;
            }
        }
    }

    fn validate_native_starter(&self) -> Result<(), String> {
        let root = {
            let state = self
                .inner
                .lock()
                .map_err(|_| "First-run authorization state unavailable".to_owned())?;
            if state.active || state.database.is_none() {
                return Err("Verified current-session setup required".to_owned());
            }
            state
                .application
                .clone()
                .ok_or("Verified application installation required")?
        };
        let expected = option_env!("MINGLEFIELD_ALPHA_INVENTORY_SHA256")
            .ok_or("Native setup manager has no packaged Alpha inventory")?;
        ensure_native_starter(&root, expected).map_err(str::to_owned)
    }

    fn validate_database_unlock(&self, password: &str) -> Result<(), String> {
        let path = {
            let state = self
                .inner
                .lock()
                .map_err(|_| "First-run authorization state unavailable")?;
            if state.active
                || state.launch_in_progress
                || state.database.is_none()
                || state.application.is_none()
            {
                return Err("Verified local database and application required".into());
            }
            state.database.as_ref().unwrap().path.clone()
        };
        use rusqlite::{Connection, OpenFlags};
        let conn = Connection::open_with_flags(
            &path,
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )
        .map_err(|_| "Cannot open the new encrypted database")?;
        conn.pragma_update(None, "key", password)
            .map_err(|_| "Cannot unlock the encrypted database")?;
        conn.query_row("SELECT count(*) FROM sqlite_schema", [], |r| {
            r.get::<_, i64>(0)
        })
        .map_err(|_| "Incorrect SQLCipher database password")?;
        Ok(())
    }

    fn consume(&self) -> Result<ActivationPermit, String> {
        let mut state = self
            .inner
            .lock()
            .map_err(|_| "First-run authorization state unavailable")?;
        if state.active
            || state.launch_in_progress
            || state.database.is_none()
            || state.application.is_none()
        {
            return Err("Verified current-session copy and installation required".to_owned());
        }
        let database = state.database.take().unwrap();
        if !state
            .consumed_operations
            .insert(database.operation_id.clone())
        {
            return Err("Already used first-run operation".to_owned());
        }
        state.active = true;
        Ok(ActivationPermit {
            database,
            application: state.application.as_ref().unwrap().clone(),
        })
    }

    fn finish(&self) {
        if let Ok(mut state) = self.inner.lock() {
            state.active = false;
        }
    }
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

fn activate_with_permit(
    permit: ActivationPermit,
    login_user_id: String,
    login_password: String,
    database_password: String,
    verify_native_start: bool,
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
    verify_installed_application(&permit.application, expected)?;
    if verify_native_start {
        ensure_native_starter(&permit.application, expected).map_err(str::to_owned)?;
    }
    let host_id = format!("local.{}", permit.database.operation_id);
    let receipt = run_verified_local_first_run_worker(
        &permit.application,
        &permit.database.path,
        &database_password,
        &login_user_id,
        &login_password,
        &host_id,
    )?;
    if verify_native_start {
        probe_installed_application(
            &permit.application,
            &permit.database.path,
            &database_password,
            expected,
        )
        .map_err(|_| {
            "Local Host created, but native startup verification failed; preserve installed files and database for review"
                .to_owned()
        })?;
    }
    Ok(FirstRunActivation {
        status: "local_host_admin_created",
        login_user_id: receipt.login_user_id,
        local_host_id: receipt.local_host_id,
        remote_host_authority_granted: receipt.remote_host_authority_granted,
        application_launch_enabled: verify_native_start,
    })
}

#[tauri::command]
pub async fn activate_first_run_local_admin(
    app: tauri::AppHandle,
    login_user_id: String,
    login_password: String,
    database_password: String,
    confirmation: String,
    verify_native_start: Option<bool>,
) -> Result<FirstRunActivation, String> {
    validate_local_credentials(
        &login_user_id,
        &login_password,
        &database_password,
        &confirmation,
    )
    .map_err(str::to_owned)?;
    let state = app.state::<FirstRunState>();
    // A typo in the SQLCipher password must not consume the operation permit.
    state.validate_database_unlock(&database_password)?;
    let verify_native_start = verify_native_start.unwrap_or(false);
    if verify_native_start {
        state.validate_native_starter()?;
    }
    let permit = state.consume()?;
    let result = tauri::async_runtime::spawn_blocking(move || {
        activate_with_permit(
            permit,
            login_user_id,
            login_password,
            database_password,
            verify_native_start,
        )
    })
    .await
    .map_err(|_| "Local first-run activation worker failed".to_owned());
    state.finish();
    result?
}

/// Start only the paths recorded by the current verified installation session.
/// No frontend-selected executable, Host ID, or database path is accepted.
#[tauri::command]
pub async fn start_installed_minglefield(
    app: tauri::AppHandle,
    database_password: String,
    confirmation: String,
) -> Result<NativeRunningReceipt, String> {
    if confirmation != "START INSTALLED MINGLEFIELD" {
        return Err("Explicit native Minglefield launch approval required".to_owned());
    }
    if database_password.is_empty() {
        return Err("SQLCipher unlock key required to start native Minglefield".to_owned());
    }
    let state = app.state::<FirstRunState>();
    let (application, database) = state.begin_launch()?;
    let result = tauri::async_runtime::spawn_blocking(move || {
        let meta = fs::symlink_metadata(&database)
            .map_err(|_| "Current-session encrypted database unavailable".to_owned())?;
        if !meta.is_file() || meta.file_type().is_symlink() {
            return Err("Current-session encrypted database is not a regular file".to_owned());
        }
        let checked = verify_encrypted_database(&database, &database_password)
            .map_err(|_| "SQLCipher unlock or integrity check rejected".to_owned())?;
        if !checked.alpha_users_table_present {
            return Err("Normal application account login not initialized".to_owned());
        }
        let expected = option_env!("MINGLEFIELD_ALPHA_INVENTORY_SHA256")
            .ok_or("Native Setup Manager has no approved application package")?;
        start_installed_application(&application, &database, &database_password, expected, true)
            .map_err(str::to_owned)
    })
    .await
    .map_err(|_| "Native Minglefield launch worker failed".to_owned())
    .and_then(|result| result);
    state.finish_launch(result.is_ok());
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_launch_requires_verified_current_session_and_rejects_replay() {
        let root = std::env::temp_dir().join(format!(
            "mf-launch-state-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir(&root).unwrap();
        let state = FirstRunState::default();
        assert!(state.begin_launch().is_err());
        let db = root.join("encrypted.sqlite3");
        let app = root.join("application");
        fs::write(&db, b"test-only-fake-sqlcipher-state").unwrap();
        fs::create_dir(&app).unwrap();
        state
            .record_encrypted_copy(&db, "fedcba9876543210fedcba9876543210")
            .unwrap();
        assert!(state.begin_launch().is_err());
        state.record_installed_application(&app).unwrap();
        let (selected_app, selected_db) = state.begin_launch().unwrap();
        assert_eq!(selected_app, fs::canonicalize(&app).unwrap());
        assert_eq!(selected_db, fs::canonicalize(&db).unwrap());
        assert!(state.begin_launch().is_err());
        assert!(state.consume().is_err());
        state.finish_launch(false);
        assert!(state.begin_launch().is_ok());
        state.finish_launch(true);
        assert!(state.begin_launch().is_err());
        let newer = root.join("another.sqlite3");
        fs::write(&newer, b"test-only-next-sqlcipher-state").unwrap();
        state
            .record_encrypted_copy(&newer, "0123456789abcdef0123456789abcdef")
            .unwrap();
        assert_eq!(
            state.begin_launch().unwrap().1,
            fs::canonicalize(&newer).unwrap()
        );
        state.finish_launch(false);
        fs::remove_dir_all(root).unwrap();
    }

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
    fn incorrect_database_key_does_not_burn_verified_first_run_operation() {
        let base = std::env::temp_dir().join(format!(
            "minglefield-cipher-credential-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&base);
        fs::create_dir(&base).unwrap();
        let db_path = base.join("encrypted.sqlite3");
        let correct_key = "IndependentSecureCipherPassword123!";
        {
            let db = rusqlite::Connection::open(&db_path).unwrap();
            db.pragma_update(None, "key", correct_key).unwrap();
            db.execute_batch("CREATE TABLE fixture(v INTEGER); INSERT INTO fixture VALUES (1);")
                .unwrap();
        }
        assert_ne!(&fs::read(&db_path).unwrap()[..16], b"SQLite format 3\0");
        let app_path = base.join("app");
        fs::create_dir(&app_path).unwrap();
        let state = FirstRunState::default();
        state
            .record_encrypted_copy(&db_path, "abcdef0123456789abcdef0123456789")
            .unwrap();
        state.record_installed_application(&app_path).unwrap();
        assert!(state
            .validate_database_unlock("WrongKey0123456789!")
            .is_err());
        assert!(state.validate_database_unlock(correct_key).is_ok());
        let permit = state.consume().unwrap();
        assert_eq!(
            permit.database.operation_id,
            "abcdef0123456789abcdef0123456789"
        );
        state.finish();
        assert!(state
            .record_encrypted_copy(&db_path, "abcdef0123456789abcdef0123456789")
            .is_err());
        fs::remove_dir_all(base).unwrap();
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
            .record_encrypted_copy(&database, "0123456789abcdef0123456789abcdef")
            .is_err());
        // A subsequent independent migration must be possible without
        // closing the installer or deleting the previous output.
        state.finish();
        let next_db = base.join("another.sqlite3");
        fs::write(&next_db, b"next-disposable-encrypted-fixture").unwrap();
        assert!(state
            .record_encrypted_copy(&next_db, "fedcba9876543210fedcba9876543210")
            .is_ok());
        assert_eq!(
            state.consume().unwrap().database.operation_id,
            "fedcba9876543210fedcba9876543210"
        );
        state.finish();
        fs::remove_dir_all(base).unwrap();
    }
}
