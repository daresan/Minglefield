//! Native OS-owned file selection and masked SQLCipher password dialog.
//! This is only the user-facing startup *input* adapter: never provisions
//! a database, Host, account or launch server, and never stores a password.
//! Commands/scripts are compile-time fixed and never contain owner input.
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};

static STARTUP_DIALOG_OPENED: AtomicBool = AtomicBool::new(false);

pub fn was_opened() -> bool {
    STARTUP_DIALOG_OPENED.load(Ordering::Relaxed)
}

const MAX_DIALOG_REPLY: usize = 8192;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DialogKind {
    DatabaseFile,
    CipherPassword,
}

#[cfg(windows)]
const WINDOWS_FILE_SCRIPT: &str = r#"
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Title = 'Select existing Minglefield SQLCipher database'
$d.Filter = 'Databases (*.db;*.sqlite;*.sqlite3)|*.db;*.sqlite;*.sqlite3|All files (*.*)|*.*'
$d.CheckFileExists = $true
$d.Multiselect = $false
if ($d.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 2 }
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::Out.WriteLine($d.FileName)
"#;

#[cfg(windows)]
const WINDOWS_PASSWORD_SCRIPT: &str = r#"
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object System.Windows.Forms.Form
$f.Text = 'Minglefield - Unlock encrypted database'
$f.Width = 435
$f.Height = 180
$f.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$f.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$f.MaximizeBox = $false
$f.MinimizeBox = $false
$f.TopMost = $true
$l = New-Object System.Windows.Forms.Label
$l.Text = 'SQLCipher database password:'
$l.Left = 16
$l.Top = 17
$l.Width = 380
$f.Controls.Add($l)
$t = New-Object System.Windows.Forms.TextBox
$t.Left = 16
$t.Top = 47
$t.Width = 385
$t.UseSystemPasswordChar = $true
$f.Controls.Add($t)
$o = New-Object System.Windows.Forms.Button
$o.Text = 'Unlock'
$o.Left = 220
$o.Top = 85
$o.Width = 85
$o.DialogResult = [System.Windows.Forms.DialogResult]::OK
$f.Controls.Add($o)
$c = New-Object System.Windows.Forms.Button
$c.Text = 'Cancel'
$c.Left = 316
$c.Top = 85
$c.Width = 85
$c.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$f.Controls.Add($c)
$f.AcceptButton = $o
$f.CancelButton = $c
$f.Add_Shown({ $t.Focus() })
if ($f.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 2 }
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::Out.WriteLine($t.Text)
$f.Dispose()
"#;

#[cfg(target_os = "macos")]
const MAC_FILE_SCRIPT: &str =
    r#"POSIX path of (choose file with prompt "Select existing Minglefield SQLCipher database")"#;

#[cfg(target_os = "macos")]
const MAC_PASSWORD_SCRIPT: &str = r#"text returned of (display dialog "SQLCipher database password" default answer "" with hidden answer buttons {"Cancel", "Unlock"} default button "Unlock")"#;

/// No operator input is ever interpolated into these program arguments.
/// The final secret is returned through the dialog process' private stdout.
fn dialog_command(kind: DialogKind) -> Result<Command, &'static str> {
    #[cfg(windows)]
    {
        let mut cmd = Command::new("powershell.exe");
        cmd.args(["-NoProfile", "-STA", "-NonInteractive", "-Command"]);
        cmd.arg(match kind {
            DialogKind::DatabaseFile => WINDOWS_FILE_SCRIPT,
            DialogKind::CipherPassword => WINDOWS_PASSWORD_SCRIPT,
        });
        Ok(cmd)
    }
    #[cfg(target_os = "macos")]
    {
        let mut cmd = Command::new("/usr/bin/osascript");
        cmd.args(["-e"]);
        cmd.arg(match kind {
            DialogKind::DatabaseFile => MAC_FILE_SCRIPT,
            DialogKind::CipherPassword => MAC_PASSWORD_SCRIPT,
        });
        Ok(cmd)
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        // Use known OS locations, never execute a PATH-shadowed replacement
        // for a graphical password dialog. Optional desktop helpers are
        // not auto-installed or treated as an Alpha runtime dependency.
        let dialog_path = |name: &str| {
            ["/usr/bin", "/bin", "/usr/local/bin"]
                .iter()
                .map(|dir| std::path::Path::new(dir).join(name))
                .find(|path| path.is_file())
        };
        if let Some(path) = dialog_path("zenity") {
            let mut cmd = Command::new(path);
            match kind {
                DialogKind::DatabaseFile => {
                    cmd.args([
                        "--file-selection",
                        "--title=Select existing Minglefield SQLCipher database",
                    ]);
                }
                DialogKind::CipherPassword => {
                    cmd.args(["--password", "--title=Minglefield SQLCipher password"]);
                }
            }
            return Ok(cmd);
        }
        if let Some(path) = dialog_path("kdialog") {
            let mut cmd = Command::new(path);
            match kind {
                DialogKind::DatabaseFile => {
                    cmd.args(["--getopenfilename", ".", "*|Existing SQLCipher database"]);
                }
                DialogKind::CipherPassword => {
                    cmd.args(["--password", "SQLCipher database password"]);
                }
            }
            return Ok(cmd);
        }
        Err("no supported Linux desktop file/password dialog is available")
    }
    #[cfg(not(any(windows, unix)))]
    {
        let _ = kind;
        Err("native desktop startup dialogs unsupported on this OS")
    }
}

