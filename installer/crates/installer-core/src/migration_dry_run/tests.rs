use super::*;
use std::time::{SystemTime, UNIX_EPOCH};

fn fixture() -> std::path::PathBuf {
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let file = std::env::temp_dir().join(format!(
        "minglefield-rehearsal-{}-{stamp}.sqlite3",
        std::process::id()
    ));
    let db = Connection::open(&file).unwrap();
    db.execute_batch(
        "CREATE TABLE alpha_invites(invitation_hash TEXT,user_id TEXT,expires_at INTEGER,redeemed INTEGER,revoked INTEGER);
         CREATE TABLE alpha_users(user_id TEXT PRIMARY KEY,disabled INTEGER);
         INSERT INTO alpha_users VALUES('alice',0);
         CREATE TABLE alpha_agents(agent_id TEXT,user_id TEXT,disabled INTEGER);
         CREATE TABLE alpha_sessions(token_hash TEXT,user_id TEXT,expires_at INTEGER,revoked INTEGER);
         CREATE TABLE alpha_jobs(job_id TEXT,user_id TEXT,agent_id TEXT,idempotency_key TEXT,action TEXT);
         CREATE TABLE alpha_passwords(user_id TEXT,salt BLOB,password_hash BLOB);
         INSERT INTO alpha_passwords VALUES('alice',x'01',x'0203');
         CREATE TABLE alpha_agent_grants(agent_id TEXT,grantee_user_id TEXT,action TEXT,revoked INTEGER);
         CREATE TABLE sec01_host_effect_definitions(host_id TEXT,effect_id TEXT,description TEXT,enabled INTEGER);
         INSERT INTO sec01_host_effect_definitions VALUES('host1','effect1','Old description',0);
         CREATE TABLE alpha_game_projects(project_id TEXT,host_id TEXT,owner_id TEXT,name TEXT,repository_root TEXT,job_attachments_root TEXT,output_root TEXT,settings_revision INTEGER);
         INSERT INTO alpha_game_projects VALUES('game1','host1','alice','Old game','/games/one','/games/one/attachments','/games/one/output',1);
         CREATE TABLE extension_data(secret BLOB);
         INSERT INTO extension_data VALUES(x'0102030405');"
    ).unwrap();
    drop(db);
    file
}

fn changes() -> Vec<ReviewCorrection> {
    vec![
        ReviewCorrection::UserDisabled {
            user_id: "alice".to_owned(),
            before: false,
            after: true,
        },
        ReviewCorrection::EffectDescription {
            host_id: "host1".to_owned(),
            effect_id: "effect1".to_owned(),
            before: "Old description".to_owned(),
            after: "New description".to_owned(),
        },
        ReviewCorrection::GameName {
            project_id: "game1".to_owned(),
            before: "Old game".to_owned(),
            after: "New game".to_owned(),
        },
    ]
}

#[test]
fn reviews_all_tables_and_rolls_back_every_staged_change() {
    let file = fixture();
    let bytes = std::fs::read(&file).unwrap();
    let preview = rehearse_migration(&file, "", &changes()).unwrap();
    assert_eq!(preview.verified_changes, 3);
    assert_eq!(preview.tables.len(), 10);
    assert_eq!(
        preview
            .tables
            .iter()
            .find(|item| item.table == "extension_data")
            .unwrap()
            .rows,
        1
    );
    assert!(!preview.execution_enabled);
    assert!(!preview.destination_created);
    assert!(!preview.source_records_written);
    assert_eq!(std::fs::read(&file).unwrap(), bytes);
    let db = Connection::open(&file).unwrap();
    let disabled: i64 = db
        .query_row("SELECT disabled FROM alpha_users", [], |r| r.get(0))
        .unwrap();
    let description: String = db
        .query_row(
            "SELECT description FROM sec01_host_effect_definitions",
            [],
            |r| r.get(0),
        )
        .unwrap();
    let game: String = db
        .query_row("SELECT name FROM alpha_game_projects", [], |r| r.get(0))
        .unwrap();
    assert_eq!(disabled, 0);
    assert_eq!(description, "Old description");
    assert_eq!(game, "Old game");
    drop(db);
    std::fs::remove_file(file).unwrap();
}

