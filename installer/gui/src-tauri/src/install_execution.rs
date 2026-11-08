//! Actual ONE-CONSENT Alpha installer, not a user-facing diagnostic sequence.
//! The Setup Manager owns the single operation, while the existing shared
//! installer-core still owns SQLCipher migration, file installation, local
//! account provisioning and native application startup.
use minglefield_installer_core::database_password::validate_new_database_password;
use minglefield_installer_core::db_operations::{
    create_new_encrypted_database, verify_encrypted_database, NEW_ENCRYPTED_DATABASE_CONFIRMATION,
};
use minglefield_installer_core::encrypted_copy_preflight::{
    execute_reviewed_encrypted_copy_with_schema, EXPERIMENTAL_COPY_CONFIRMATION,
};
use minglefield_installer_core::local_first_run_worker::ensure_verified_installer_local_admin;
use minglefield_installer_core::migration_dry_run::ReviewCorrection;
use crate::migration_review::StagedCorrection;
use minglefield_installer_core::managed_alpha_install::{
    install_or_reuse_application, verify_installed_application,
};
use minglefield_installer_core::native_application_probe::{
    ensure_native_starter, start_installed_application,
};
use rusqlite::{Connection, OpenFlags};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io;
use std::path::{Component, Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tauri::Manager;

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct InstallRequest {
    install_dir: String,
    database_path: String,
    source_database: Option<String>,
    source_password: String,
    database_password: String,
    login_password: String,
    login_password_confirmation: String,
    corrections: Vec<StagedCorrection>,
    schema_additions: Vec<String>,
    approved: bool,
    continue_existing: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InstalledAndRunning {
    status: &'static str,
    installed_application: String,
    encrypted_database: String,
    database_action: &'static str,
    application_reused: bool,
    local_admin_user: &'static str,
    local_host_id: String,
    native_process_id: u32,
    local_url: String,
    encrypted_database_verified: bool,
    // This is a real GUI installation, not full CLI/silent/release acceptance.
    native_application_running: bool,
}

#[derive(Default)]
pub struct InstallExecutionState {
    busy: Arc<AtomicBool>,
    completed: Arc<AtomicBool>,
}

struct BusyGuard(Arc<AtomicBool>);
impl Drop for BusyGuard {
    fn drop(&mut self) {
        self.0.store(false, Ordering::Release);
    }
}

fn absolute_path(raw: &str) -> Result<PathBuf, String> {
    let path = PathBuf::from(raw.trim());
    if !path.is_absolute()
        || path.file_name().is_none()
        || path
            .components()
            .any(|part| matches!(part, Component::CurDir | Component::ParentDir))
    {
        return Err("Installations- und Datenbankpfade müssen absolut und eindeutig sein".into());
    }
    Ok(path)
}

fn metadata_if_present(path: &Path) -> Result<Option<fs::Metadata>, String> {
    match fs::symlink_metadata(path) {
        Ok(meta) => Ok(Some(meta)),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(_) => Err("Ausgewählter Zielpfad kann nicht geprüft werden".into()),
    }
}

/// Do not ask a user to run a migration, database or write test first.
/// Existing directories and destinations are an ordinary warning + continue
/// or abort; the second call validates the same actual current state again.
fn check_existing_paths(
    application: &Path,
    database: &Path,
    continued: bool,
) -> Result<(bool, bool), String> {
    let app = metadata_if_present(application)?.is_some();
    let db = metadata_if_present(database)?.is_some();
    if (app || db) && !continued {
        return Err(
            "INSTALL_WARNING_EXISTING: Bereits vorhandene Anwendungs- oder Datenbankziele. Weiter übernimmt eine gültige verschlüsselte DB unverändert und sichert vor dem Ersetzen alter Programmdateien deren bisherigen Inhalt; Abbruch verändert nichts."
                .into(),
        );
    }
    Ok((app, db))
}

fn make_real_parent(path: &Path) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or("Zielpfad hat kein übergeordnetes Verzeichnis")?;
    for ancestor in parent.ancestors() {
        match metadata_if_present(ancestor)? {
            Some(metadata) if metadata.file_type().is_symlink() || !metadata.is_dir() => {
                return Err("Zielordner enthält einen unzulässigen Verzeichnisverweis".into())
            }
            _ => {}
        }
    }
    fs::create_dir_all(parent).map_err(|_| "Zielverzeichnis kann nicht angelegt werden".into())
}

fn random_hex() -> Result<String, String> {
    let db = Connection::open_in_memory().map_err(|_| "Zufallskennung nicht verfügbar")?;
    db.query_row("SELECT lower(hex(randomblob(16)))", [], |row| row.get(0))
        .map_err(|_| "Zufallskennung nicht verfügbar".into())
}

/// An automatically made private backup is an internal migration safeguard,
/// never a user-run test, and remains available to inspect after failure.
/// Its source database bytes are never published in an installer artifact.
fn automatic_source_backup(source: &Path, destination: &Path) -> Result<PathBuf, String> {
    let original =
        fs::symlink_metadata(source).map_err(|_| "Quelldatenbank kann nicht geöffnet werden")?;
    if !original.is_file() || original.file_type().is_symlink() {
        return Err("Quelldatenbank muss eine reguläre Datei sein".into());
    }
    let parent = destination
        .parent()
        .ok_or("Datenbankziel ohne Elternordner")?;
    let backup_dir = parent.join(format!(".minglefield-source-backup-{}", random_hex()?));
    #[cfg(unix)]
    let mut builder = fs::DirBuilder::new();
    #[cfg(not(unix))]
    let builder = fs::DirBuilder::new();
    #[cfg(unix)]
    {
        use std::os::unix::fs::DirBuilderExt;
        builder.mode(0o700);
    }
    builder
        .create(&backup_dir)
        .map_err(|_| "Private Migrationssicherung kann nicht angelegt werden")?;
    let backup = backup_dir.join("source.sqlite3");
    fs::copy(source, &backup)
        .map_err(|_| "Quelldatenbank kann nicht unabhängig gesichert werden")?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&backup, fs::Permissions::from_mode(0o600))
            .map_err(|_| "Private Migrationssicherung kann nicht geschützt werden")?;
    }
    fs::OpenOptions::new()
        .read(true)
        .write(true)
        .open(&backup)
        .and_then(|file| file.sync_all())
        .map_err(|_| "Migrationssicherung konnte nicht geschrieben werden")?;
    Ok(backup)
}

