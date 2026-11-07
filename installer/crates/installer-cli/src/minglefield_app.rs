//! Native Minglefield Alpha application entrypoint (M2.09/M2.10).
//! Ships beside the managed, pinned embedded Python/SQLCipher runtime, but
//! needs no Setup Manager, external Python, Cargo, checkout, or Host claim.
//!
//! The public owner-selected credentials follow the same Bee-like V3
//! configuration fields as the installer. This is a launch executable, not
//! a general-purpose Host provisioning interface. No credentials are logged.
use minglefield_installer_core::config_v3::{
    parse_stdin_secrets, DatabaseOptions, InstallerConfigV3,
};
use minglefield_installer_core::db_operations::verify_encrypted_database;
use minglefield_installer_core::managed_alpha_install::verify_installed_application;
use serde_json::{json, Value};
mod native_start_dialog;
use native_start_dialog::DialogKind;
use std::env;
use std::fs;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::time::Duration;

const MAX_MANIFEST_BYTES: u64 = 64 * 1024;
const MAX_FRAME: usize = 8192;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(90);

#[derive(Default)]
struct LaunchOptions {
    database: DatabaseOptions,
    config: Option<PathBuf>,
    stdin: bool,
    verify_only: bool,
    no_browser: bool,
    probe_exit: bool,
    no_dialog: bool,
}

fn option_value(
    args: &mut impl Iterator<Item = String>,
    field: &mut Option<String>,
) -> Result<(), &'static str> {
    if field.is_some() {
        return Err("duplicate native application option");
    }
    let value = args
        .next()
        .ok_or("missing native application option value")?;
    if value.starts_with("--") {
        return Err("missing native application option value");
    }
    *field = Some(value);
    Ok(())
}

fn parse_args(args: impl IntoIterator<Item = String>) -> Result<LaunchOptions, &'static str> {
    let mut input = args.into_iter();
    let mut opts = LaunchOptions::default();
    while let Some(arg) = input.next() {
        if let Some((name, value)) = arg.split_once('=') {
            let field = match name {
                "--database" => &mut opts.database.database_path,
                "--db-password" => &mut opts.database.password.literal,
                "--db-password-file" => &mut opts.database.password.file,
                _ => return Err("unsupported native application option"),
            };
            if field.replace(value.to_owned()).is_some() {
                return Err("duplicate native application option");
            }
            continue;
        }
        match arg.as_str() {
            "--database" => option_value(&mut input, &mut opts.database.database_path)?,
            "--db-password" => option_value(&mut input, &mut opts.database.password.literal)?,
            "--db-password-file" => option_value(&mut input, &mut opts.database.password.file)?,
            "--config" => {
                if opts.config.is_some() {
                    return Err("duplicate configuration option");
                }
                opts.config = Some(PathBuf::from(
                    input.next().ok_or("missing native configuration path")?,
                ));
            }
            "--secrets-stdin" if !opts.stdin => opts.stdin = true,
            "--verify-only" if !opts.verify_only => opts.verify_only = true,
            "--no-browser" if !opts.no_browser => opts.no_browser = true,
            "--probe-exit" if !opts.probe_exit => opts.probe_exit = true,
            "--no-dialog" if !opts.no_dialog => opts.no_dialog = true,
            _ => return Err("unsupported or duplicate native application option"),
        }
    }
    if opts.probe_exit && opts.verify_only {
        return Err("conflicting native application operations");
    }
    Ok(opts)
}

fn regular_file(path: &Path) -> Result<(), &'static str> {
    let meta = fs::symlink_metadata(path).map_err(|_| "native file unavailable")?;
    if !meta.is_file() || meta.file_type().is_symlink() {
        return Err("native file must be a regular file");
    }
    Ok(())
}

struct InstalledApp {
    root: PathBuf,
    python: PathBuf,
    worker: PathBuf,
    managed_files: usize,
}

fn manifest_string<'a>(manifest: &'a Value, name: &str) -> Result<&'a str, &'static str> {
    manifest
        .get(name)
        .and_then(Value::as_str)
        .ok_or("native application manifest field absent")
}

