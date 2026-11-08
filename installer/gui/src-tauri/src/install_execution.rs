//! Actual ONE-CONSENT Alpha installer, not a user-facing diagnostic sequence.
//! The Setup Manager owns the single operation, while the existing shared
//! installer-core still owns SQLCipher migration, file installation, local
//! account provisioning and native application startup.
use crate::migration_review::StagedCorrection;
use minglefield_installer_core::database_password::validate_new_database_password;
use minglefield_installer_core::db_operations::{
    create_new_encrypted_database, verify_encrypted_database, NEW_ENCRYPTED_DATABASE_CONFIRMATION,
};
use minglefield_installer_core::encrypted_copy_preflight::{
    execute_reviewed_encrypted_copy_with_schema, EXPERIMENTAL_COPY_CONFIRMATION,
};
use minglefield_installer_core::legacy_alpha_constraints::audit_registered_alpha_schema_objects;
use minglefield_installer_core::local_first_run_worker::ensure_verified_installer_local_admin;
use minglefield_installer_core::managed_alpha_install::{
    install_or_reuse_application, verify_installed_application,
};
use minglefield_installer_core::migration_dry_run::{RawCell, ReviewCorrection};
use minglefield_installer_core::native_application_probe::{
    ensure_native_starter, start_installed_application,
};
use minglefield_installer_core::sqlite_inspection::open_inspected_snapshot;
use rusqlite::{types::Value, Connection, OpenFlags};
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
    local_host_id: Option<String>,
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

/// Reuse the actual Host ID stored in the imported SQLCipher database.
/// Older installations use 'host.local' or custom IDs, not necessarily local.*.
/// If several IDs exist, page 5 requires a deliberate local-Host choice.
fn selected_local_host(
    database: &Path,
    password: &str,
    requested: Option<&str>,
) -> Result<String, String> {
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
        .map_err(|_| "Hostzuordnungen können nicht geprüft werden")?;
    let mut hosts = Vec::new();
    if exists > 0 {
        let mut stmt = db
            .prepare("SELECT host_id FROM alpha_executor_hosts WHERE active=1 ORDER BY host_id")
            .map_err(|_| "Hostzuordnungen können nicht gelesen werden")?;
        hosts = stmt
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(|_| "Hostzuordnungen können nicht gelesen werden")?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|_| "Hostzuordnungen sind unvollständig")?;
    }
    if let Some(id) = requested.filter(|id| !id.is_empty()) {
        if hosts.iter().any(|existing| existing == id) {
            return Ok(id.to_owned());
        }
        return Err("Der ausgewählte lokale Host existiert nicht in der Datenbank".into());
    }
    match hosts.as_slice() {
        [] => Ok(format!("local.{}", random_hex()?)),
        [only] => Ok(only.clone()),
        _ => {
            let local: Vec<_> = hosts
                .iter()
                .filter(|id| id.as_str() == "host.local" || id.starts_with("local."))
                .collect();
            if local.len() == 1 {
                Ok(local[0].to_string())
            } else {
                Err("Mehrere Hosts: Auf Seite 5 bitte den lokalen Host auswählen".into())
            }
        }
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ExistingHostBinding {
    host_id: String,
    operator_id: String,
}

/// Show stored Host IDs without claiming, modifying, or creating a Host.
/// Read-only inspection never authorizes a remote Host.
#[tauri::command]
pub async fn inspect_host_bindings(
    path: String,
    password: String,
) -> Result<Vec<ExistingHostBinding>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let file = absolute_path(&path)?;
        // Use the same read-only SQLite/SQLCipher snapshot as the page-five
        // database editor. Plaintext SQLite must not be keyed as SQLCipher.
        let (db, _) = open_inspected_snapshot(&file, &password)
            .map_err(|_| "Hostdatenbank konnte nicht schreibgeschützt geprüft werden")?;
        let exists: i64 = db
            .query_row(
                "SELECT count(*) FROM sqlite_schema WHERE type='table' AND name='alpha_executor_hosts'",
                [],
                |row| row.get(0),
            )
            .map_err(|_| "Hosttabelle kann nicht geprüft werden")?;
        if exists == 0 {
            return Ok(Vec::new());
        }
        let mut stmt = db
            .prepare("SELECT host_id,operator_id FROM alpha_executor_hosts WHERE active=1 ORDER BY host_id")
            .map_err(|_| "Hosttabelle kann nicht gelesen werden")?;
        let rows = stmt
            .query_map([], |row| {
                Ok(ExistingHostBinding {
                    host_id: row.get(0)?,
                    operator_id: row.get(1)?,
                })
            })
            .map_err(|_| "Hosttabelle kann nicht gelesen werden")?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|_| "Hosttabelle ist unvollständig")?;
        Ok(rows)
    })
    .await
    .map_err(|_| "Hostübersicht konnte nicht erstellt werden".to_owned())?
}