/// Prefer a single previously recorded local.* Host. Never silently bind a
/// new administrator to arbitrary imported/remote host IDs. An additional
/// local.* Host is prepared when no unique local mapping is known.
fn selected_local_host(database: &Path, password: &str) -> Result<String, String> {
    let db = Connection::open_with_flags(
        database,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .map_err(|_| "Verschlüsselte Datenbank kann nicht geöffnet werden")?;
    db.pragma_update(None, "key", password)
        .map_err(|_| "SQLCipher-Schlüssel wurde abgelehnt")?;
    let exists: i64 = db
        .query_row(
            "SELECT count(*) FROM sqlite_schema WHERE type='table' AND name='alpha_executor_hosts'",
            [],
            |row| row.get(0),
        )
        .map_err(|_| "Lokale Hostzuordnungen können nicht geprüft werden")?;
    if exists > 0 {
        let mut stmt = db
            .prepare(
                "SELECT host_id FROM alpha_executor_hosts WHERE host_id LIKE 'local.%' ORDER BY host_id LIMIT 2",
            )
            .map_err(|_| "Lokale Hostzuordnungen können nicht gelesen werden")?;
        let hosts = stmt
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(|_| "Lokale Hostzuordnungen können nicht gelesen werden")?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|_| "Lokale Hostzuordnungen sind unvollständig")?;
        if hosts.len() == 1 {
            return Ok(hosts[0].clone());
        }
    }
    Ok(format!("local.{}", random_hex()?))
}