fn installed_app(executable: &Path) -> Result<InstalledApp, &'static str> {
    regular_file(executable)?;
    let root = executable
        .parent()
        .ok_or("native application directory unavailable")?;
    if fs::symlink_metadata(root)
        .map_err(|_| "native application directory unavailable")?
        .file_type()
        .is_symlink()
    {
        return Err("native application directory cannot be a symlink");
    }
    // Use the canonical identity for security checks, but preserve the
    // original, absolute OS path for Python subprocess execution. On Windows
    // fs::canonicalize() produces a \\?\-prefixed extended-length path,
    // which the pinned Python/SQLite worker does not consistently accept.
    // The previously verified Python start adapter uses the ordinary path.
    let canonical_root =
        fs::canonicalize(root).map_err(|_| "native application root unavailable")?;
    let root = root.to_path_buf();
    let manifest_path = root.join("runtime-manifest.json");
    regular_file(&manifest_path)?;
    let file_size = fs::metadata(&manifest_path)
        .map_err(|_| "native application manifest unavailable")?
        .len();
    if file_size == 0 || file_size > MAX_MANIFEST_BYTES {
        return Err("native application manifest length invalid");
    }
    let manifest: Value = serde_json::from_slice(
        &fs::read(manifest_path).map_err(|_| "cannot inspect native manifest")?,
    )
    .map_err(|_| "invalid native application manifest")?;
    if manifest.get("schemaVersion").and_then(Value::as_u64) != Some(1)
        || manifest
            .get("nativeApplicationIncluded")
            .and_then(Value::as_bool)
            != Some(true)
    {
        return Err("not a verified native Minglefield application package");
    }
    let executable_name = if cfg!(windows) {
        "Minglefield.exe"
    } else {
        "Minglefield"
    };
    if manifest_string(&manifest, "nativeApplicationExecutable")? != executable_name {
        return Err("native Minglefield executable name mismatch");
    }
    if fs::canonicalize(executable).map_err(|_| "native Minglefield path unavailable")?
        != canonical_root.join(executable_name)
    {
        return Err("native executable not located in its managed Alpha root");
    }
    let digest = manifest_string(&manifest, "managedFileInventorySha256")?;
    if digest.len() != 64
        || !digest
            .bytes()
            .all(|x| x.is_ascii_hexdigit() && !x.is_ascii_uppercase())
    {
        return Err("invalid native inventory digest");
    }
    // Inventory symlink containment comparisons also use canonical identities.
    verify_installed_application(&canonical_root, digest)
        .map_err(|_| "native Minglefield package inventory verification failed")?;
    let python_name = if cfg!(windows) {
        "runtime/python/python.exe"
    } else {
        "runtime/python/bin/python3.11"
    };
    if manifest_string(&manifest, "pythonExecutable")? != python_name
        || manifest_string(&manifest, "applicationEntrypoint")?
            != "application/server/installed_alpha_launch.py"
    {
        return Err("native application runtime path does not match platform");
    }
    let python = root.join(python_name);
    let worker = root.join("application/server/installed_alpha_launch.py");
    regular_file(&python)?;
    regular_file(&worker)?;
    Ok(InstalledApp {
        root,
        python,
        worker,
        managed_files: manifest
            .get("managedFileCount")
            .and_then(Value::as_u64)
            .unwrap_or(0) as usize,
    })
}

fn interactive_dialogs_allowed(opts: &LaunchOptions) -> bool {
    // Never make CI, scripts or private-stdin automation unexpectedly wait
    // for a graphical interaction. Ordinary double-click startup is allowed.
    !opts.no_dialog && !opts.verify_only && !opts.probe_exit && !opts.no_browser && !opts.stdin
}