fn interpret_reply(kind: DialogKind, status_ok: bool, data: &[u8]) -> Result<String, &'static str> {
    if !status_ok {
        return Err("native Minglefield startup dialog cancelled or unavailable");
    }
    if data.len() > MAX_DIALOG_REPLY {
        return Err("native Minglefield startup dialog response too long");
    }
    let decoded =
        std::str::from_utf8(data).map_err(|_| "native Minglefield startup dialog is not UTF-8")?;
    // Dialog subprocesses conventionally append one line ending to stdout.
    // Do not trim other whitespace: spaces can be part of a password.
    let text = decoded
        .strip_suffix("\r\n")
        .or_else(|| decoded.strip_suffix('\n'))
        .unwrap_or(decoded);
    if text.is_empty() || text.as_bytes().contains(&0) {
        return Err("native Minglefield startup dialog returned no value");
    }
    if kind == DialogKind::CipherPassword && text.len() > 4096 {
        return Err("native Minglefield SQLCipher password too long");
    }
    if kind == DialogKind::DatabaseFile && !std::path::Path::new(text).is_absolute() {
        return Err("native Minglefield file dialog did not select an absolute path");
    }
    Ok(text.to_owned())
}

pub fn ask(kind: DialogKind) -> Result<String, &'static str> {
    let mut command = dialog_command(kind)?;
    STARTUP_DIALOG_OPENED.store(true, Ordering::Relaxed);
    command
        .stdin(Stdio::null())
        .stderr(Stdio::null())
        .stdout(Stdio::piped());
    let result = command
        .output()
        .map_err(|_| "native Minglefield startup dialog could not open")?;
    interpret_reply(kind, result.status.success(), &result.stdout)
}

/// Show a generic, non-sensitive message only after a *real* GUI unlock
/// attempt failed. Neither SQLCipher keys, paths, argv nor worker diagnostics
/// enter GUI command arguments. Scripts and headless operation never call it.
pub fn show_unlock_error() {
    const MESSAGE: &str =
        "Could not open the encrypted database. Check the selected file and SQLCipher password.";
    #[cfg(windows)]
    {
        let script = r#"
Add-Type -AssemblyName System.Windows.Forms
[void][System.Windows.Forms.MessageBox]::Show(
    'Could not open the encrypted database. Check the file and SQLCipher password.',
    'Minglefield', [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Warning)
"#;
        let _ = Command::new("powershell.exe")
            .args(["-NoProfile", "-STA", "-NonInteractive", "-Command", script])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    #[cfg(target_os = "macos")]
    {
        let _ = Command::new("/usr/bin/osascript")
            .args([
                "-e",
                r#"display alert "Minglefield" message "Could not open the encrypted database. Check the selected file and SQLCipher password.""#,
            ])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    #[cfg(all(unix, not(target_os = "macos")))]
    {
        let dialog_path = |name: &str| {
            ["/usr/bin", "/bin", "/usr/local/bin"]
                .iter()
                .map(|dir| std::path::Path::new(dir).join(name))
                .find(|path| path.is_file())
        };
        let mut command = if let Some(path) = dialog_path("zenity") {
            let mut dialog = Command::new(path);
            dialog.args(["--error", "--title=Minglefield"]);
            dialog.arg(format!("--text={MESSAGE}"));
            Some(dialog)
        } else if let Some(path) = dialog_path("kdialog") {
            let mut dialog = Command::new(path);
            dialog.args(["--error", MESSAGE, "--title", "Minglefield"]);
            Some(dialog)
        } else {
            None
        };
        if let Some(dialog) = command.as_mut() {
            let _ = dialog
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn masked_dialog_result_preserves_whitespace_and_never_discloses_text() {
        assert_eq!(
            interpret_reply(DialogKind::CipherPassword, true, b" leading secret ! \r\n").unwrap(),
            " leading secret ! "
        );
        assert!(interpret_reply(DialogKind::CipherPassword, false, b"secret").is_err());
        assert!(interpret_reply(DialogKind::CipherPassword, true, b"").is_err());
        assert!(interpret_reply(DialogKind::CipherPassword, true, b"\xff").is_err());
        assert!(interpret_reply(DialogKind::CipherPassword, true, &vec![b'x'; 4097]).is_err());
    }

    #[test]
    fn file_dialog_accepts_only_existing_form_absolute_path_to_validate_later() {
        let absolute = if cfg!(windows) {
            "C:\\\\private\\\\owner.sqlite3"
        } else {
            "/private/owner.sqlite3"
        };
        assert!(interpret_reply(DialogKind::DatabaseFile, true, absolute.as_bytes()).is_ok());
        assert!(interpret_reply(DialogKind::DatabaseFile, true, b"relative.db").is_err());
        assert!(interpret_reply(DialogKind::DatabaseFile, false, absolute.as_bytes()).is_err());
        assert!(interpret_reply(DialogKind::DatabaseFile, true, &[0]).is_err());
    }

    #[test]
    fn dialog_command_does_not_include_any_runtime_secret_or_db_path() {
        if let Ok(cmd) = dialog_command(DialogKind::CipherPassword) {
            let args = cmd
                .get_args()
                .map(|arg| arg.to_string_lossy().into_owned())
                .collect::<Vec<_>>();
            assert!(!args.iter().any(|x| x.contains("owner.sqlite3")));
            assert!(!args.iter().any(|x| x.contains("secret-name")));
        }
    }
}
