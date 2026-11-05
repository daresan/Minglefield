//! Non-persistent migration rehearsal command. Never writes a destination.
use minglefield_installer_core::migration_destination::preview_migration_destination;
use minglefield_installer_core::migration_dry_run::{
    rehearse_migration, ReviewCorrection,
};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum StagedCorrection {
    UserDisabled {
        user_id: String,
        before: bool,
        after: bool,
    },
    EffectDescription {
        host_id: String,
        effect_id: String,
        before: String,
        after: String,
    },
    GameName {
        project_id: String,
        before: String,
        after: String,
    },
}

impl From<StagedCorrection> for ReviewCorrection {
    fn from(value: StagedCorrection) -> Self {
        match value {
            StagedCorrection::UserDisabled { user_id, before, after } => {
                Self::UserDisabled { user_id, before, after }
            }
            StagedCorrection::EffectDescription {
                host_id,
                effect_id,
                before,
                after,
            } => Self::EffectDescription {
                host_id,
                effect_id,
                before,
                after,
            },
            StagedCorrection::GameName { project_id, before, after } => {
                Self::GameName { project_id, before, after }
            }
        }
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TableCountPreview {
    table: String,
    rows: u64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MigrationRehearsalPreview {
    status: &'static str,
    source_integrity_verified: bool,
    destination_path_validated: bool,
    source_preserved: bool,
    destination_created: bool,
    verified_changes: usize,
    preserved_tables: Vec<TableCountPreview>,
    schema_object_count: usize,
    execution_enabled: bool,
}

#[tauri::command]
pub async fn preview_migration_rehearsal(
    source_path: String,
    destination_path: String,
    password: String,
    corrections: Vec<StagedCorrection>,
) -> Result<MigrationRehearsalPreview, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let source = Path::new(&source_path);
        let destination = Path::new(&destination_path);
        let target = preview_migration_destination(source, destination)
            .map_err(|error| format!("Migration destination rejected: {error:?}"))?;
        let changes = corrections.into_iter().map(ReviewCorrection::from).collect::<Vec<_>>();
        let inspected = rehearse_migration(source, &password, &changes)?;
        Ok(MigrationRehearsalPreview {
            status: "verified_rehearsal_only",
            source_integrity_verified: true,
            destination_path_validated: target.preserves_source,
            source_preserved: !inspected.source_records_written,
            destination_created: inspected.destination_created,
            verified_changes: inspected.verified_changes,
            preserved_tables: inspected.tables.into_iter().map(|table| TableCountPreview {
                table: table.table,
                rows: table.rows,
            }).collect(),
            schema_object_count: inspected.schema_objects,
            execution_enabled: false,
        })
    })
    .await
    .map_err(|_| "Migration rehearsal worker failed".to_owned())?
}