fn execute_install(
    request: InstallRequest,
    resources: PathBuf,
    manager_directory: PathBuf,
) -> Result<InstalledAndRunning, String> {
    if !request.approved {
        return Err("Installation wurde nicht bestätigt".into());
    }
    let install_dir = absolute_path(&request.install_dir)?;
    let database = absolute_path(&request.database_path)?;
    let source = request
        .source_database
        .as_deref()
        .filter(|raw| !raw.trim().is_empty())
        .map(absolute_path)
        .transpose()?;
    if request.database_password.is_empty() || request.database_password.len() > 4096 {
        return Err("Gültiges SQLCipher-Datenbankpasswort erforderlich".into());
    }
    if request.login_password != request.login_password_confirmation
        || request.login_password.len() > 256
        || (!request.login_password.is_empty() && request.login_password.len() < 12)
        || (!request.login_password.is_empty()
            && request.login_password == request.database_password)
    {
        return Err("Mingleadmin-Loginpasswort und Bestätigung sind ungültig".into());
    }
    if request.corrections.iter().any(|edit| !matches!(edit, StagedCorrection::FullRow { .. })) {
        return Err("Die Produkt-Datenbearbeitung erlaubt nur geprüfte vollständige Tabellenzeilen".into());
    }
    if source.is_none() && (!request.corrections.is_empty() || !request.schema_additions.is_empty()) {
        return Err("Daten- und Schemaänderungen erfordern eine gewählte Quelldatenbank".into());
    }
    let (_existing_application, existing_db) =
        check_existing_paths(&install_dir, &database, request.continue_existing)?;
    if existing_db && (!request.corrections.is_empty() || !request.schema_additions.is_empty()) {
        return Err("Eine bereits vorhandene SQLCipher-Zieldatenbank bleibt unverändert. Für Daten- oder Schemaänderungen bitte einen neuen Zielpfad wählen.".into());
    }
    let changes: Vec<ReviewCorrection> = request.corrections.into_iter().map(ReviewCorrection::from).collect();
    let digest = option_env!("MINGLEFIELD_ALPHA_INVENTORY_SHA256")
        .ok_or("Kein festgelegtes Alpha-Anwendungspaket vorhanden")?;
    let package = crate::alpha_application_install::find_packaged_alpha_source(
        &resources,
        &manager_directory,
        digest,
    )?;
    ensure_native_starter(&package, digest).map_err(str::to_owned)?;
    // Everything above is read-only and requires no user-run probes.
    let database_action = if existing_db {
        let meta = fs::symlink_metadata(&database)
            .map_err(|_| "Vorhandene Datenbank kann nicht geprüft werden")?;
        if !meta.is_file() || meta.file_type().is_symlink() {
            return Err("Vorhandenes Datenbankziel ist keine reguläre Datei".into());
        }
        verify_encrypted_database(&database, &request.database_password)
            .map_err(|_| "Vorhandene DB nicht mit dem angegebenen SQLCipher-Schlüssel verwendbar; anderer Zielpfad nötig")?;
        "reused_encrypted_database"
    } else {
        make_real_parent(&database)?;
        if let Some(source) = source {
            let backup = automatic_source_backup(&source, &database)?;
            let proof = execute_reviewed_encrypted_copy_with_schema(
                &source,
                &database,
                &backup,
                &request.source_password,
                &request.database_password,
                &changes,
                &request.schema_additions,
                EXPERIMENTAL_COPY_CONFIRMATION,
            )
            .map_err(|reason| format!("Datenbankmigration fehlgeschlagen: {reason}"))?;
            if !proof.destination_created || !proof.encrypted_destination_verified {
                return Err("Datenbankmigration wurde nicht vollständig bestätigt".into());
            }
            "migrated_encrypted_database"
        } else {
            validate_new_database_password(&request.database_password)
                .map_err(|_| "Neues Datenbankpasswort erfüllt die Anforderungen nicht")?;
            create_new_encrypted_database(
                &database,
                &request.database_password,
                NEW_ENCRYPTED_DATABASE_CONFIRMATION,
            )
            .map_err(|reason| {
                format!("Neue SQLCipher-Datenbank konnte nicht erstellt werden: {reason}")
            })?;
            "created_encrypted_database"
        }
    };
    verify_encrypted_database(&database, &request.database_password)
        .map_err(|_| "Verschlüsselte Datenbank ist nach der Installation nicht lesbar")?;
    make_real_parent(&install_dir)?;
    let (installed, reused) =
        install_or_reuse_application(&package, &install_dir, digest, request.continue_existing)
            .map_err(|reason| {
                format!("Minglefield-Anwendungsdateien konnten nicht installiert werden: {reason}")
            })?;
    verify_installed_application(Path::new(&installed.install_dir), digest)
        .map_err(|_| "Installierte Minglefield-Dateien konnten nicht verifiziert werden")?;
    let local_host_id = selected_local_host(&database, &request.database_password)?;
    let admin = ensure_verified_installer_local_admin(
        Path::new(&installed.install_dir),
        &database,
        &request.database_password,
        &request.login_password,
        &local_host_id,
    )
    .map_err(|_| {
        "Mingleadmin konnte nicht hinzugefügt/übernommen werden. Bereits migrierte DB und Anwendungsdateien bleiben erhalten; bitte Loginpasswort und bisherigen DB-Zustand prüfen."
            .to_owned()
    })?;
    let running = start_installed_application(
        Path::new(&installed.install_dir),
        &database,
        &request.database_password,
        digest,
        true,
    )
    .map_err(|reason| {
        format!("Anwendungsstart fehlgeschlagen: {reason}. Daten und vorherige Anwendungssicherung bleiben erhalten")
    })?;
    Ok(InstalledAndRunning {
        status: "minglefield_installed_and_running",
        installed_application: installed.install_dir,
        encrypted_database: database.to_string_lossy().into_owned(),
        database_action,
        application_reused: reused,
        local_admin_user: "mingleadmin",
        local_host_id: admin.local_host_id,
        native_process_id: running.process_id,
        local_url: format!("http://127.0.0.1:{}/", running.port),
        encrypted_database_verified: true,
        native_application_running: true,
    })
}