/// Reinstall-resume verification of a destination already created by a
/// previous authorized migration attempt. Never delete, recreate, or write
/// the occupied SQLCipher DB just to resume an interrupted install.
fn db_value_matches(cell: &RawCell, value: &Value) -> bool {
    match (cell.kind.as_str(), cell.value.as_deref(), value) {
        ("null", None, Value::Null) => true,
        ("integer", Some(raw), Value::Integer(actual)) => raw.parse::<i64>() == Ok(*actual),
        ("real", Some(raw), Value::Real(actual)) => {
            raw.parse::<f64>().ok().filter(|number| number.is_finite()) == Some(*actual)
        }
        ("text", Some(raw), Value::Text(actual)) => raw == actual,
        ("blob", Some(raw), Value::Blob(bytes)) => {
            raw.len() == bytes.len() * 2
                && bytes.iter().enumerate().all(|(index, byte)| {
                    u8::from_str_radix(&raw[index * 2..index * 2 + 2], 16).ok() == Some(*byte)
                })
        }
        _ => false,
    }
}

fn quoted_sqlite_identifier(identifier: &str) -> Result<String, String> {
    if identifier.is_empty() || identifier.len() > 256 || identifier.as_bytes().contains(&0) {
        return Err("Ungültiger Name in der Datenbearbeitung".into());
    }
    Ok(format!("\"{}\"", identifier.replace('"', "\"\"")))
}

fn match_rows(
    db: &Connection,
    changes: &[ReviewCorrection],
    use_after: bool,
) -> Result<(), String> {
    for correction in changes {
        let ReviewCorrection::FullRow {
            table,
            row_id,
            columns,
            before,
            after,
        } = correction
        else {
            return Err(
                "Eine ältere Korrektur kann hier nicht automatisch übernommen werden".into(),
            );
        };
        if columns.is_empty()
            || columns.len() > 1024
            || before.len() != columns.len()
            || after.len() != columns.len()
        {
            return Err("Unvollständige Datenkorrektur".into());
        }
        let expected = if use_after { after } else { before };
        let table = quoted_sqlite_identifier(table)?;
        let projection = columns
            .iter()
            .map(|column| quoted_sqlite_identifier(column))
            .collect::<Result<Vec<_>, _>>()?
            .join(",");
        let query = if row_id.is_some() {
            format!("SELECT {projection} FROM {table} WHERE rowid=?1")
        } else {
            format!("SELECT {projection} FROM {table}")
        };
        let mut stmt = db
            .prepare(&query)
            .map_err(|_| "Datensatzschema stimmt nicht mehr überein")?;
        let mut rows = if let Some(id) = row_id {
            let id = id.parse::<i64>().map_err(|_| "Ungültige Datensatz-ID")?;
            stmt.query([id])
        } else {
            stmt.query([])
        }
        .map_err(|_| "Datenbankkorrektur konnte nicht verglichen werden")?;
        let mut matches = 0usize;
        let mut scanned = 0usize;
        while let Some(row) = rows
            .next()
            .map_err(|_| "Datenbankdatensatz konnte nicht gelesen werden")?
        {
            scanned += 1;
            if scanned > 5000 {
                return Err("Zu viele Datensätze für die Wiederaufnahmeprüfung".into());
            }
            let actual = (0..columns.len())
                .map(|index| row.get::<_, Value>(index))
                .collect::<rusqlite::Result<Vec<_>>>()
                .map_err(|_| "Datenbankwert konnte nicht verglichen werden")?;
            if actual
                .iter()
                .zip(expected.iter())
                .all(|(value, cell)| db_value_matches(cell, value))
            {
                matches += 1;
            }
        }
        if matches != 1 {
            return Err("Vorhandene DB enthält nicht die bestätigten Datenänderungen; anderer Zielpfad oder angepasste Auswahl erforderlich".into());
        }
    }
    Ok(())
}