/// Fill *missing* owner inputs only; a config, argument, file, environment
/// secret or private stdin frame never triggers an extra password prompt.
/// Injection of a dialog callback makes this rule testable without GUI events.
fn complete_interactive_sources(
    db: &mut DatabaseOptions,
    allow: bool,
    environment_key_selected: bool,
    mut ask: impl FnMut(DialogKind) -> Result<String, &'static str>,
) -> Result<(), &'static str> {
    if !allow {
        return Ok(());
    }
    if db.database_path.is_none() {
        db.database_path = Some(ask(DialogKind::DatabaseFile)?);
    }
    let key_selected = db.password.literal.is_some()
        || db.password.file.is_some()
        || db.new_password.literal.is_some()
        || db.new_password.file.is_some()
        || environment_key_selected;
    if !key_selected {
        db.password.literal = Some(ask(DialogKind::CipherPassword)?);
    }
    Ok(())
}

fn resolve_key(opts: &LaunchOptions, root: &Path) -> Result<(PathBuf, String), &'static str> {
    let automatic = root.join("minglefield.conf");
    let config_path = opts.config.as_ref().or(if automatic.exists() {
        Some(&automatic)
    } else {
        None
    });
    let mut db = if let Some(path) = config_path {
        regular_file(path)?;
        let config = fs::read_to_string(path).map_err(|_| "cannot read administrator config")?;
        InstallerConfigV3::parse(&config)
            .map_err(|_| "invalid administrator version 3 config")?
            .database
    } else {
        DatabaseOptions::default()
    };
    db.override_with(opts.database.clone());
    complete_interactive_sources(
        &mut db,
        interactive_dialogs_allowed(opts),
        env::var_os("MINGLEFIELD_DB_PASSWORD").is_some()
            || env::var_os("MINGLEFIELD_NEW_DB_PASSWORD").is_some(),
        native_start_dialog::ask,
    )?;
    let database = db
        .database_path
        .as_deref()
        .ok_or("selected existing SQLCipher database path required")?;
    let path = Path::new(database);
    if !path.is_absolute() {
        return Err("selected database must have an absolute path");
    }
    regular_file(path)?;
    let (header, size) = {
        let mut file = fs::File::open(path).map_err(|_| "cannot open selected SQLCipher file")?;
        let mut buf = [0_u8; 16];
        file.read_exact(&mut buf)
            .map_err(|_| "selected SQLCipher database is incomplete")?;
        (
            buf,
            fs::metadata(path)
                .map_err(|_| "cannot inspect SQLCipher file")?
                .len(),
        )
    };
    if size < 16 || &header == b"SQLite format 3\0" {
        return Err("selected database must be encrypted SQLCipher");
    }

    let frame = if opts.stdin {
        Some(
            parse_stdin_secrets(std::io::stdin().lock())
                .map_err(|_| "invalid bounded native secrets stdin")?,
        )
    } else {
        None
    };
    if frame.as_ref().is_some_and(|f| f.login_password.is_some()) {
        return Err("native application launch must not accept account login password");
    }
    if frame
        .as_ref()
        .is_some_and(|f| f.db_password.is_some() && f.new_db_password.is_some())
    {
        return Err("conflicting native application database key channels");
    }
    let chosen = if db.password.literal.is_some()
        || db.password.file.is_some()
        || frame.as_ref().is_some_and(|f| f.db_password.is_some())
        || env::var_os("MINGLEFIELD_DB_PASSWORD").is_some()
    {
        db.password.resolve(
            env::var("MINGLEFIELD_DB_PASSWORD").ok(),
            frame.as_ref().and_then(|f| f.db_password.as_deref()),
        )
    } else {
        db.new_password.resolve(
            env::var("MINGLEFIELD_NEW_DB_PASSWORD").ok(),
            frame.as_ref().and_then(|f| f.new_db_password.as_deref()),
        )
    };
    let secret = chosen
        .map_err(|_| "conflicting or invalid native SQLCipher password source")?
        .ok_or("native SQLCipher password required")?;
    let verified = verify_encrypted_database(path, &secret)
        .map_err(|_| "native SQLCipher database unlock/integrity rejected")?;
    if !verified.alpha_users_table_present {
        return Err("Alpha account login has not yet been initialized");
    }
    // Keep the canonical identity check, but pass the operator's original
    // absolute path to the embedded Python worker. This is the same path
    // spelling accepted by the independent CI reference launcher; otherwise
    // Windows may receive \\?\-prefixed database filenames through JSON.
    fs::canonicalize(path).map_err(|_| "cannot identify selected database")?;
    Ok((path.to_path_buf(), secret))
}

