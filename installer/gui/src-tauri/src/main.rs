// GUI-only entrypoint: suppress the Windows console subsystem window in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use minglefield_installer_core::config::InstallerConfig;
use minglefield_installer_core::config_v2::InstallerConfigV2;
use minglefield_installer_core::Mode;
use serde::Serialize;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct PlanPreview {
    version: u32,
    install_dir: String,
    data_dir: String,
    provision_host: bool,
    install_optional_conda: bool,
    install_optional_comfyui: bool,
    execution_enabled: bool,
    install_optional_git: bool,
    install_optional_gh: bool,
    offer_gh_login: bool,
    consent_git: bool,
    consent_gh: bool,
    consent_login: bool,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct DefaultConfig {
    version: u32,
    install_dir: String,
    data_dir: String,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct LicenseInfo {
    identifier: &'static str,
    text: &'static str,
}

#[tauri::command]
fn framework_license() -> LicenseInfo {
    LicenseInfo {
        identifier: "GPL-3.0-or-later",
        text: include_str!("../../../../LICENSE"),
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct ReadmeInfo {
    text: &'static str,
}

#[tauri::command]
fn application_readme() -> ReadmeInfo {
    ReadmeInfo {
        text: include_str!("../../../../README.md"),
    }
}

#[cfg(test)]
mod readme_tests {
    #[test]
    fn embedded_application_readme_is_present() {
        let readme = super::application_readme();
        assert!(readme.text.starts_with("# Minglefield"));
        assert!(readme.text.len() > 500);
        assert!(readme.text.contains("GPL-3.0-or-later"));
        assert!(!readme.text.contains("License selection is pending"));
        assert!(!readme.text.contains("until licensing is finalized"));
    }
}

#[cfg(test)]
mod license_tests {
    #[test]
    fn embedded_framework_license_is_complete() {
        let license = super::framework_license();
        assert_eq!(license.identifier, "GPL-3.0-or-later");
        assert!(license.text.starts_with("GNU GENERAL PUBLIC LICENSE"));
        assert!(license.text.contains("END OF TERMS AND CONDITIONS"));
        assert!(license.text.len() > 30_000);
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SourceInspection {
    kind: &'static str,
    location: String,
    provenance_verified: bool,
    launch_ready: bool,
}

#[tauri::command]
fn inspect_source_path(path: String) -> SourceInspection {
    use minglefield_installer_core::discovery::{inspect_source_directory, CandidateKind};
    let candidate = inspect_source_directory(std::path::Path::new(&path));
    SourceInspection {
        kind: match candidate.kind {
            CandidateKind::SourceCheckout => "source_checkout",
            CandidateKind::Unrecognized => "unrecognized",
        },
        location: candidate.location,
        provenance_verified: candidate.provenance_verified,
        launch_ready: candidate.launch_ready,
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct DataInventoryItem {
    relative_path: String,
    source_directory: String,
    kind: &'static str,
    status: &'static str,
    sqlite_page_size: Option<u32>,
    sqlite_user_version: Option<u32>,
    sqlite_application_id: Option<u32>,
    schema_version_status: Option<&'static str>,
}

#[tauri::command]
fn inspect_existing_data(path: String) -> Vec<DataInventoryItem> {
    minglefield_installer_core::data_inventory::inspect_data_directory(std::path::Path::new(&path))
        .into_iter()
        .map(|candidate| DataInventoryItem {
            relative_path: candidate.relative_path,
            source_directory: path.clone(),
            kind: candidate.kind,
            status: candidate.status,
            sqlite_page_size: candidate.sqlite_page_size,
            sqlite_user_version: candidate.sqlite_user_version,
            sqlite_application_id: candidate.sqlite_application_id,
            schema_version_status: if candidate.kind == "sqlite_database" {
                use minglefield_installer_core::schema_versions::{
                    classify_header, HeaderVersionStatus,
                };
                Some(
                    match classify_header(
                        candidate.sqlite_application_id.unwrap_or(0),
                        candidate.sqlite_user_version.unwrap_or(0),
                        None,
                    ) {
                        HeaderVersionStatus::LegacyUnversioned => "legacy_unversioned_unverified",
                        HeaderVersionStatus::UnregisteredApplication => "unregistered_application",
                        HeaderVersionStatus::VersionedUnverified(_) => "versioned_unverified",
                    },
                )
            } else {
                None
            },
        })
        .collect()
}

#[tauri::command]
fn inspect_default_user_data() -> Result<Vec<DataInventoryItem>, String> {
    let paths =
        minglefield_installer_core::default_existing_data_search_paths().map_err(str::to_string)?;
    Ok(paths.into_iter().flat_map(inspect_existing_data).collect())
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SqliteInspectionPreview {
    status: &'static str,
    integrity_ok: bool,
    foreign_key_violations: u64,
    foreign_keys_ok: bool,
    application_id: i64,
    user_version: i64,
    tables: Vec<SqliteTablePreview>,
    schema_objects: Vec<SqliteSchemaObjectPreview>,
    migration_enabled: bool,
}

#[derive(Serialize)]
struct SqliteTablePreview {
    name: String,
    columns: Vec<String>,
    create_sql: Option<String>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct SqliteSchemaObjectPreview {
    object_type: String,
    name: String,
    table_name: String,
    create_sql: Option<String>,
}

#[tauri::command]
async fn inspect_sqlite_database(
    path: String,
    password: String,
) -> Result<SqliteInspectionPreview, String> {
    let inspection = tauri::async_runtime::spawn_blocking(move || {
        minglefield_installer_core::sqlite_inspection::inspect_sqlite_with_password(
            std::path::Path::new(&path),
            &password,
        )
    })
    .await
    .map_err(|_| "SQLite inspection task failed".to_owned())?
    .map_err(|error| format!("SQLite inspection rejected: {error:?}"))?;
    Ok(SqliteInspectionPreview {
        status: "sqlite_integrity_verified_schema_unclassified",
        integrity_ok: inspection.integrity_ok,
        foreign_key_violations: inspection.foreign_key_violations,
        foreign_keys_ok: inspection.foreign_key_violations == 0,
        application_id: inspection.application_id,
        user_version: inspection.user_version,
        tables: inspection
            .tables
            .into_iter()
            .map(|table| SqliteTablePreview {
                name: table.name,
                columns: table.columns,
                create_sql: table.create_sql,
            })
            .collect(),
        schema_objects: inspection
            .schema_objects
            .into_iter()
            .map(|item| SqliteSchemaObjectPreview {
                object_type: item.object_type,
                name: item.name,
                table_name: item.table_name,
                create_sql: item.create_sql,
            })
            .collect(),
        migration_enabled: false,
    })
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct AlphaUserReview {
    user_id: String,
    disabled: bool,
}

#[tauri::command]
async fn inspect_alpha_users(
    path: String,
    password: String,
) -> Result<Vec<AlphaUserReview>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        use rusqlite::{Connection, OpenFlags};
        use std::path::Path;
        let source = Path::new(&path);
        let inspection =
            minglefield_installer_core::sqlite_inspection::inspect_sqlite_with_password(
                source, &password,
            )
            .map_err(|error| format!("Database inspection rejected: {error:?}"))?;
        if !inspection.integrity_ok || inspection.foreign_key_violations != 0 {
            return Err("Database integrity validation failed".to_owned());
        }
        let users = inspection
            .tables
            .iter()
            .find(|table| table.name == "alpha_users")
            .ok_or_else(|| "Alpha users table not found".to_owned())?;
        if !users.columns.contains(&"user_id".to_owned())
            || !users.columns.contains(&"disabled".to_owned())
        {
            return Err("Alpha users schema is not compatible".to_owned());
        }
        let db = Connection::open_with_flags(source, OpenFlags::SQLITE_OPEN_READ_ONLY)
            .map_err(|_| "Cannot open selected database".to_owned())?;
        if !password.is_empty() {
            db.pragma_update(None, "key", &password)
                .map_err(|_| "Cannot unlock selected database".to_owned())?;
        }
        let mut stmt = db
            .prepare("SELECT user_id, disabled FROM alpha_users ORDER BY user_id LIMIT 501")
            .map_err(|_| "Cannot read Alpha users".to_owned())?;
        let rows = stmt
            .query_map([], |row| {
                Ok(AlphaUserReview {
                    user_id: row.get(0)?,
                    disabled: row.get::<_, i64>(1)? != 0,
                })
            })
            .map_err(|_| "Cannot query Alpha users".to_owned())?
            .collect::<rusqlite::Result<Vec<_>>>()
            .map_err(|_| "Cannot decode Alpha users".to_owned())?;
        if rows.len() > 500 {
            return Err("More than 500 users: review pagination required".to_owned());
        }
        Ok(rows)
    })
    .await
    .map_err(|_| "Alpha users inspection task failed".to_owned())?
}

#[tauri::command]
fn default_configuration() -> Result<DefaultConfig, String> {
    let c = InstallerConfig::defaults().map_err(|err| format!("{err:?}"))?;
    Ok(DefaultConfig {
        version: c.version,
        install_dir: c.install_dir,
        data_dir: c.data_dir,
    })
}

#[tauri::command]
fn preview_install_plan(
    new_db_password: String,
    confirm_db_password: String,
    install_dir: String,
    data_dir: String,
    config_text: Option<String>,
) -> Result<PlanPreview, String> {
    // Enforce SQLCipher destination credentials at the Rust boundary even for
    // preview. The frontend alone is not a security boundary.
    minglefield_installer_core::database_password::validate_new_database_password(&new_db_password)
        .map_err(|error| format!("Invalid destination database password: {error:?}"))?;
    if new_db_password != confirm_db_password {
        return Err("Destination database password confirmation does not match".to_owned());
    }
    let (c, tools, config_version) = if let Some(text) = config_text {
        let version_lines: Vec<&str> = text
            .lines()
            .map(str::trim)
            .filter(|line| {
                line.split_once('=')
                    .is_some_and(|(key, _)| key.trim() == "version")
            })
            .collect();
        if version_lines.len() != 1 {
            return Err("missing or duplicate configuration version".to_owned());
        }
        let version = version_lines[0]
            .split_once('=')
            .map(|(_, value)| value.trim())
            .unwrap_or("");
        if version == "2" {
            let config = InstallerConfigV2::parse(&text).map_err(str::to_string)?;
            config.git_tools.validate().map_err(str::to_string)?;
            (config.base, config.git_tools, 2)
        } else {
            let config = InstallerConfig::parse(&text).map_err(str::to_string)?;
            (
                config,
                minglefield_installer_core::git_tools_v2::GitToolOptions::disabled(),
                1,
            )
        }
    } else {
        let mut c = InstallerConfig::defaults().map_err(|err| format!("{err:?}"))?;
        c.install_dir = install_dir;
        c.data_dir = data_dir;
        (
            c,
            minglefield_installer_core::git_tools_v2::GitToolOptions::disabled(),
            1,
        )
    };
    let p = c.preview(Mode::Gui).map_err(|err| format!("{err:?}"))?;
    Ok(PlanPreview {
        version: config_version,
        install_dir: p.install_dir,
        data_dir: c.data_dir,
        provision_host: p.provision_host,
        install_optional_conda: p.install_optional_conda,
        install_optional_comfyui: p.install_optional_comfyui,
        execution_enabled: false,
        install_optional_git: tools.install_optional_git,
        install_optional_gh: tools.install_optional_gh,
        offer_gh_login: tools.offer_gh_login,
        consent_git: tools.consent_git,
        consent_gh: tools.consent_gh,
        consent_login: tools.consent_login,
    })
}

#[cfg(test)]
mod mandatory_database_password_tests {
    use super::preview_install_plan;

    #[test]
    fn rejects_missing_password_even_for_fresh_install_preview() {
        let result = preview_install_plan(
            String::new(),
            String::new(),
            String::new(),
            String::new(),
            None,
        );
        assert!(result.is_err());
        assert!(result
            .err()
            .unwrap()
            .contains("Invalid destination database password"));
    }

    #[test]
    fn rejects_mismatched_confirmation_at_backend_boundary() {
        let result = preview_install_plan(
            "ValidPass9!".into(),
            "OtherPass9!".into(),
            String::new(),
            String::new(),
            None,
        );
        assert!(result.is_err());
        assert!(result
            .err()
            .unwrap()
            .contains("confirmation does not match"));
    }
}

#[tauri::command]
async fn browse_directory() -> Option<String> {
    tauri::async_runtime::spawn_blocking(|| {
        rfd::FileDialog::new()
            .pick_folder()
            .map(|path| path.to_string_lossy().into_owned())
    })
    .await
    .ok()
    .flatten()
}

#[tauri::command]
async fn browse_sqlite_file() -> Option<String> {
    tauri::async_runtime::spawn_blocking(|| {
        rfd::FileDialog::new()
            .add_filter("SQLite database", &["sqlite3", "sqlite", "db"])
            .pick_file()
            .map(|path| path.to_string_lossy().into_owned())
    })
    .await
    .ok()
    .flatten()
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            default_configuration,
            framework_license,
            application_readme,
            inspect_source_path,
            inspect_existing_data,
            inspect_default_user_data,
            inspect_sqlite_database,
            inspect_alpha_users,
            browse_directory,
            browse_sqlite_file,
            preview_install_plan
        ])
        .run(tauri::generate_context!())
        .expect("failed to start Minglefield installer GUI");
}
