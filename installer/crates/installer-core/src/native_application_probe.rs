//! Shared native Minglefield startup probe for installer CLI and Tauri.
//! This verification does not create Host authority, store secrets, or start
//! a persistent service. Only inventory-bound native packages may be probed.
use crate::managed_alpha_install::verify_installed_application;
use serde_json::{json, Value};
use std::fs;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::Path;
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

const TIMEOUT: Duration = Duration::from_secs(90);
const MAX_REPORT: usize = 4096;

fn native_path(root: &Path) -> std::path::PathBuf {
    root.join(if cfg!(windows) {
        "Minglefield.exe"
    } else {
        "Minglefield"
    })
}

/// Validate the installed native starter and every managed package entry.
/// May be called *before* a current-session first-run permit is consumed.
pub fn ensure_native_starter(root: &Path, pinned_inventory: &str) -> Result<(), &'static str> {
    verify_installed_application(root, pinned_inventory)
        .map_err(|_| "installed native package inventory rejected")?;
    let metadata = fs::symlink_metadata(native_path(root))
        .map_err(|_| "native Minglefield starter unavailable")?;
    if metadata.file_type().is_symlink() || !metadata.is_file() {
        return Err("native Minglefield starter must be a regular file");
    }
    Ok(())
}

fn verify_response(stdout: &[u8]) -> Result<(), &'static str> {
    if stdout.is_empty() || stdout.len() > MAX_REPORT {
        return Err("native startup response size invalid");
    }
    let report: Value =
        serde_json::from_slice(stdout).map_err(|_| "invalid native readiness response")?;
    if report.get("status").and_then(Value::as_str) != Some("native_minglefield_startup_verified")
        || report.get("encryptedDatabase").and_then(Value::as_bool) != Some(true)
        || report
            .get("hostProvisioningEnabled")
            .and_then(Value::as_bool)
            != Some(false)
        || report
            .get("hostClaimBootstrapEnabled")
            .and_then(Value::as_bool)
            != Some(false)
        || report.get("bind").and_then(Value::as_str) != Some("127.0.0.1")
    {
        return Err("native application readiness contract rejected");
    }
    Ok(())
}

/// Probe the installed native application with the key delivered through the
/// existing private stdin JSON frame. Never forward the account login secret
/// or place the SQLCipher key on the child process command line.
pub fn probe_installed_application(
    root: &Path,
    database: &Path,
    cipher_key: &str,
    pinned_inventory: &str,
) -> Result<(), &'static str> {
    ensure_native_starter(root, pinned_inventory)?;
    let mut child = Command::new(native_path(root))
        .arg("--database")
        .arg(database)
        .arg("--secrets-stdin")
        .arg("--probe-exit")
        .arg("--no-browser")
        .arg("--no-dialog")
        .env_remove("MINGLEFIELD_DB_PASSWORD")
        .env_remove("MINGLEFIELD_NEW_DB_PASSWORD")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "cannot launch installed native application")?;
    let frame = json!({
        "db_password": cipher_key,
        "new_db_password": null,
        "login_password": null
    });
    let delivery = (|| -> Result<(), &'static str> {
        let mut stdin = child.stdin.take().ok_or("native stdin unavailable")?;
        serde_json::to_writer(&mut stdin, &frame)
            .map_err(|_| "cannot deliver native private key frame")?;
        stdin
            .flush()
            .map_err(|_| "cannot flush private key frame")?;
        Ok(())
    })();
    if let Err(reason) = delivery {
        let _ = child.kill();
        let _ = child.wait();
        return Err(reason);
    }
    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) if start.elapsed() < TIMEOUT => {
                thread::sleep(Duration::from_millis(100));
            }
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("native application readiness probe timed out");
            }
            Err(_) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("cannot observe native application completion");
            }
        }
    }
    let output = child
        .wait_with_output()
        .map_err(|_| "native application verification unavailable")?;
    if !output.status.success() {
        return Err("installed native application failed startup");
    }
    verify_response(&output.stdout)
}

