//! Non-persistent migration rehearsal command. Never writes a destination.
use minglefield_installer_core::encrypted_copy_preflight::{
    execute_reviewed_encrypted_copy, rehearse_encrypted_test_copy,
    EXPERIMENTAL_COPY_CONFIRMATION,
};
use minglefield_installer_core::migration_destination::preview_migration_destination;
use minglefield_installer_core::migration_dry_run::{
    rehearse_migration, GamePathField, GitProfileField, ReviewCorrection,
};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FullCellValue {
    pub(crate) kind: String,
    pub(crate) value: Option<String>,
}

impl FullCellValue {
    fn into_core(self) -> minglefield_installer_core::migration_dry_run::RawCell {
        minglefield_installer_core::migration_dry_run::RawCell {
            kind: self.kind,
            value: self.value,
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum StagedCorrection {
    FullRow {
        table: String,
        row_id: Option<String>,
        columns: Vec<String>,
        before: Vec<FullCellValue>,
        after: Vec<FullCellValue>,
    },
    UserDisabled {
        user_id: String,
        before: bool,
        after: bool,
    },
    AgentDisabled {
        agent_id: String,
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
    EffectEnabled {
        host_id: String,
        effect_id: String,
        before: bool,
        after: bool,
    },
    GamePath {
        project_id: String,
        field: StagedGamePathField,
        before: String,
        after: String,
    },
    GitProfileText {
        host_id: String,
        profile_id: String,
        owner_id: String,
        field: StagedGitProfileField,
        before: String,
        after: String,
    },
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StagedGitProfileField {
    Label,
    AuthorName,
    AuthorEmail,
}

impl From<StagedGitProfileField> for GitProfileField {
    fn from(value: StagedGitProfileField) -> Self {
        match value {
            StagedGitProfileField::Label => Self::Label,
            StagedGitProfileField::AuthorName => Self::AuthorName,
            StagedGitProfileField::AuthorEmail => Self::AuthorEmail,
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StagedGamePathField {
    #[serde(rename = "repository_root")]
    Repository,
    #[serde(rename = "job_attachments_root")]
    JobAttachments,
    #[serde(rename = "output_root")]
    Output,
}

impl From<StagedGamePathField> for GamePathField {
    fn from(value: StagedGamePathField) -> Self {
        match value {
            StagedGamePathField::Repository => Self::RepositoryRoot,
            StagedGamePathField::JobAttachments => Self::JobAttachmentsRoot,
            StagedGamePathField::Output => Self::OutputRoot,
        }
    }
}

impl From<StagedCorrection> for ReviewCorrection {
    fn from(value: StagedCorrection) -> Self {
        match value {
            StagedCorrection::FullRow {
                table,
                row_id,
                columns,
                before,
                after,
            } => Self::FullRow {
                table,
                row_id,
                columns,
                before: before.into_iter().map(FullCellValue::into_core).collect(),
                after: after.into_iter().map(FullCellValue::into_core).collect(),
            },
            StagedCorrection::UserDisabled {
                user_id,
                before,
                after,
            } => Self::UserDisabled {
                user_id,
                before,
                after,
            },
            StagedCorrection::AgentDisabled {
                agent_id,
                user_id,
                before,
                after,
            } => Self::AgentDisabled {
                agent_id,
                user_id,
                before,
                after,
            },
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
            StagedCorrection::GameName {
                project_id,
                before,
                after,
            } => Self::GameName {
                project_id,
                before,
                after,
            },
            StagedCorrection::EffectEnabled {
                host_id,
                effect_id,
                before,
                after,
            } => Self::EffectEnabled {
                host_id,
                effect_id,
                before,
                after,
            },
            StagedCorrection::GamePath {
                project_id,
                field,
                before,
                after,
            } => Self::GamePath {
                project_id,
                field: field.into(),
                before,
                after,
            },
            StagedCorrection::GitProfileText {
                host_id,
                profile_id,
                owner_id,
                field,
                before,
                after,
            } => Self::GitProfileText {
                host_id,
                profile_id,
                owner_id,
                field: field.into(),
                before,
                after,
            },
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
pub struct TableFieldCoveragePreview {
    table: String,
    columns: Vec<String>,
    staged_editable_columns: Vec<String>,
    protected_columns: Vec<String>,
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
    field_coverage: Vec<TableFieldCoveragePreview>,
    schema_object_count: usize,
    full_data_copy_verified: bool,
    verified_row_count: u64,
    verified_table_count: usize,
    verified_schema_entry_count: usize,
    verified_internal_table_count: usize,
    encrypted_destination_verified: bool,
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
        let changes = corrections
            .into_iter()
            .map(ReviewCorrection::from)
            .collect::<Vec<_>>();
        let inspected = rehearse_migration(source, &password, &changes)?;
        Ok(MigrationRehearsalPreview {
            status: "verified_rehearsal_only",
            source_integrity_verified: true,
            destination_path_validated: target.preserves_source,
            source_preserved: !inspected.source_records_written,
            destination_created: inspected.destination_created,
            verified_changes: inspected.verified_changes,
            preserved_tables: inspected
                .tables
                .into_iter()
                .map(|table| TableCountPreview {
                    table: table.table,
                    rows: table.rows,
                })
                .collect(),
            field_coverage: inspected
                .field_coverage
                .into_iter()
                .map(|coverage| TableFieldCoveragePreview {
                    table: coverage.table,
                    columns: coverage.columns,
                    staged_editable_columns: coverage.staged_editable_columns,
                    protected_columns: coverage.protected_columns,
                })
                .collect(),
            schema_object_count: inspected.schema_objects,
            full_data_copy_verified: inspected.fidelity.values_verified,
            verified_row_count: inspected.fidelity.rows_checked,
            verified_table_count: inspected.fidelity.tables_checked,
            verified_schema_entry_count: inspected.fidelity.schema_entries_checked,
            verified_internal_table_count: inspected.fidelity.internal_tables_checked,
            encrypted_destination_verified: false,
            execution_enabled: false,
        })
    })
    .await
    .map_err(|_| "Migration rehearsal worker failed".to_owned())?
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TemporaryEncryptedCopyPreview {
    status: &'static str,
    source_integrity_verified: bool,
    full_source_copy_verified: bool,
    temporary_encrypted_copy_verified: bool,
    ciphertext_header_verified: bool,
    wrong_key_rejected: bool,
    atomic_temporary_publication_verified: bool,
    full_disk_copy_verified: bool,
    verified_staged_changes: usize,
    staged_values_match_ciphertext: bool,
    checked_rows: u64,
    checked_tables: usize,
    checked_schema_entries: usize,
    temporary_files_removed: bool,
    destination_created: bool,
    encrypted_destination_verified: bool,
    execution_enabled: bool,
}

/// Explicit, user-initiated, temporary disk rehearsal. Nothing is written
/// to the proposed destination path or the Alpha source.
#[tauri::command]
pub async fn verify_temporary_encrypted_copy(
    source_path: String,
    destination_path: String,
    existing_password: String,
    new_password: String,
    corrections: Vec<StagedCorrection>,
) -> Result<TemporaryEncryptedCopyPreview, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let source = Path::new(&source_path);
        let destination = Path::new(&destination_path);
        preview_migration_destination(source, destination)
            .map_err(|error| format!("Migration destination rejected: {error:?}"))?;
        // Validate the user's exact staged changes in an independent memory
        // rehearsal before authorizing *temporary* encrypted file creation.
        let changes: Vec<ReviewCorrection> = corrections
            .into_iter()
            .map(ReviewCorrection::from)
            .collect();
        let baseline = rehearse_migration(source, &existing_password, &changes)?;
        let proof =
            rehearse_encrypted_test_copy(source, &existing_password, &new_password, &changes)?;
        if proof.staged_changes_verified != changes.len()
            || proof.staged_changes_verified != baseline.verified_changes
            || !proof.staged_values_match_ciphertext
            || !proof.atomic_temporary_publication_verified
            || proof.rows_checked != baseline.fidelity.rows_checked
            || proof.tables_checked != baseline.fidelity.tables_checked
            || proof.schema_entries_checked != baseline.fidelity.schema_entries_checked
            || !proof.temporary_files_removed
            || proof.destination_created
            || proof.encrypted_destination_verified
            || proof.execution_enabled
        {
            return Err("Encrypted disk rehearsal did not satisfy safety checks".to_owned());
        }
        Ok(TemporaryEncryptedCopyPreview {
            status: "temporary_encrypted_copy_verified",
            source_integrity_verified: true,
            full_source_copy_verified: proof.full_source_verified,
            temporary_encrypted_copy_verified: proof.full_disk_copy_verified,
            ciphertext_header_verified: proof.ciphertext_header_verified,
            wrong_key_rejected: proof.wrong_key_rejected,
            atomic_temporary_publication_verified: proof.atomic_temporary_publication_verified,
            full_disk_copy_verified: proof.full_disk_copy_verified,
            verified_staged_changes: proof.staged_changes_verified,
            staged_values_match_ciphertext: proof.staged_values_match_ciphertext,
            checked_rows: proof.rows_checked,
            checked_tables: proof.tables_checked,
            checked_schema_entries: proof.schema_entries_checked,
            temporary_files_removed: proof.temporary_files_removed,
            destination_created: false,
            encrypted_destination_verified: false,
            execution_enabled: false,
        })
    })
    .await
    .map_err(|_| "Temporary encrypted copy rehearsal worker failed".to_owned())?
}

fn verify_local_experimental_approval(
    backup_path: &str,
    confirmation: &str,
) -> Result<(), String> {
    if confirmation != EXPERIMENTAL_COPY_CONFIRMATION {
        return Err("Exact experimental encrypted-copy confirmation is required".to_owned());
    }
    if backup_path.trim().is_empty() {
        return Err("A separate, existing source backup file is required".to_owned());
    }
    Ok(())
}

#[cfg(test)]
mod experimental_copy_approval_tests {
    use super::{verify_local_experimental_approval, EXPERIMENTAL_COPY_CONFIRMATION};

    #[test]
    fn no_unconfirmed_experimental_file_write() {
        assert!(verify_local_experimental_approval("", "").is_err());
        assert!(verify_local_experimental_approval("backup.sqlite3", "YES").is_err());
        assert!(verify_local_experimental_approval("", EXPERIMENTAL_COPY_CONFIRMATION).is_err());
        assert!(verify_local_experimental_approval(
            "backup.sqlite3",
            EXPERIMENTAL_COPY_CONFIRMATION,
        ).is_ok());
    }
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ExperimentalEncryptedCopyResult {
    status: &'static str,
    source_preserved: bool,
    backup_verified: bool,
    destination_created: bool,
    encrypted_destination_verified: bool,
    full_disk_copy_verified: bool,
    checked_rows: u64,
    checked_tables: usize,
    checked_schema_entries: usize,
    verified_staged_changes: usize,
    temporary_files_removed: bool,
    application_installation_enabled: bool,
    host_provisioning_enabled: bool,
}

/// A locally consented *database-copy-only* Alpha action. The core validates
/// an existing independent backup against the current source and refuses
/// collisions before generating an encrypted destination. No Host claim or
/// app install is performed; this is not a general-purpose migration API.
#[tauri::command]
pub async fn create_experimental_encrypted_copy(
    source_path: String,
    destination_path: String,
    backup_path: String,
    existing_password: String,
    new_password: String,
    corrections: Vec<StagedCorrection>,
    confirmation: String,
) -> Result<ExperimentalEncryptedCopyResult, String> {
    verify_local_experimental_approval(&backup_path, &confirmation)?;
    tauri::async_runtime::spawn_blocking(move || {
        let changes: Vec<ReviewCorrection> = corrections
            .into_iter()
            .map(ReviewCorrection::from)
            .collect();
        let source = Path::new(&source_path);
        let destination = Path::new(&destination_path);
        let backup = Path::new(&backup_path);
        let baseline = rehearse_migration(source, &existing_password, &changes)?;
        if !baseline.fidelity.values_verified || baseline.source_records_written {
            return Err("Current source rehearsal must verify before execution".to_owned());
        }
        let proof = execute_reviewed_encrypted_copy(
            source,
            destination,
            backup,
            &existing_password,
            &new_password,
            &changes,
            &confirmation,
        )?;
        if !proof.full_source_verified
            || !proof.full_disk_copy_verified
            || !proof.encrypted_destination_verified
            || !proof.destination_created
            || !proof.temporary_files_removed
            || proof.execution_enabled
            || proof.staged_changes_verified != changes.len()
            || proof.rows_checked != baseline.fidelity.rows_checked
            || proof.tables_checked != baseline.fidelity.tables_checked
            || proof.schema_entries_checked != baseline.fidelity.schema_entries_checked
        {
            return Err("Experimental encrypted destination did not satisfy verification".into());
        }
        Ok(ExperimentalEncryptedCopyResult {
            status: "experimental_encrypted_copy_created",
            source_preserved: true,
            backup_verified: true,
            destination_created: true,
            encrypted_destination_verified: true,
            full_disk_copy_verified: true,
            checked_rows: proof.rows_checked,
            checked_tables: proof.tables_checked,
            checked_schema_entries: proof.schema_entries_checked,
            verified_staged_changes: proof.staged_changes_verified,
            temporary_files_removed: true,
            application_installation_enabled: false,
            host_provisioning_enabled: false,
        })
    })
    .await
    .map_err(|_| "Experimental encrypted copy worker failed".to_owned())?
}