fn private_start_frame(database: &Path, key: &str) -> Result<Vec<u8>, &'static str> {
    let data = serde_json::to_vec(&json!({
        "version": 1,
        "databasePath": database,
        "sqlcipherKey": key,
        "port": 0
    }))
    .map_err(|_| "cannot encode private Alpha startup frame")?;
    if data.is_empty() || data.len() > MAX_FRAME {
        return Err("private Alpha startup frame length invalid");
    }
    Ok(data)
}

fn parse_readiness(frame: &[u8]) -> Result<u16, &'static str> {
    let response: Value =
        serde_json::from_slice(frame).map_err(|_| "invalid native Alpha readiness JSON")?;
    let value = response
        .as_object()
        .ok_or("invalid native Alpha readiness structure")?;
    if value.len() != 6
        || value.get("version").and_then(Value::as_u64) != Some(1)
        || value.get("status").and_then(Value::as_str) != Some("ready")
        || value.get("bind").and_then(Value::as_str) != Some("127.0.0.1")
        || value.get("encryptedDatabase").and_then(Value::as_bool) != Some(true)
        || value
            .get("hostClaimBootstrapEnabled")
            .and_then(Value::as_bool)
            != Some(false)
    {
        return Err("native Alpha readiness violated local-only security contract");
    }
    let port = value
        .get("port")
        .and_then(Value::as_u64)
        .ok_or("native Alpha readiness has no port")?;
    if !(1..=65535).contains(&port) {
        return Err("native Alpha readiness port is invalid");
    }
    Ok(port as u16)
}

