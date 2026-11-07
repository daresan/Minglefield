//! Shared native Minglefield startup probe for installer CLI and Tauri.
//! This verification does not create Host authority, store secrets, or start
//! a persistent service. Only inventory-bound native packages may be probed.
use crate::managed_alpha_install::verify_installed_application;
use serde_json::{json, Value};
use std::fs;
use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};
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
pub fn ensure_native_starter(
    root: &Path,
    pinned_inventory: &str,
) -> Result<(), &'static str> {
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
    if report.get("status").and_then(Value::as_str)
        != Some("native_minglefield_startup_verified")
        || report.get("encryptedDatabase").and_then(Value::as_bool) != Some(true)
        || report.get("hostProvisioningEnabled").and_then(Value::as_bool) != Some(false)
        || report.get("hostClaimBootstrapEnabled").and_then(Value::as_bool) != Some(false)
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
        stdin.flush().map_err(|_| "cannot flush private key frame")?;
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

#[cfg(test)]
mod tests {
    use super::*;

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