#[tauri::command]
pub async fn install_minglefield(
    app: tauri::AppHandle,
    state: tauri::State<'_, InstallExecutionState>,
    request: InstallRequest,
) -> Result<InstalledAndRunning, String> {
    if !request.approved {
        return Err("Bitte Installation durchführen bestätigen".into());
    }
    if state.completed.load(Ordering::Acquire) {
        return Err("Installation wurde in dieser Sitzung bereits abgeschlossen".into());
    }
    if state.busy.swap(true, Ordering::AcqRel) {
        return Err("Installation läuft bereits".into());
    }
    let busy = state.busy.clone();
    let completed = state.completed.clone();
    let locations = (|| -> Result<(PathBuf, PathBuf), String> {
        let resources = app
            .path()
            .resource_dir()
            .map_err(|_| "Anwendungspaket ist nicht erreichbar")?;
        let executable = std::env::current_exe().map_err(|_| "Setup Manager-Dateipfad fehlt")?;
        let manager_dir = executable
            .parent()
            .ok_or("Setup Manager-Verzeichnis fehlt")?
            .to_path_buf();
        Ok((resources, manager_dir))
    })();
    let (resources, manager_dir) = match locations {
        Ok(paths) => paths,
        Err(reason) => {
            busy.store(false, Ordering::Release);
            return Err(reason);
        }
    };
    let result = tauri::async_runtime::spawn_blocking(move || {
        let _guard = BusyGuard(busy);
        let result = execute_install(request, resources, manager_dir);
        if result.is_ok() {
            completed.store(true, Ordering::Release);
        }
        result
    })
    .await
    .map_err(|_| "Installationsausführung unerwartet beendet".to_owned())?;
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn single_consent_and_existing_path_warning_are_independent_of_user_tests() {
        let root = std::env::temp_dir().join(format!(
            "mf-single-install-review-{}",
            random_hex().unwrap()
        ));
        let app = root.join("Minglefield");
        let db = root.join("minglefield.sqlite3");
        fs::create_dir_all(&app).unwrap();
        assert!(check_existing_paths(&app, &db, false)
            .unwrap_err()
            .starts_with("INSTALL_WARNING_EXISTING:"));
        assert_eq!(
            check_existing_paths(&app, &db, true).unwrap(),
            (true, false)
        );
        assert!(absolute_path("relative/location").is_err());
        assert!(absolute_path("../database.sqlite3").is_err());
        fs::remove_dir_all(root).unwrap();
    }
}