fn verify_existing_migration_intent(
    source: &Path,
    old_password: &str,
    destination: &Path,
    new_password: &str,
    changes: &[ReviewCorrection],
    additions: &[String],
) -> Result<(), String> {
    let (source_db, source_schema) = open_inspected_snapshot(source, old_password)
        .map_err(|_| "Migrationquelle kann nicht unabhängig überprüft werden")?;
    if !source_schema.integrity_ok || source_schema.foreign_key_violations != 0 {
        return Err("Migrationsquelle ist nicht konsistent".into());
    }
    match_rows(&source_db, changes, false)?;
    let source_audit = audit_registered_alpha_schema_objects(&source_db, &source_schema)
        .map_err(|_| "Original-Schema konnte nicht überprüft werden")?;
    if additions
        .iter()
        .any(|name| !source_audit.missing_objects.contains(name))
    {
        return Err("Schemaauswahl entspricht nicht mehr der Migrationsquelle".into());
    }
    let (target_db, target_schema) = open_inspected_snapshot(destination, new_password)
        .map_err(|_| "Bereits verschlüsselte DB konnte nicht gelesen werden")?;
    if !target_schema.integrity_ok || target_schema.foreign_key_violations != 0 {
        return Err("Vorhandene DB ist nicht konsistent".into());
    }
    match_rows(&target_db, changes, true)?;
    let target_audit = audit_registered_alpha_schema_objects(&target_db, &target_schema)
        .map_err(|_| "Ziel-Schema konnte nicht überprüft werden")?;
    if additions.iter().any(|name| {
        target_audit.missing_objects.contains(name)
            || target_audit.incompatible_objects.contains(name)
    }) {
        return Err("Vorhandene DB enthält nicht alle gewählten Schemaergänzungen".into());
    }
    Ok(())
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
    if request
        .corrections
        .iter()
        .any(|edit| !matches!(edit, StagedCorrection::FullRow { .. }))
    {
        return Err(
            "Die Produkt-Datenbearbeitung erlaubt nur geprüfte vollständige Tabellenzeilen".into(),
        );
    }
    if source.is_none() && (!request.corrections.is_empty() || !request.schema_additions.is_empty())
    {
        return Err("Daten- und Schemaänderungen erfordern eine gewählte Quelldatenbank".into());
    }
    let (_existing_application, existing_db) =
        check_existing_paths(&install_dir, &database, request.continue_existing)?;
    let changes: Vec<ReviewCorrection> = request
        .corrections
        .into_iter()
        .map(ReviewCorrection::from)
        .collect();
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
        if !changes.is_empty() || !request.schema_additions.is_empty() {
            let source_path = source.as_deref().ok_or(
                "Für die Übernahme vorgemerkter Korrekturen ist eine Quelldatenbank erforderlich",
            )?;
            if source_path == database.as_path() {
                return Err(
                    "Quelle und verschlüsselte Zieldatenbank dürfen nicht dieselbe Datei sein"
                        .into(),
                );
            }
            verify_existing_migration_intent(
                source_path,
                &request.source_password,
                &database,
                &request.database_password,
                &changes,
                &request.schema_additions,
            )?;
        }
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
    // Register the *installed application* in Windows Installed Apps, never
    // the portable Setup Manager. Database files remain outside its remover.
    crate::windows_app_registration::register_installed_application(Path::new(
        &installed.install_dir,
    ))?;
    let local_host_id = selected_local_host(
        &database,
        &request.database_password,
        request.local_host_id.as_deref(),
    )?;
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
    fn imported_host_local_is_reused_without_creating_another_host() {
        let root = std::env::temp_dir().join(format!(
            "minglefield-existing-host-{}",
            random_hex().unwrap()
        ));
        fs::create_dir(&root).unwrap();
        let path = root.join("legacy-host.sqlite3");
        {
            let db = Connection::open(&path).unwrap();
            db.pragma_update(None, "key", "HostDatabase9!").unwrap();
            db.execute_batch(
                "CREATE TABLE alpha_executor_hosts(
                    host_id TEXT PRIMARY KEY,
                    operator_id TEXT NOT NULL,
                    active INTEGER NOT NULL
                );
                INSERT INTO alpha_executor_hosts
                    VALUES('host.local','user.daniel',1);",
            )
            .unwrap();
        }
        assert_eq!(
            selected_local_host(&path, "HostDatabase9!", None).unwrap(),
            "host.local"
        );
        assert_eq!(
            selected_local_host(&path, "HostDatabase9!", Some("host.local")).unwrap(),
            "host.local"
        );
        assert!(selected_local_host(&path, "HostDatabase9!", Some("remote.other")).is_err());
        {
            let db = Connection::open(&path).unwrap();
            db.pragma_update(None, "key", "HostDatabase9!").unwrap();
            db.execute(
                "INSERT INTO alpha_executor_hosts VALUES('remote.other','otherowner',1)",
                [],
            )
            .unwrap();
        }
        assert_eq!(
            selected_local_host(&path, "HostDatabase9!", None).unwrap(),
            "host.local"
        );
        assert_eq!(
            selected_local_host(&path, "HostDatabase9!", Some("host.local")).unwrap(),
            "host.local"
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn existing_encrypted_migration_reuses_matching_edits_without_deleting_user_db() {
        let root = std::env::temp_dir().join(format!(
            "minglefield-existing-migration-{}",
            random_hex().unwrap()
        ));
        fs::create_dir(&root).unwrap();
        let source = root.join("source.sqlite3");
        let dest = root.join("previous-migration.sqlite3");
        {
            let db = Connection::open(&source).unwrap();
            db.execute_batch(
                "CREATE TABLE alpha_users(user_id TEXT PRIMARY KEY,disabled INTEGER);
                 INSERT INTO alpha_users VALUES('user.daniel',0);",
            )
            .unwrap();
        }
        {
            let db = Connection::open(&dest).unwrap();
            db.pragma_update(None, "key", "VerifiedKey9!").unwrap();
            db.execute_batch(
                "CREATE TABLE alpha_users(user_id TEXT PRIMARY KEY,disabled INTEGER);
                 INSERT INTO alpha_users VALUES('user.daniel',1);",
            )
            .unwrap();
        }
        let correction = ReviewCorrection::FullRow {
            table: "alpha_users".into(),
            row_id: Some("1".into()),
            columns: vec!["user_id".into(), "disabled".into()],
            before: vec![
                RawCell {
                    kind: "text".into(),
                    value: Some("user.daniel".into()),
                },
                RawCell {
                    kind: "integer".into(),
                    value: Some("0".into()),
                },
            ],
            after: vec![
                RawCell {
                    kind: "text".into(),
                    value: Some("user.daniel".into()),
                },
                RawCell {
                    kind: "integer".into(),
                    value: Some("1".into()),
                },
            ],
        };
        let before = fs::read(&dest).unwrap();
        assert!(verify_existing_migration_intent(
            &source,
            "",
            &dest,
            "VerifiedKey9!",
            std::slice::from_ref(&correction),
            &[],
        )
        .is_ok());
        assert_eq!(before, fs::read(&dest).unwrap());
        {
            let db = Connection::open(&dest).unwrap();
            db.pragma_update(None, "key", "VerifiedKey9!").unwrap();
            db.execute("UPDATE alpha_users SET disabled=0", []).unwrap();
        }
        assert!(verify_existing_migration_intent(
            &source,
            "",
            &dest,
            "VerifiedKey9!",
            &[correction],
            &[],
        )
        .is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn real_install_request_accepts_typed_staged_row_changes_and_selected_schema_objects() {
        let input = serde_json::json!({
            "installDir": "/tmp/minglefield-app",
            "databasePath": "/tmp/minglefield-encrypted.sqlite3",
            "sourceDatabase": "/tmp/legacy.sqlite3",
            "sourcePassword": "",
            "databasePassword": "ExampleCipherKey9!",
            "loginPassword": "ExampleLoginKey8!",
            "loginPasswordConfirmation": "ExampleLoginKey8!",
            "corrections": [{
                "kind": "full_row",
                "table": "alpha_users",
                "row_id": "1",
                "columns": ["disabled"],
                "before": [{"kind":"integer","value":"0"}],
                "after": [{"kind":"integer","value":"1"}]
            }],
            "schemaAdditions": ["registered_missing_index"],
            "localHostId": "host.local",
            "approved": true,
            "continueExisting": false
        });
        let request: InstallRequest = serde_json::from_value(input).unwrap();
        assert!(request.approved);
        assert_eq!(request.schema_additions, ["registered_missing_index"]);
        assert!(matches!(
            request.corrections[0],
            StagedCorrection::FullRow { .. }
        ));
        let changes: Vec<ReviewCorrection> = request
            .corrections
            .into_iter()
            .map(ReviewCorrection::from)
            .collect();
        assert_eq!(changes.len(), 1);
        assert!(matches!(changes[0], ReviewCorrection::FullRow { .. }));
    }

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