#[test]
fn rejects_stale_user_and_game_values_without_source_edits() {
    let file = fixture();
    let bytes = std::fs::read(&file).unwrap();
    for correction in [
        ReviewCorrection::UserDisabled {
            user_id: "alice".into(),
            before: true,
            after: false,
        },
        ReviewCorrection::GameName {
            project_id: "game1".into(),
            before: "Old".into(),
            after: "New".into(),
        },
    ] {
        assert!(rehearse_migration(&file, "", &[correction]).is_err());
    }
    assert_eq!(std::fs::read(&file).unwrap(), bytes);
    std::fs::remove_file(file).unwrap();
}

#[test]
fn rejects_duplicates_and_malformed_identity_or_name() {
    let file = fixture();
    let all = changes();
    assert!(rehearse_migration(&file, "", &[all[0].clone(), all[0].clone()]).is_err());
    assert!(rehearse_migration(
        &file,
        "",
        &[ReviewCorrection::UserDisabled {
            user_id: "../alice".into(),
            before: false,
            after: true,
        }]
    )
    .is_err());
    assert!(rehearse_migration(
        &file,
        "",
        &[ReviewCorrection::GameName {
            project_id: "game1".into(),
            before: "Old game".into(),
            after: " ".into(),
        }]
    )
    .is_err());
    std::fs::remove_file(file).unwrap();
}

#[test]
fn rejects_schema_that_is_not_complete_private_alpha() {
    let file = fixture();
    {
        let db = Connection::open(&file).unwrap();
        db.execute_batch("DROP TABLE alpha_sessions").unwrap();
    }
    let error = rehearse_migration(&file, "", &[]).unwrap_err();
    assert!(error.contains("alpha_sessions"));
    std::fs::remove_file(file).unwrap();
}

#[test]
fn blocks_unreviewed_triggers_before_applying_changes() {
    let file = fixture();
    {
        let db = Connection::open(&file).unwrap();
        db.execute_batch(
            "CREATE TRIGGER unexpected AFTER UPDATE ON alpha_users
             BEGIN UPDATE alpha_passwords SET salt=x'ff'; END;",
        )
        .unwrap();
    }
    let error = rehearse_migration(&file, "", &changes()).unwrap_err();
    assert!(error.contains("triggers"));
    std::fs::remove_file(file).unwrap();
}

#[test]
fn permits_no_change_rehearsal_and_never_creates_destination() {
    let file = fixture();
    let preview = rehearse_migration(&file, "", &[]).unwrap();
    assert_eq!(preview.verified_changes, 0);
    assert_eq!(preview.tables.len(), 10);
    assert!(!preview.execution_enabled);
    std::fs::remove_file(file).unwrap();
}

#[test]
fn rehearses_effect_activation_and_all_game_paths_without_any_source_mutation() {
    let file = fixture();
    let bytes = std::fs::read(&file).unwrap();
    let changes = vec![
        ReviewCorrection::EffectEnabled {
            host_id: "host1".into(),
            effect_id: "effect1".into(),
            before: false,
            after: true,
        },
        ReviewCorrection::GamePath {
            project_id: "game1".into(),
            field: GamePathField::RepositoryRoot,
            before: "/games/one".into(),
            after: "/new/game".into(),
        },
        ReviewCorrection::GamePath {
            project_id: "game1".into(),
            field: GamePathField::JobAttachmentsRoot,
            before: "/games/one/attachments".into(),
            after: "/new/attachments".into(),
        },
        ReviewCorrection::GamePath {
            project_id: "game1".into(),
            field: GamePathField::OutputRoot,
            before: "/games/one/output".into(),
            after: "/new/output".into(),
        },
    ];
    let result = rehearse_migration(&file, "", &changes).unwrap();
    assert_eq!(result.verified_changes, 4);
    assert_eq!(std::fs::read(&file).unwrap(), bytes);
    std::fs::remove_file(file).unwrap();
}

#[test]
fn rejects_invalid_and_stale_game_paths_and_effect_activation() {
    let file = fixture();
    for change in [
        ReviewCorrection::GamePath {
            project_id: "game1".into(),
            field: GamePathField::RepositoryRoot,
            before: "/games/one".into(),
            after: "relative".into(),
        },
        ReviewCorrection::GamePath {
            project_id: "game1".into(),
            field: GamePathField::OutputRoot,
            before: "/stale".into(),
            after: "/games/updated".into(),
        },
        ReviewCorrection::EffectEnabled {
            host_id: "host1".into(),
            effect_id: "effect1".into(),
            before: true,
            after: false,
        },
    ] {
        assert!(rehearse_migration(&file, "", &[change]).is_err());
    }
    std::fs::remove_file(file).unwrap();
}