/// A running app owns its native process and the embedded local Alpha worker.
/// The Setup Manager is NOT a runtime dependency; this receipt has no secrets.
#[derive(Debug, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NativeRunningReceipt {
    pub status: &'static str,
    pub bind: &'static str,
    pub port: u16,
    pub process_id: u32,
    pub encrypted_database: bool,
    pub host_provisioning_enabled: bool,
    pub host_claim_bootstrap_enabled: bool,
}

fn running_port(stdout: &[u8]) -> Result<u16, &'static str> {
    if stdout.is_empty() || stdout.len() > MAX_REPORT || !stdout.ends_with(b"\n") {
        return Err("native running startup response length invalid");
    }
    let report: Value =
        serde_json::from_slice(stdout).map_err(|_| "invalid native running readiness JSON")?;
    let fields = report
        .as_object()
        .ok_or("native running readiness must be a JSON object")?;
    if fields.len() != 6
        || fields.get("status").and_then(Value::as_str) != Some("native_minglefield_ready")
        || fields.get("bind").and_then(Value::as_str) != Some("127.0.0.1")
        || fields.get("encryptedDatabase").and_then(Value::as_bool) != Some(true)
        || fields
            .get("hostProvisioningEnabled")
            .and_then(Value::as_bool)
            != Some(false)
        || fields
            .get("hostClaimBootstrapEnabled")
            .and_then(Value::as_bool)
            != Some(false)
    {
        return Err("native running readiness rejected");
    }
    let port = fields
        .get("port")
        .and_then(Value::as_u64)
        .ok_or("native readiness has no port")?;
    u16::try_from(port)
        .ok()
        .filter(|port| *port > 0)
        .ok_or("native readiness port invalid")
}

fn check_running_loopback(port: u16) -> Result<(), &'static str> {
    let socket = SocketAddr::from(([127, 0, 0, 1], port));
    let mut conn = TcpStream::connect_timeout(&socket, Duration::from_secs(8))
        .map_err(|_| "native local application did not accept connections")?;
    conn.set_read_timeout(Some(Duration::from_secs(8)))
        .map_err(|_| "native local readiness timeout invalid")?;
    conn.write_all(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        .map_err(|_| "native local readiness request failed")?;
    let mut bytes = [0_u8; 64];
    let n = conn
        .read(&mut bytes)
        .map_err(|_| "native local readiness reply failed")?;
    if n < 12 || !bytes[..n].starts_with(b"HTTP/1.") {
        return Err("native local application response invalid");
    }
    Ok(())
}

