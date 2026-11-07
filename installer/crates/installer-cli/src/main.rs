//! Headless installer CLI: plan preview and explicitly approved managed Alpha
//! file installation plus reviewed SQLCipher inspection/copy. Host setup
//! and native app launch remain unimplemented; never imply full installation.
use minglefield_installer_core::config::InstallerConfig;
use minglefield_installer_core::config_v2::InstallerConfigV2;
use minglefield_installer_core::config_v3::{DatabaseOptions, InstallerConfigV3};
use minglefield_installer_core::managed_alpha_install::install_from_verified_root;
use minglefield_installer_core::{InstallPlan, Mode};
use std::env;
use std::path::Path;
use std::process::ExitCode;

mod database;
mod output;

use database::DatabaseAction;

const INSTALL_CONFIRMATION: &str = "INSTALL MINGLEFIELD ALPHA FILES";

#[derive(Default)]
struct FileInstallOptions {
    enabled: bool,
    source: Option<String>,
    inventory_sha256: Option<String>,
    confirmation: Option<String>,
}

fn require_option_value(
    args: &mut impl Iterator<Item = String>,
    name: &'static str,
) -> Result<String, (u8, String)> {
    args.next()
        .filter(|value| !value.starts_with("--"))
        .ok_or((2, format!("{name} requires a value")))
}

/// One real install operation: both the GUI and CLI invoke the shared Rust
/// core's exact inventory validation and non-overwriting file writer.
fn complete(
    plan: &InstallPlan,
    preview: String,
    action: &FileInstallOptions,
    db_action: &DatabaseAction,
    db_config: Option<&DatabaseOptions>,
    json: bool,
) -> Result<(), (u8, String)> {
    if db_action.active() {
        if action.enabled
            || action.source.is_some()
            || action.inventory_sha256.is_some()
            || action.confirmation.is_some()
        {
            return Err((2, "file and database operations require separate explicit actions".to_owned()));
        }
        if plan.install_optional_conda || plan.install_optional_comfyui {
            return Err((2, "optional runtime installation is not implemented for database operations".to_owned()));
        }
        return db_action.execute(db_config, json);
    }
    if db_action.has_unbound_inputs() || db_config.is_some_and(DatabaseOptions::has_any) {
        return Err((2, "database input options require an explicit database action".to_owned()));
    }
    if !action.enabled {
        if action.source.is_some()
            || action.inventory_sha256.is_some()
            || action.confirmation.is_some()
        {
            return Err((
                2,
                "package arguments require --install-alpha-files".to_owned(),
            ));
        }
        if json {
            println!("{preview}");
        } else {
            println!("PLAN ONLY (no files changed, no Host claimed): {plan:?}");
        }
        return Ok(());
    }
    let source = action.source.as_deref().ok_or((
        2,
        "--package-dir is required for file installation".to_owned(),
    ))?;
    let digest = action.inventory_sha256.as_deref().ok_or((
        2,
        "--inventory-sha256 is required for file installation".to_owned(),
    ))?;
    if action.confirmation.as_deref() != Some(INSTALL_CONFIRMATION) {
        return Err((
            2,
            "explicit --confirm-install approval is required".to_owned(),
        ));
    }
    if plan.install_optional_conda || plan.install_optional_comfyui {
        return Err((
            2,
            "optional runtime installation is not implemented in the file-only CLI".to_owned(),
        ));
    }
    let installed = match install_from_verified_root(
        Path::new(source),
        Path::new(&plan.install_dir),
        digest,
    ) {
        Ok(installed) => installed,
        Err(_) => {
            return Err((
                4,
                "verified managed Alpha file installation rejected; source, digest, or target invalid"
                    .to_owned(),
            ));
        }
    };
    if json {
        println!(
            "{}",
            output::installed_alpha_files(&installed.install_dir, installed.installed_entries)
        );
    } else {
        println!(
            "ALPHA FILES INSTALLED (not a full app launch or Host claim): {} verified entries",
            installed.installed_entries
        );
    }
    Ok(())
}

