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
         INSERT INTO alpha_agents VALUES('agent1','alice',0);
         CREATE TABLE alpha_sessions(token_hash TEXT,user_id TEXT,expires_at INTEGER,revoked INTEGER);
         CREATE TABLE alpha_jobs(job_id TEXT,user_id TEXT,agent_id TEXT,idempotency_key TEXT,action TEXT);
         CREATE TABLE alpha_passwords(user_id TEXT,salt BLOB,password_hash BLOB);
         INSERT INTO alpha_passwords VALUES('alice',x'01',x'0203');
         CREATE TABLE alpha_agent_grants(agent_id TEXT,grantee_user_id TEXT,action TEXT,revoked INTEGER);
         CREATE TABLE sec01_host_effect_definitions(host_id TEXT,effect_id TEXT,description TEXT,enabled INTEGER);
         INSERT INTO sec01_host_effect_definitions VALUES('host1','effect1','Old description',0);
         CREATE TABLE alpha_game_projects(project_id TEXT,host_id TEXT,owner_id TEXT,name TEXT,repository_root TEXT,job_attachments_root TEXT,output_root TEXT,settings_revision INTEGER);
         INSERT INTO alpha_game_projects VALUES('game1','host1','alice','Old game','/games/one','/games/one/attachments','/games/one/output',1);
         CREATE TABLE alpha_git_profiles(host_id TEXT,profile_id TEXT,owner_id TEXT,label TEXT,auth_method TEXT,git_executable TEXT,author_name TEXT,author_email TEXT);
         INSERT INTO alpha_git_profiles VALUES('host1','profile1','alice','Personal','local','git','Alice','alice@example.test');
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
    assert!(preview.fidelity.values_verified);
    assert_eq!(preview.fidelity.tables_checked, 11);
    assert_eq!(preview.fidelity.rows_checked, 7);
    assert_eq!(preview.tables.len(), 11);
    assert_eq!(preview.field_coverage.len(), preview.tables.len());
    let games = preview
        .field_coverage
        .iter()
        .find(|entry| entry.table == "alpha_game_projects")
        .unwrap();
    assert_eq!(games.staged_editable_columns.len(), 8);
    assert!(games.protected_columns.is_empty());
    let passwords = preview
        .field_coverage
        .iter()
        .find(|entry| entry.table == "alpha_passwords")
        .unwrap();
    assert!(passwords
        .staged_editable_columns
        .contains(&"password_hash".to_owned()));
    assert!(passwords.protected_columns.is_empty());
    let extension = preview
        .field_coverage
        .iter()
        .find(|entry| entry.table == "extension_data")
        .unwrap();
    assert_eq!(extension.staged_editable_columns, vec!["secret"]);
    assert_eq!(extension.columns, vec!["secret"]);
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
    assert_eq!(preview.tables.len(), 11);
    assert!(preview.fidelity.values_verified);
    assert_eq!(preview.fidelity.internal_tables_checked, 0);
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

#[test]
fn rehearses_agent_disabled_without_changing_source() {
    let file = fixture();
    let original = std::fs::read(&file).unwrap();
    let change = ReviewCorrection::AgentDisabled {
        agent_id: "agent1".to_owned(),
        user_id: "alice".to_owned(),
        before: false,
        after: true,
    };
    let preview = rehearse_migration(&file, "", &[change]).unwrap();
    assert_eq!(preview.verified_changes, 1);
    assert_eq!(std::fs::read(&file).unwrap(), original);
    let stale = ReviewCorrection::AgentDisabled {
        agent_id: "agent1".to_owned(),
        user_id: "mallory".to_owned(),
        before: false,
        after: true,
    };
    assert!(rehearse_migration(&file, "", &[stale]).is_err());
    std::fs::remove_file(file).unwrap();
}

