//! Per-user Windows application registration for the INSTALLED Minglefield app.
//! The portable Tauri Setup Manager is not entered in Installed Apps.
//! No elevation, database changes, publisher claims or external installer.
use std::path::Path;

#[cfg(windows)]
const UNINSTALL_KEY: &str =
    r"HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Minglefield";

#[cfg(windows)]
const UNINSTALL_SCRIPT: &str = r#"
# Minglefield app removal: the installed app, never the portable Setup Manager.
# Only managed package files are removed. SQLCipher databases, backups,
# imported hosts, and unrelated user files are never deleted.
$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath(
    (Split-Path -Parent $MyInvocation.MyCommand.Path)).TrimEnd('\')
$exe = Join-Path $root 'Minglefield.exe'
$inventoryPath = Join-Path $root 'managed-file-inventory.json'
if (-not (Test-Path -LiteralPath $inventoryPath -PathType Leaf)) {
    throw 'Minglefield inventory missing; no files were removed.'
}
$manifest = Get-Content -LiteralPath $inventoryPath -Raw | ConvertFrom-Json
if ($manifest.schemaVersion -ne 1 -or $null -eq $manifest.files) {
    throw 'Invalid application file inventory; no files were removed.'
}
$files = @($manifest.files.PSObject.Properties.Name)
if ($files.Count -eq 0 -or $files.Count -gt 40000) {
    throw 'Unbounded application file inventory; no files were removed.'
}
$targets = New-Object System.Collections.Generic.List[string]
foreach ($relative in $files) {
    if ([string]::IsNullOrEmpty($relative) -or
        $relative.Contains('\') -or $relative.Contains(':') -or
        @($relative.Split('/')).Contains('..') -or
        @($relative.Split('/')).Contains('.')) {
        throw 'Unsafe application inventory path; no files were removed.'
    }
    $path = [System.IO.Path]::GetFullPath(
        (Join-Path $root ($relative.Replace('/', '\'))))
    if (-not $path.StartsWith($root + '\',
        [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Application inventory escapes installation; no files removed.'
    }
    $targets.Add($path)
}
# Stop only THIS installed Minglefield executable and its embedded Python tree.
$taskkill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
Get-Process -Name Minglefield -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $exe } |
    ForEach-Object {
        & $taskkill /PID $_.Id /T /F 2>$null | Out-Null
    }
Start-Sleep -Milliseconds 400
foreach ($file in $targets) {
    if (Test-Path -LiteralPath $file) {
        Remove-Item -LiteralPath $file -Force -ErrorAction Stop
    }
}
foreach ($name in @('runtime-manifest.json', 'managed-file-inventory.json')) {
    $item = Join-Path $root $name
    if (Test-Path -LiteralPath $item -PathType Leaf) {
        Remove-Item -LiteralPath $item -Force -ErrorAction Stop
    }
}
# Remove only empty directories, never user/foreign files or adjacent backups.
$folders = @(
    $targets | ForEach-Object { Split-Path -Parent $_ } |
    Sort-Object -Unique
) | Sort-Object -Property Length -Descending
foreach ($folder in $folders) {
    if ((Test-Path -LiteralPath $folder -PathType Container) -and
        $folder -ne $root -and
        @((Get-ChildItem -LiteralPath $folder -Force)).Count -eq 0) {
        Remove-Item -LiteralPath $folder -Force
    }
}
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Minglefield'
if (Test-Path -LiteralPath $key) {
    $registered = (Get-ItemProperty -LiteralPath $key).InstallLocation
    if ($registered -eq $root) {
        Remove-Item -LiteralPath $key -Force
    }
}
$self = $MyInvocation.MyCommand.Path
if (Test-Path -LiteralPath $self -PathType Leaf) {
    Remove-Item -LiteralPath $self -Force
}
if (@(Get-ChildItem -LiteralPath $root -Force).Count -eq 0) {
    Remove-Item -LiteralPath $root -Force
}
"#;

#[cfg(windows)]
fn system_executable(name: &str) -> Result<std::path::PathBuf, String> {
    let root = std::env::var_os("SystemRoot")
        .ok_or("Windows-Verzeichnis ist nicht verfügbar")?;
    let path = Path::new(&root).join("System32").join(name);
    if !path.is_file() {
        return Err("Windows-Anwendungsregistrierung ist nicht verfügbar".into());
    }
    Ok(path)
}

#[cfg(windows)]
fn add_value(key: &str, name: &str, kind: &str, value: &str) -> Result<(), String> {
    let status = std::process::Command::new(system_executable("reg.exe")?)
        .args(["add", key, "/v", name, "/t", kind, "/d", value, "/f"])
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map_err(|_| "Windows-App-Registrierung konnte nicht gestartet werden")?;
    if !status.success() {
        return Err("Windows-App-Registrierung wurde abgelehnt".into());
    }
    Ok(())
}

#[cfg(windows)]
pub fn register_installed_application(root: &Path) -> Result<(), String> {
    use std::fs;
    use std::io::Write;
    let app = root.join("Minglefield.exe");
    let metadata = fs::symlink_metadata(&app)
        .map_err(|_| "Die installierte Minglefield.exe fehlt")?;
    if !metadata.is_file() || metadata.file_type().is_symlink() {
        return Err("Installierter Minglefield-Starter ist ungültig".into());
    }
    let root = fs::canonicalize(root)
        .map_err(|_| "Installationsordner ist nicht erreichbar")?;
    let uninstall_file = root.join("MinglefieldUninstall.ps1");
    match fs::symlink_metadata(&uninstall_file) {
        Ok(meta) => {
            if !meta.is_file() || meta.file_type().is_symlink()
                || fs::read(&uninstall_file).map_err(|_| "Uninstaller unlesbar")?
                    != UNINSTALL_SCRIPT.as_bytes()
            {
                return Err("Vorhandene fremde Deinstallationsdatei bleibt unverändert".into());
            }
        }
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            let mut file = fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&uninstall_file)
                .map_err(|_| "Minglefield-Deinstaller kann nicht erstellt werden")?;
            file.write_all(UNINSTALL_SCRIPT.as_bytes())
                .and_then(|_| file.sync_all())
                .map_err(|_| "Minglefield-Deinstaller kann nicht gespeichert werden")?;
        }
        Err(_) => return Err("Minglefield-Deinstaller kann nicht geprüft werden".into()),
    }
    let powershell = system_executable("WindowsPowerShell\\v1.0\\powershell.exe")?;
    let uninstall = format!(
        "\"{}\" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"{}\"",
        powershell.display(),
        uninstall_file.display()
    );
    let location = root.to_string_lossy();
    add_value(UNINSTALL_KEY, "DisplayName", "REG_SZ", "Minglefield")?;
    add_value(UNINSTALL_KEY, "DisplayVersion", "REG_SZ", "0.1.0 Alpha")?;
    add_value(UNINSTALL_KEY, "Publisher", "REG_SZ", "Minglefield")?;
    add_value(UNINSTALL_KEY, "InstallLocation", "REG_SZ", &location)?;
    add_value(
        UNINSTALL_KEY, "DisplayIcon", "REG_SZ",
        &app.to_string_lossy(),
    )?;
    add_value(UNINSTALL_KEY, "NoModify", "REG_DWORD", "1")?;
    add_value(UNINSTALL_KEY, "NoRepair", "REG_DWORD", "1")?;
    // Last: do not advertise a complete uninstall command until all the
    // other registry information and the actual removal script are present.
    add_value(UNINSTALL_KEY, "UninstallString", "REG_SZ", &uninstall)?;
    Ok(())
}

#[cfg(not(windows))]
pub fn register_installed_application(_root: &Path) -> Result<(), String> {
    Ok(())
}

#[cfg(test)]
mod tests {
    #[cfg(windows)]
    #[test]
    fn script_is_bound_to_the_managed_application_and_preserves_user_data() {
        use super::UNINSTALL_SCRIPT;
        assert!(UNINSTALL_SCRIPT.contains("managed-file-inventory.json"));
        assert!(UNINSTALL_SCRIPT.contains("Get-Process -Name Minglefield"));
        assert!(UNINSTALL_SCRIPT.contains("/PID $_.Id /T /F"));
        assert!(!UNINSTALL_SCRIPT.contains("Remove-Item -Recurse"));
        assert!(!UNINSTALL_SCRIPT.contains("LOCALAPPDATA"));
    }
}