fn start_worker(app: &InstalledApp, frame: &[u8]) -> Result<(Child, u16), &'static str> {
    let mut command = Command::new(&app.python);
    command
        .arg("-I")
        .arg("-B")
        .arg(&app.worker)
        .current_dir(app.root.join("application/server"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    // Match the previously CI-verified Python start adapter on Windows.
    // CREATE_NO_WINDOW is deliberately not applied here: it changes the
    // subprocess launch environment without being needed for a console
    // binary, and Windows failed to return the private readiness frame
    // with that flag. A later native GUI subsystem owns window suppression.
    let mut child = command
        .spawn()
        .map_err(|_| "cannot start bundled Alpha runtime")?;
    let result = (|| {
        child
            .stdin
            .take()
            .ok_or("native private stdin pipe unavailable")?
            .write_all(frame)
            .map_err(|_| "cannot deliver private Alpha startup frame")?;
        let mut output = child
            .stdout
            .take()
            .ok_or("native Alpha readiness pipe unavailable")?;
        let (sender, receiver) = mpsc::sync_channel(1);
        std::thread::spawn(move || {
            let mut buffer = Vec::with_capacity(256);
            for _ in 0..=MAX_FRAME {
                let mut byte = [0_u8; 1];
                if output.read_exact(&mut byte).is_err() {
                    break;
                }
                buffer.push(byte[0]);
                if byte[0] == b'\n' {
                    break;
                }
            }
            let _ = sender.send(buffer);
        });
        let response = receiver
            .recv_timeout(STARTUP_TIMEOUT)
            .map_err(|_| "native Alpha startup timed out")?;
        if response.is_empty() {
            return Err("native Alpha worker closed stdout before readiness");
        }
        if response.len() > MAX_FRAME {
            return Err("native Alpha readiness exceeds bounded length");
        }
        if !response.ends_with(b"\n") {
            return Err("native Alpha readiness missing line terminator");
        }
        parse_readiness(&response)
    })();
    match result {
        Ok(port) => Ok((child, port)),
        Err(error) => {
            let _ = child.kill();
            let _ = child.wait();
            Err(error)
        }
    }
}

fn probe_loopback(port: u16) -> Result<(), &'static str> {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let mut stream = TcpStream::connect_timeout(&address, Duration::from_secs(8))
        .map_err(|_| "native local Alpha gateway did not accept connections")?;
    stream
        .set_read_timeout(Some(Duration::from_secs(8)))
        .map_err(|_| "cannot set native Alpha read timeout")?;
    stream
        .write_all(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .map_err(|_| "cannot probe native local Alpha gateway")?;
    let mut first = [0_u8; 64];
    let count = stream
        .read(&mut first)
        .map_err(|_| "no response from native local Alpha gateway")?;
    if count < 12 || !first[..count].starts_with(b"HTTP/1.") {
        return Err("invalid native local Alpha HTTP response");
    }
    Ok(())
}

fn open_browser(port: u16) {
    let url = format!("http://127.0.0.1:{port}/");
    #[cfg(windows)]
    let _ = Command::new("explorer.exe").arg(&url).spawn();
    #[cfg(target_os = "macos")]
    let _ = Command::new("/usr/bin/open").arg(&url).spawn();
    #[cfg(all(unix, not(target_os = "macos")))]
    let _ = Command::new("xdg-open").arg(&url).spawn();
}

fn run(args: impl IntoIterator<Item = String>) -> Result<(), &'static str> {
    let args: Vec<String> = args.into_iter().collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        println!("Minglefield native Alpha application");
        println!("Usage: Minglefield --database ABSOLUTE_PATH [--db-password VALUE]");
        println!("  [--db-password-file PATH] [--config CONFIG_V3] [--secrets-stdin]");
        println!("  [--verify-only] [--no-browser] [--probe-exit] [--no-dialog]");
        println!("When needed, normal desktop launch opens the OS file/password dialogs.");
        println!("Supports MINGLEFIELD_DB_PASSWORD and administrator-authored V3 settings.");
        println!("No Setup Manager or system Python is needed to launch installed Alpha.");
        return Ok(());
    }
    let opts = parse_args(args)?;
    let executable = env::current_exe().map_err(|_| "native application executable unavailable")?;
    let app = installed_app(&executable)?;
    let (database, secret) = resolve_key(&opts, &app.root)?;
    if opts.verify_only {
        println!(
            "{}",
            json!({
                "status": "native_minglefield_prerequisites_verified",
                "databaseEncrypted": true,
                "managedEntries": app.managed_files,
                "hostProvisioningEnabled": false
            })
        );
        return Ok(());
    }
    let frame = private_start_frame(&database, &secret)?;
    let (mut child, port) = start_worker(&app, &frame)?;
    let report = json!({
        "status": if opts.probe_exit {
            "native_minglefield_startup_verified"
        } else {
            "native_minglefield_ready"
        },
        "bind": "127.0.0.1",
        "port": port,
        "encryptedDatabase": true,
        "hostClaimBootstrapEnabled": false,
        "hostProvisioningEnabled": false
    });
    if opts.probe_exit {
        let result = probe_loopback(port);
        let _ = child.kill();
        let _ = child.wait();
        result?;
        println!("{report}");
        return Ok(());
    }
    println!("{report}");
    if !opts.no_browser {
        open_browser(port);
    }
    child
        .wait()
        .map_err(|_| "native Minglefield application terminated unexpectedly")?;
    Ok(())
}