fn run(args: impl IntoIterator<Item = String>) -> Result<(), (u8, String)> {
    let mut args = args.into_iter();
    let mut json = false;
    let mut silent = false;
    let mut defaults = false;
    let mut install_dir: Option<String> = None;
    let mut data_dir: Option<String> = None;
    let mut config_file: Option<String> = None;
    let mut action = FileInstallOptions::default();
    let mut db_action = DatabaseAction::default();
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--silent" if !silent => silent = true,
            "--json" if !json => json = true,
            "--defaults" if !defaults => defaults = true,
            "--install-alpha-files" if !action.enabled => action.enabled = true,
            "--silent" | "--json" | "--defaults" | "--install-alpha-files" => {
                return Err((2, format!("duplicate argument: {arg}")));
            }
            "--install-dir" => {
                if install_dir.is_some() {
                    return Err((2, "duplicate argument: --install-dir".to_string()));
                }
                install_dir = Some(require_option_value(&mut args, "--install-dir")?);
            }
            "--data-dir" => {
                if data_dir.is_some() {
                    return Err((2, "duplicate argument: --data-dir".to_string()));
                }
                data_dir = Some(require_option_value(&mut args, "--data-dir")?);
            }
            "--package-dir" => {
                if action.source.is_some() {
                    return Err((2, "duplicate argument: --package-dir".to_owned()));
                }
                action.source = Some(require_option_value(&mut args, "--package-dir")?);
            }
            "--inventory-sha256" => {
                if action.inventory_sha256.is_some() {
                    return Err((2, "duplicate argument: --inventory-sha256".to_owned()));
                }
                action.inventory_sha256 =
                    Some(require_option_value(&mut args, "--inventory-sha256")?);
            }
            "--confirm-install" => {
                if action.confirmation.is_some() {
                    return Err((2, "duplicate argument: --confirm-install".to_owned()));
                }
                action.confirmation = Some(require_option_value(&mut args, "--confirm-install")?);
            }
            "--config" => {
                if config_file.is_some() {
                    return Err((2, "duplicate argument: --config".to_owned()));
                }
                config_file = Some(require_option_value(&mut args, "--config")?);
            }
            "--help" | "-h" => {
                println!(
                    "Usage: minglefield-installer-cli --silent (--defaults | --config FILE) \\
                     [--install-dir ABSOLUTE_PATH] [--data-dir ABSOLUTE_PATH] [--json]"
                );
                println!(
                    "File-only install: add --install-alpha-files --package-dir PATH \\
                     --inventory-sha256 HEX --confirm-install 'INSTALL MINGLEFIELD ALPHA FILES'"
                );
                println!(
                    "Default operation is PLAN ONLY. File install is not database migration, \\
                     Host provisioning, release provenance or an application launcher."
                );
                println!("Database: --verify-encrypted-db or --create-encrypted-copy, with --database PATH,");
                println!("  --source-db PATH --backup-db PATH --db-password VALUE --new-db-password VALUE");
                println!("  --db-password-file PATH --new-db-password-file PATH --secrets-stdin");
                println!("  --schema-add ID --confirm-db-copy 'CREATE EXPERIMENTAL ENCRYPTED COPY'.");
                println!("V3 config supports database_path, source_db_path, backup_db_path, db_password,");
                println!("  db_password_file, new_db_password, new_db_password_file.");
                println!("Env: MINGLEFIELD_DB_PASSWORD, MINGLEFIELD_NEW_DB_PASSWORD.");
                println!("Database copy neither provisions Hosts nor launches the app.");
                return Ok(());
            }
            _ => {
                if !db_action.parse(&arg, &mut args)? {
                    return Err((2, "unsupported argument; use --help".to_owned()));
                }
            }
        }
    }
    if !silent || (defaults == config_file.is_some()) {
        return Err((
            2,
            "require --silent and exactly one of --defaults or --config FILE".to_owned(),
        ));
    }
    if let Some(file) = config_file {
        let text = std::fs::read_to_string(&file)
            .map_err(|_| (3, "cannot read installer configuration".to_owned()))?;
        let version_lines: Vec<&str> = text
            .lines()
            .map(str::trim)
            .filter(|line| !line.is_empty() && !line.starts_with('#'))
            .filter(|line| {
                line.split_once('=')
                    .is_some_and(|(key, _)| key.trim() == "version")
            })
            .collect();
        if version_lines.len() != 1 {
            return Err((3, "invalid config: missing or duplicate version".to_owned()));
        }
        let version = version_lines[0]
            .split_once('=')
            .map(|(_, value)| value.trim())
            .unwrap_or("");
        if version == "3" {
            let mut config = InstallerConfigV3::parse(&text)
                .map_err(|_| (3, "invalid version 3 configuration".to_owned()))?;
            if let Some(path) = install_dir {
                config.base.base.install_dir = path;
            }
            if let Some(path) = data_dir {
                config.base.base.data_dir = path;
            }
            let plan = config
                .preview(Mode::Silent)
                .map_err(|_| (3, "invalid installation plan".to_owned()))?;
            if (action.enabled || db_action.active())
                && (config.base.git_tools.install_optional_git
                    || config.base.git_tools.install_optional_gh
                    || config.base.git_tools.offer_gh_login)
            {
                return Err((
                    2,
                    "Git/gh optional installation not implemented in this CLI action".to_owned(),
                ));
            }
            complete(
                &plan,
                output::success_v3(&config, &plan),
                &action,
                &db_action,
                Some(&config.database),
                json,
            )?;
        } else if version == "2" {
            let mut config = InstallerConfigV2::parse(&text)
                .map_err(|_| (3, "invalid version 2 configuration".to_owned()))?;
            if let Some(path) = install_dir {
                config.base.install_dir = path;
            }
            if let Some(path) = data_dir {
                config.base.data_dir = path;
            }
            let plan = config
                .preview(Mode::Silent)
                .map_err(|_| (3, "invalid installation plan".to_owned()))?;
            if action.enabled
                && (config.git_tools.install_optional_git
                    || config.git_tools.install_optional_gh
                    || config.git_tools.offer_gh_login)
            {
                return Err((
                    2,
                    "Git/gh optional installation not implemented in file-only CLI".to_owned(),
                ));
            }
            complete(&plan, output::success_v2(&config, &plan), &action, &db_action, None, json)?;
        } else {
            let mut config = InstallerConfig::parse(&text)
                .map_err(|_| (3, "invalid version 1 configuration".to_owned()))?;
            if let Some(path) = install_dir {
                config.install_dir = path;
            }
            if let Some(path) = data_dir {
                config.data_dir = path;
            }
            let plan = config
                .preview(Mode::Silent)
                .map_err(|_| (3, "invalid installation plan".to_owned()))?;
            complete(&plan, output::success(&config, &plan), &action, &db_action, None, json)?;
        }
    } else {
        let mut config = InstallerConfig::defaults()
            .map_err(|_| (3, "cannot determine default paths".to_owned()))?;
        if let Some(path) = install_dir {
            config.install_dir = path;
        }
        if let Some(path) = data_dir {
            config.data_dir = path;
        }
        let plan = config
            .preview(Mode::Silent)
            .map_err(|_| (3, "invalid installation plan".to_owned()))?;
        complete(&plan, output::success(&config, &plan), &action, &db_action, None, json)?;
    }
    Ok(())
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().skip(1).collect();
    let json = args.iter().any(|arg| arg == "--json");
    match run(args) {
        Ok(()) => ExitCode::SUCCESS,
        Err((code, message)) => {
            if json {
                println!("{}", output::failure(code, &message));
            } else {
                eprintln!("{message}");
            }
            ExitCode::from(code)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_missing_config_and_missing_option_values() {
        assert_eq!(
            run(["--silent".to_string(), "--config".to_string()])
                .unwrap_err()
                .0,
            2
        );
        assert_eq!(
            run([
                "--silent".to_string(),
                "--defaults".to_string(),
                "--install-dir".to_string()
            ])
            .unwrap_err()
            .0,
            2
        );
        assert_eq!(
            run([
                "--silent".to_string(),
                "--config".to_string(),
                "__minglefield_missing_config__".to_string()
            ])
            .unwrap_err()
            .0,
            3
        );
    }

    #[test]
    fn rejects_duplicate_and_unvalued_options() {
        for args in [
            vec!["--silent", "--silent", "--defaults"],
            vec!["--silent", "--defaults", "--defaults"],
            vec!["--silent", "--defaults", "--json", "--json"],
            vec![
                "--silent",
                "--defaults",
                "--install-dir",
                "/tmp",
                "--install-dir",
                "/tmp",
            ],
            vec!["--silent", "--config", "one", "--config", "two"],
            vec!["--silent", "--config", "--json"],
            vec!["--silent", "--defaults", "--install-dir", "--json"],
        ] {
            let result = run(args.into_iter().map(str::to_owned));
            assert_eq!(result.unwrap_err().0, 2);
        }
    }

    #[test]
    fn rejects_ambiguous_modes() {
        assert!(run([
            "--silent".to_string(),
            "--defaults".to_string(),
            "--config".to_string(),
            "x".to_string()
        ])
        .is_err());
        assert!(run(["--defaults".to_string()]).is_err());
        assert!(run(["--silent".to_string()]).is_err());
    }

    fn disposable_managed_package() -> (std::path::PathBuf, std::path::PathBuf, String) {
        use minglefield_installer_core::integrity::sha256_hex;
        use std::fs;
        let root = std::env::temp_dir().join(format!(
            "mf-cli-install-test-{}-{:x}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let source = root.join("verified-source");
        let application = source.join("application/server/installed_alpha_launch.py");
        let python = source.join("runtime/python/bin/python3.11");
        fs::create_dir_all(application.parent().unwrap()).unwrap();
        fs::create_dir_all(python.parent().unwrap()).unwrap();
        fs::write(application, b"abc").unwrap();
        fs::write(python, b"def").unwrap();
        let inventory = concat!(
            "{\"schemaVersion\":1,\"files\":{",
            "\"application/server/installed_alpha_launch.py\":",
            "{\"type\":\"file\",\"size\":3,\"sha256\":",
            "\"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\"},",
            "\"runtime/python/bin/python3.11\":",
            "{\"type\":\"file\",\"size\":3,\"sha256\":",
            "\"cb8379ac2098aa165029e3938a51da0bcecfc008fd6795f401178647f96c5b34\"}}}"
        );
        fs::write(source.join("managed-file-inventory.json"), inventory).unwrap();
        fs::write(source.join("runtime-manifest.json"), "{}").unwrap();
        (root, source, sha256_hex(inventory.as_bytes()))
    }

    #[test]
    fn actually_installs_verified_alpha_files_only_with_explicit_consent() {
        use std::fs;
        let (root, source, digest) = disposable_managed_package();
        let target = root.join("new-application");
        let args = vec![
            "--silent".to_owned(),
            "--defaults".to_owned(),
            "--install-dir".to_owned(),
            target.to_string_lossy().into_owned(),
            "--install-alpha-files".to_owned(),
            "--package-dir".to_owned(),
            source.to_string_lossy().into_owned(),
            "--inventory-sha256".to_owned(),
            digest.clone(),
        ];
        assert_eq!(run(args.clone()).unwrap_err().0, 2);
        assert!(!target.exists());
        let mut approved = args;
        approved.extend([
            "--confirm-install".to_owned(),
            INSTALL_CONFIRMATION.to_owned(),
        ]);
        assert!(run(approved.clone()).is_ok());
        assert_eq!(
            fs::read(target.join("application/server/installed_alpha_launch.py")).unwrap(),
            b"abc"
        );
        assert_eq!(run(approved).unwrap_err().0, 4);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn tampered_bundle_does_not_create_destination() {
        use std::fs;
        let (root, source, digest) = disposable_managed_package();
        let target = root.join("not-created");
        fs::write(source.join("runtime/python/bin/python3.11"), b"tampered").unwrap();
        let args = vec![
            "--silent".to_owned(),
            "--defaults".to_owned(),
            "--install-dir".to_owned(),
            target.to_string_lossy().into_owned(),
            "--install-alpha-files".to_owned(),
            "--package-dir".to_owned(),
            source.to_string_lossy().into_owned(),
            "--inventory-sha256".to_owned(),
            digest,
            "--confirm-install".to_owned(),
            INSTALL_CONFIRMATION.to_owned(),
        ];
        assert_eq!(run(args).unwrap_err().0, 4);
        assert!(!target.exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn refuses_database_password_without_explicit_operation() {
        let args = vec![
            "--silent".to_owned(),
            "--defaults".to_owned(),
            "--db-password".to_owned(),
            "NotPrintedSecret111!".to_owned(),
        ];
        let error = run(args).unwrap_err();
        assert_eq!(error.0, 2);
        assert!(!error.1.contains("NotPrintedSecret111!"));
    }

    #[test]
    fn database_verification_uses_real_sqlcipher_and_rejects_fake_header() {
        let root = std::env::temp_dir().join(format!(
            "mf-cli-db-verification-{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&root).unwrap();
        let candidate = root.join("fake-encrypted.db");
        std::fs::write(&candidate, b"fake-not-sqlcipher").unwrap();
        let before = std::fs::read(&candidate).unwrap();
        let result = run(vec![
            "--silent".to_owned(),
            "--defaults".to_owned(),
            "--verify-encrypted-db".to_owned(),
            "--database".to_owned(),
            candidate.to_string_lossy().into_owned(),
            "--db-password".to_owned(),
            "NotPrintedSecret111!".to_owned(),
        ]);
        let error = result.unwrap_err();
        assert_eq!(error.0, 4);
        assert!(!error.1.contains("NotPrintedSecret111!"));
        assert_eq!(std::fs::read(&candidate).unwrap(), before);
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn v3_admin_authored_config_accepts_plaintext_password_field() {
        let root = std::env::temp_dir().join(format!(
            "mf-cli-v3-conf-{}",
            std::process::id()
        ));
        std::fs::create_dir_all(&root).unwrap();
        let configuration = root.join("config.conf");
        let text = concat!(
            "version=3\ninstall_optional_conda=false\ninstall_optional_comfyui=false\n",
            "explicit_optional_consent=false\ninstall_optional_git=false\n",
            "install_optional_gh=false\noffer_gh_login=false\n",
            "consent_git=false\nconsent_gh=false\nconsent_login=false\n",
            "database_path=/missing/private.db\n",
            "db_password=NotPrintedSecret111!\n"
        );
        std::fs::write(&configuration, text).unwrap();
        let result = run(vec![
            "--silent".to_owned(),
            "--config".to_owned(),
            configuration.to_string_lossy().into_owned(),
            "--verify-encrypted-db".to_owned(),
        ]);
        let error = result.unwrap_err();
        assert_eq!(error.0, 4);
        assert!(!error.1.contains("NotPrintedSecret111!"));
        std::fs::remove_dir_all(root).unwrap();
    }
}