#[test]
fn rehearses_git_metadata_but_never_authentication_or_owner() {
    let file = fixture();
    let before_bytes = std::fs::read(&file).unwrap();
    let corrections = vec![
        ReviewCorrection::GitProfileText {
            host_id: "host1".into(),
            profile_id: "profile1".into(),
            owner_id: "alice".into(),
            field: GitProfileField::Label,
            before: "Personal".into(),
            after: "Updated".into(),
        },
        ReviewCorrection::GitProfileText {
            host_id: "host1".into(),
            profile_id: "profile1".into(),
            owner_id: "alice".into(),
            field: GitProfileField::AuthorEmail,
            before: "alice@example.test".into(),
            after: "alice@new.example".into(),
        },
    ];
    let preview = rehearse_migration(&file, "", &corrections).unwrap();
    assert_eq!(preview.verified_changes, 2);
    let git = preview
        .field_coverage
        .iter()
        .find(|entry| entry.table == "alpha_git_profiles")
        .unwrap();
    assert_eq!(git.staged_editable_columns.len(), 8);
    assert!(git.protected_columns.is_empty());
    assert_eq!(std::fs::read(&file).unwrap(), before_bytes);
    for bad in [
        ReviewCorrection::GitProfileText {
            host_id: "host1".into(),
            profile_id: "profile1".into(),
            owner_id: "mallory".into(),
            field: GitProfileField::Label,
            before: "Personal".into(),
            after: "Updated".into(),
        },
        ReviewCorrection::GitProfileText {
            host_id: "host1".into(),
            profile_id: "profile1".into(),
            owner_id: "alice".into(),
            field: GitProfileField::AuthorName,
            before: "stale".into(),
            after: "Updated".into(),
        },
        ReviewCorrection::GitProfileText {
            host_id: "host1".into(),
            profile_id: "profile1".into(),
            owner_id: "alice".into(),
            field: GitProfileField::Label,
            before: "Personal".into(),
            after: "".into(),
        },
    ] {
        assert!(rehearse_migration(&file, "", &[bad]).is_err());
    }
    std::fs::remove_file(file).unwrap();
}