/// Start the *existing* native application rather than the short probe.
/// This process remains running after the Setup Manager or CLI exits.
/// No account password, Host claim, or persistent SQLCipher secret is created.
pub fn start_installed_application(
    root: &Path,
    database: &Path,
    cipher_key: &str,
    pinned_inventory: &str,
    open_browser: bool,
) -> Result<NativeRunningReceipt, &'static str> {
    ensure_native_starter(root, pinned_inventory)?;
    let mut command = Command::new(native_path(root));
    command
        .arg("--database")
        .arg(database)
        .arg("--secrets-stdin")
        .arg("--no-dialog")
        .env_remove("MINGLEFIELD_DB_PASSWORD")
        .env_remove("MINGLEFIELD_NEW_DB_PASSWORD")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    if !open_browser {
        command.arg("--no-browser");
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW: never flash a console when launched by Tauri.
        command.creation_flags(0x0800_0000);
    }
    // A separate process group also permits exact clean-up in CI without
    // signalling the installer or unrelated user processes.
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    let mut child = command
        .spawn()
        .map_err(|_| "cannot start verified native Minglefield application")?;
    let pid = child.id();
    let startup = (|| -> Result<u16, &'static str> {
        let stdout = child
            .stdout
            .take()
            .ok_or("native readiness pipe unavailable")?;
        let (sender, receiver) = mpsc::sync_channel(1);
        std::thread::spawn(move || {
            let mut reader = stdout;
            let mut response = Vec::with_capacity(256);
            for _ in 0..=MAX_REPORT {
                let mut b = [0_u8; 1];
                if reader.read_exact(&mut b).is_err() {
                    break;
                }
                response.push(b[0]);
                if b[0] == b'\n' {
                    break;
                }
            }
            let _ = sender.send(response);
        });
        let frame = json!({
            "db_password": cipher_key,
            "new_db_password": null,
            "login_password": null
        });
        {
            let mut stdin = child
                .stdin
                .take()
                .ok_or("native private stdin unavailable")?;
            serde_json::to_writer(&mut stdin, &frame)
                .map_err(|_| "cannot deliver native database secret")?;
            stdin
                .flush()
                .map_err(|_| "cannot flush native database secret")?;
        }
        let reply = receiver
            .recv_timeout(TIMEOUT)
            .map_err(|_| "native application start timed out")?;
        let port = running_port(&reply)?;
        check_running_loopback(port)?;
        if child
            .try_wait()
            .map_err(|_| "native application process unavailable")?
            .is_some()
        {
            return Err("native application exited during startup");
        }
        Ok(port)
    })();
    match startup {
        Ok(port) => {
            // Reap on normal shutdown while the installer remains open. Rust
            // threads do not prevent process exit; the native app continues
            // independently when the Setup Manager closes.
            std::thread::spawn(move || {
                let _ = child.wait();
            });
            Ok(NativeRunningReceipt {
                status: "native_minglefield_running",
                bind: "127.0.0.1",
                port,
                process_id: pid,
                encrypted_database: true,
                host_provisioning_enabled: false,
                host_claim_bootstrap_enabled: false,
            })
        }
        Err(reason) => {
            let _ = child.kill();
            let _ = child.wait();
            Err(reason)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_forged_running_readiness() {
        let ok = json!({
            "status": "native_minglefield_ready", "bind": "127.0.0.1",
            "port": 34567, "encryptedDatabase": true,
            "hostProvisioningEnabled": false, "hostClaimBootstrapEnabled": false
        });
        assert_eq!(running_port(format!("{ok}\n").as_bytes()).unwrap(), 34567);
        for (name, value) in [
            ("status", json!("native_minglefield_startup_verified")),
            ("bind", json!("0.0.0.0")),
            ("port", json!(0)),
            ("port", json!(65536)),
            ("hostProvisioningEnabled", json!(true)),
            ("hostClaimBootstrapEnabled", json!(true)),
        ] {
            let mut bad = ok.clone();
            bad[name] = value;
            assert!(running_port(format!("{bad}\n").as_bytes()).is_err());
        }
        let mut bad = ok.clone();
        bad["extra"] = json!(true);
        assert!(running_port(format!("{bad}\n").as_bytes()).is_err());
        assert!(running_port(ok.to_string().as_bytes()).is_err());
    }

    #[test]
    fn accepts_only_encrypted_loopback_readiness_without_host_claim() {
        let valid = json!({
            "status": "native_minglefield_startup_verified",
            "bind": "127.0.0.1",
            "port": 45678,
            "encryptedDatabase": true,
            "hostProvisioningEnabled": false,
            "hostClaimBootstrapEnabled": false
        });
        assert!(verify_response(valid.to_string().as_bytes()).is_ok());
        for (field, value) in [
            ("status", json!("native_minglefield_ready")),
            ("bind", json!("0.0.0.0")),
            ("encryptedDatabase", json!(false)),
            ("hostProvisioningEnabled", json!(true)),
            ("hostClaimBootstrapEnabled", json!(true)),
        ] {
            let mut forged = valid.clone();
            forged[field] = value;
            assert!(verify_response(forged.to_string().as_bytes()).is_err());
        }
        assert!(verify_response(b"").is_err());
        assert!(verify_response(&vec![b'x'; MAX_REPORT + 1]).is_err());
    }
}
