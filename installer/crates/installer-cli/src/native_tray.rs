//! Windows notification-area lifecycle for the independent Minglefield app.
//! A fixed OS WinForms tray surface belongs to the native Minglefield process,
//! NOT to the Setup Manager, which can exit immediately after installation.
//! No credentials, tokens, selected paths or untrusted scripts are interpolated
//! into the PowerShell source. Only fixed numeric process IDs and the verified
//! Minglefield executable path pass as child environment variables.
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::time::Duration;

const TRAY_SCRIPT: &str = r#"
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$nativeId = [int]::Parse($env:MINGLEFIELD_TRAY_NATIVE_PID)
$workerId = [int]::Parse($env:MINGLEFIELD_TRAY_WORKER_PID)
$port = [int]::Parse($env:MINGLEFIELD_TRAY_PORT)
$executable = $env:MINGLEFIELD_TRAY_NATIVE_EXE
$expectedWorker = Join-Path (Split-Path -Parent $executable) 'runtime\python\python.exe'
$context = New-Object System.Windows.Forms.ApplicationContext
$icon = New-Object System.Windows.Forms.NotifyIcon
try {
    $icon.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon($executable)
} catch {
    $icon.Icon = [System.Drawing.SystemIcons]::Application
}
if ($null -eq $icon.Icon) {
    $icon.Icon = [System.Drawing.SystemIcons]::Application
}
$icon.Text = 'Minglefield - Local Host'
$icon.Visible = $true
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$open = $menu.Items.Add('Minglefield im Browser öffnen')
$quit = $menu.Items.Add('Minglefield beenden')
$open.Add_Click({
    Start-Process ("http://127.0.0.1:" + $port + "/")
})
$icon.Add_DoubleClick({
    Start-Process ("http://127.0.0.1:" + $port + "/")
})
$quit.Add_Click({
    # The native app owns its embedded Python worker. /T terminates that
    # entire owned subtree and no other unrelated Minglefield or Python.
    $taskkill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
    if (Test-Path -LiteralPath $taskkill -PathType Leaf) {
        $icon.Visible = $false
        & $taskkill /PID $nativeId /T /F 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            $icon.Visible = $true
        }
    }
    if (-not $icon.Visible) { $context.ExitThread() }
})
$icon.ContextMenuStrip = $menu
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 1000
$timer.Add_Tick({
    $parent = Get-Process -Id $nativeId -ErrorAction SilentlyContinue
    $worker = Get-Process -Id $workerId -ErrorAction SilentlyContinue
    if ($null -eq $parent -or $null -eq $worker) {
        # If the native parent is killed unexpectedly, its embedded Python
        # process must not be left behind when the tray can still observe it.
        if ($null -eq $parent -and $null -ne $worker -and
            $worker.Path -eq $expectedWorker) {
            Stop-Process -Id $workerId -Force -ErrorAction SilentlyContinue
        }
        $icon.Visible = $false
        $timer.Stop()
        $context.ExitThread()
    }
})
$timer.Start()
[Console]::Out.WriteLine('minglefield_tray_ready')
[Console]::Out.Flush()
try {
    [System.Windows.Forms.Application]::Run($context)
} finally {
    $timer.Stop()
    $timer.Dispose()
    $icon.Visible = $false
    $icon.Dispose()
    $menu.Dispose()
    $context.Dispose()
}
"#;

fn powershell_executable() -> Result<PathBuf, &'static str> {
    let root = std::env::var_os("SystemRoot").ok_or("Windows system directory unavailable")?;
    let path = Path::new(&root)
        .join("System32")
        .join("WindowsPowerShell")
        .join("v1.0")
        .join("powershell.exe");
    if !path.is_file() {
        return Err("Windows PowerShell tray component unavailable");
    }
    Ok(path)
}

/// Called only after the native gateway has confirmed readiness. Normal
/// no-browser/probe CI launches never create an interactive tray.
pub fn start_tray(native_exe: &Path, worker_pid: u32, port: u16) -> Result<Child, &'static str> {
    use std::os::windows::process::CommandExt;
    let mut command = Command::new(powershell_executable()?);
    command
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-STA",
            "-WindowStyle",
            "Hidden",
            "-Command",
        ])
        .arg(TRAY_SCRIPT)
        .env(
            "MINGLEFIELD_TRAY_NATIVE_PID",
            std::process::id().to_string(),
        )
        .env("MINGLEFIELD_TRAY_WORKER_PID", worker_pid.to_string())
        .env("MINGLEFIELD_TRAY_PORT", port.to_string())
        .env("MINGLEFIELD_TRAY_NATIVE_EXE", native_exe)
        .env_remove("MINGLEFIELD_DB_PASSWORD")
        .env_remove("MINGLEFIELD_NEW_DB_PASSWORD")
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .creation_flags(0x0800_0000);
    let mut child = command
        .spawn()
        .map_err(|_| "cannot start Minglefield tray")?;
    let stdout = child
        .stdout
        .take()
        .ok_or("Minglefield tray pipe unavailable")?;
    let (sender, receiver) = mpsc::sync_channel(1);
    std::thread::spawn(move || {
        let mut line = String::new();
        let result = BufReader::new(stdout).read_line(&mut line);
        let _ = sender.send(result.ok().filter(|n| *n > 0).map(|_| line));
    });
    let ready = receiver
        .recv_timeout(Duration::from_secs(12))
        .ok()
        .flatten()
        .is_some_and(|line| line.trim() == "minglefield_tray_ready");
    if !ready
        || child
            .try_wait()
            .map_err(|_| "Minglefield tray exited")?
            .is_some()
    {
        let _ = child.kill();
        let _ = child.wait();
        return Err("Minglefield tray failed to become visible");
    }
    Ok(child)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(windows)]
    #[test]
    fn embedded_powershell_is_parseable_without_executing_installer_operations() {
        use std::io::Write;
        use std::process::{Command, Stdio};
        let code = concat!(
            "$src=[Console]::In.ReadToEnd();",
            "$tokens=$null;$issues=$null;",
            "[void][System.Management.Automation.Language.Parser]::ParseInput(",
            "$src,[ref]$tokens,[ref]$issues);",
            "if($issues.Count -gt 0){exit 1};exit 0"
        );
        let powershell = super::powershell_executable().unwrap();
        let mut parser = Command::new(powershell)
            .args(["-NoProfile", "-NonInteractive", "-Command", code])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .unwrap();
        parser
            .stdin
            .take()
            .unwrap()
            .write_all(super::TRAY_SCRIPT.as_bytes())
            .unwrap();
        assert!(parser.wait().unwrap().success());
    }

    #[test]
    fn tray_has_both_requested_actions_and_ties_worker_shutdown_to_native_pid() {
        assert!(TRAY_SCRIPT.contains("Minglefield im Browser öffnen"));
        assert!(TRAY_SCRIPT.contains("Minglefield beenden"));
        assert!(TRAY_SCRIPT.contains("/PID $nativeId /T /F"));
        assert!(TRAY_SCRIPT.contains("Stop-Process -Id $workerId"));
        assert!(!TRAY_SCRIPT.contains("sqlcipherKey"));
        assert!(!TRAY_SCRIPT.contains("db_password"));
    }
}