fn main() -> std::process::ExitCode {
    let result = std::panic::catch_unwind(|| run(env::args().skip(1)));
    match result {
        Ok(Ok(())) => std::process::ExitCode::SUCCESS,
        Ok(Err(reason)) => {
            // Every error is a static developer-authored string. Never echo
            // raw environment, argv, config, DB paths or SQLCipher keys.
            eprintln!("minglefield_native_launch_rejected: {reason}");
            std::process::ExitCode::from(2)
        }
        Err(_) => {
            eprintln!("minglefield_native_launch_rejected: internal_panic");
            std::process::ExitCode::from(2)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_plaintext_db_options_and_ambiguous_native_flags() {
        assert!(parse_args(["--db-password".to_owned(), "value".to_owned()]).is_ok());
        assert!(parse_args(["--db-password=--DashKey123!".to_owned()]).is_ok());
        assert!(parse_args(["--db-password=x".to_owned(), "--db-password=y".to_owned(),]).is_err());
        assert!(parse_args(["--probe-exit".to_owned(), "--verify-only".to_owned()]).is_err());
    }

    #[test]
    fn verifies_bounded_private_launch_frames_without_logging_credentials() {
        let frame =
            private_start_frame(Path::new("/test/alpha.db"), "NotPrintedSecret123!").unwrap();
        assert!(frame.len() < MAX_FRAME);
        assert!(parse_readiness(
            br#"{"version":1,"status":"ready","bind":"127.0.0.1","port":32111,"encryptedDatabase":true,"hostClaimBootstrapEnabled":false}"#
        )
        .is_ok());
        assert!(parse_readiness(
            br#"{"version":1,"status":"ready","bind":"0.0.0.0","port":32111,"encryptedDatabase":true,"hostClaimBootstrapEnabled":false}"#
        )
        .is_err());
        assert!(parse_readiness(
            br#"{"version":1,"status":"ready","bind":"127.0.0.1","port":32111,"encryptedDatabase":true,"hostClaimBootstrapEnabled":true}"#
        )
        .is_err());
    }

    #[test]
    fn graphical_prompts_are_never_used_during_scripted_or_ci_launch() {
        let normal = parse_args(Vec::<String>::new()).unwrap();
        assert!(interactive_dialogs_allowed(&normal));
        for flag in [
            "--verify-only",
            "--probe-exit",
            "--no-browser",
            "--secrets-stdin",
            "--no-dialog",
        ] {
            let options = parse_args([flag.to_owned()]).unwrap();
            assert!(!interactive_dialogs_allowed(&options));
        }
    }

    #[test]
    fn interactive_inputs_only_fill_missing_fields_and_preserve_existing_secrets() {
        let mut db = DatabaseOptions::default();
        let mut asked = Vec::new();
        complete_interactive_sources(&mut db, true, false, |kind| {
            asked.push(kind);
            Ok(match kind {
                DialogKind::DatabaseFile => "/private/selected.db".to_owned(),
                DialogKind::CipherPassword => "OwnerChosenPass9!".to_owned(),
            })
        })
        .unwrap();
        assert_eq!(
            asked,
            vec![DialogKind::DatabaseFile, DialogKind::CipherPassword]
        );
        assert_eq!(db.database_path.as_deref(), Some("/private/selected.db"));
        assert_eq!(db.password.literal.as_deref(), Some("OwnerChosenPass9!"));
        asked.clear();
        complete_interactive_sources(&mut db, true, false, |kind| {
            asked.push(kind);
            Err("unexpected GUI request")
        })
        .unwrap();
        assert!(asked.is_empty());
    }

    #[test]
    fn config_file_and_noninteractive_credentials_never_force_password_dialog() {
        let mut db = DatabaseOptions {
            database_path: Some("/private/from-config.db".to_owned()),
            password: minglefield_installer_core::config_v3::SecretInput {
                file: Some("/private/credential.txt".to_owned()),
                ..Default::default()
            },
            ..Default::default()
        };
        complete_interactive_sources(&mut db, true, false, |_| Err("unexpected GUI request"))
            .unwrap();
        assert!(db.password.literal.is_none());
        let mut with_env_key = DatabaseOptions::default();
        let mut requested = Vec::new();
        complete_interactive_sources(&mut with_env_key, true, true, |kind| {
            requested.push(kind);
            Ok("/private/selected.db".to_owned())
        })
        .unwrap();
        assert_eq!(requested, vec![DialogKind::DatabaseFile]);
        assert!(with_env_key.password.literal.is_none());
        let mut headless = DatabaseOptions::default();
        complete_interactive_sources(&mut headless, false, false, |_| {
            Err("unexpected GUI request")
        })
        .unwrap();
        assert!(headless.database_path.is_none());
        assert!(headless.password.literal.is_none());
    }

    #[test]
    fn refuses_unmanaged_native_application_before_reading_any_secret() {
        assert!(installed_app(Path::new("/missing/minglefield-app")).is_err());
    }
}