#[test]
fn encrypted_alpha_source_is_verified_without_creating_output_or_changing_bytes() {
    let file = std::env::temp_dir().join(format!(
        "minglefield-fidelity-cipher-{}-{}.sqlite3",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    {
        let db = Connection::open(&file).unwrap();
        db.pragma_update(None, "key", "ExistingSourcePassword9!")
            .unwrap();
        db.execute_batch(
            "CREATE TABLE alpha_invites(invitation_hash TEXT,user_id TEXT,expires_at INTEGER,redeemed INTEGER,revoked INTEGER);
             CREATE TABLE alpha_users(user_id TEXT PRIMARY KEY,disabled INTEGER);
             INSERT INTO alpha_users VALUES('alice',0);
             CREATE TABLE alpha_agents(agent_id TEXT,user_id TEXT,disabled INTEGER);
             CREATE TABLE alpha_sessions(token_hash TEXT,user_id TEXT,expires_at INTEGER,revoked INTEGER);
             CREATE TABLE alpha_jobs(job_id TEXT,user_id TEXT,agent_id TEXT,idempotency_key TEXT,action TEXT);
             CREATE TABLE alpha_passwords(user_id TEXT,salt BLOB,password_hash BLOB);
             INSERT INTO alpha_passwords VALUES('alice',x'0001ff',x'eeff00');
             CREATE TABLE alpha_agent_grants(agent_id TEXT,grantee_user_id TEXT,action TEXT,revoked INTEGER);
             CREATE TABLE other_binary(blob BLOB);
             INSERT INTO other_binary VALUES(x'000000ff');"
        ).unwrap();
    }
    let source_bytes = std::fs::read(&file).unwrap();
    assert_ne!(&source_bytes[..16], b"SQLite format 3\0");
    let result = rehearse_migration(&file, "ExistingSourcePassword9!", &[]).unwrap();
    assert!(result.fidelity.values_verified);
    assert_eq!(result.fidelity.tables_checked, 8);
    assert_eq!(result.fidelity.rows_checked, 3);
    assert!(!result.destination_created);
    assert_eq!(std::fs::read(&file).unwrap(), source_bytes);
    assert!(rehearse_migration(&file, "incorrect-password", &[]).is_err());
    std::fs::remove_file(file).unwrap();
}

#[test]
fn plaintext_alpha_with_optional_password_keeps_second_copy_unencrypted() {
    let file = fixture();
    let original_bytes = std::fs::read(&file).unwrap();
    let normal = rehearse_migration(&file, "", &[]).unwrap();
    let password_supplied = rehearse_migration(&file, "IgnoredExistingDbPassword9!", &[]).unwrap();
    assert!(normal.fidelity.values_verified);
    assert_eq!(password_supplied.fidelity, normal.fidelity);
    assert_eq!(password_supplied.verified_changes, 0);
    let changed = rehearse_migration(&file, "IgnoredExistingDbPassword9!", &changes()).unwrap();
    assert!(changed.fidelity.values_verified);
    assert_eq!(changed.verified_changes, 3);
    assert_eq!(std::fs::read(&file).unwrap(), original_bytes);
    std::fs::remove_file(file).unwrap();
}

fn full_cell(kind: &str, value: Option<&str>) -> RawCell {
    RawCell {
        kind: kind.to_owned(),
        value: value.map(str::to_owned),
    }
}

#[test]
fn rehearses_workflow_host_rules_and_binary_cell_changes_without_source_writes() {
    let file = fixture();
    {
        let db = Connection::open(&file).unwrap();
        db.execute_batch(
            r#"CREATE TABLE sec01_host_rules(host_id TEXT, rule_id TEXT, config TEXT);
            INSERT INTO sec01_host_rules VALUES('h1','rule1','{"parallel":2}');
            CREATE TABLE sec01_host_comfy_workflows(host_id TEXT, workflow_id TEXT, definition BLOB);
            INSERT INTO sec01_host_comfy_workflows VALUES('h1','rig',x'00ff');
            CREATE TABLE extra_no_rowid(k TEXT PRIMARY KEY, note TEXT) WITHOUT ROWID;
            INSERT INTO extra_no_rowid VALUES('key','old');"#
        ).unwrap();
    }
    let before_bytes = std::fs::read(&file).unwrap();
    let changes = vec![
        ReviewCorrection::FullRow {
            table: "sec01_host_rules".into(),
            row_id: Some("1".into()),
            columns: vec!["host_id".into(), "rule_id".into(), "config".into()],
            before: vec![
                full_cell("text", Some("h1")),
                full_cell("text", Some("rule1")),
                full_cell("text", Some(r#"{"parallel":2}"#)),
            ],
            after: vec![
                full_cell("text", Some("h1")),
                full_cell("text", Some("rule1")),
                full_cell("text", Some(r#"{"parallel":3}"#)),
            ],
        },
        ReviewCorrection::FullRow {
            table: "sec01_host_comfy_workflows".into(),
            row_id: Some("1".into()),
            columns: vec!["host_id".into(), "workflow_id".into(), "definition".into()],
            before: vec![
                full_cell("text", Some("h1")),
                full_cell("text", Some("rig")),
                full_cell("blob", Some("00ff")),
            ],
            after: vec![
                full_cell("text", Some("h1")),
                full_cell("text", Some("rig")),
                full_cell("blob", Some("12ab")),
            ],
        },
        ReviewCorrection::FullRow {
            table: "extra_no_rowid".into(),
            row_id: None,
            columns: vec!["k".into(), "note".into()],
            before: vec![
                full_cell("text", Some("key")),
                full_cell("text", Some("old")),
            ],
            after: vec![
                full_cell("text", Some("key")),
                full_cell("text", Some("new")),
            ],
        },
    ];
    let result = rehearse_migration(&file, "", &changes).unwrap();
    assert_eq!(result.verified_changes, 3);
    assert!(result.fidelity.values_verified);
    assert!(!result.source_records_written);
    assert_eq!(std::fs::read(&file).unwrap(), before_bytes);
    let stale = vec![ReviewCorrection::FullRow {
        table: "sec01_host_rules".into(),
        row_id: Some("1".into()),
        columns: vec!["host_id".into(), "rule_id".into(), "config".into()],
        before: vec![
            full_cell("text", Some("h1")),
            full_cell("text", Some("rule1")),
            full_cell("text", Some("stale")),
        ],
        after: vec![
            full_cell("text", Some("h1")),
            full_cell("text", Some("rule1")),
            full_cell("text", Some("new")),
        ],
    }];
    assert!(rehearse_migration(&file, "", &stale).is_err());
    assert_eq!(std::fs::read(&file).unwrap(), before_bytes);
    std::fs::remove_file(file).unwrap();
}
