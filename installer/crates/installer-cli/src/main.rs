//! Read-only bootstrap CLI. Never writes application files or claims a Host.
use minglefield_installer_core::config::InstallerConfig;
use minglefield_installer_core::Mode;
use std::env;
use std::process::ExitCode;

fn run(args: impl IntoIterator<Item = String>) -> Result<(), (u8, String)> {
    let mut args = args.into_iter();
    let mut silent = false;
    let mut defaults = false;
    let mut install_dir: Option<String> = None;
    let mut config_file: Option<String> = None;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--silent" => silent = true,
            "--defaults" => defaults = true,
            "--install-dir" => {
                install_dir = Some(
                    args.next()
                        .ok_or((2, "--install-dir requires a value".to_string()))?,
                );
            }
            "--config" => {
                config_file = Some(
                    args.next()
                        .ok_or((2, "--config requires a file path".to_string()))?,
                );
            }
            "--help" | "-h" => {
                println!("Usage: minglefield-installer-cli --silent (--defaults | --config FILE) [--install-dir ABSOLUTE_PATH]");
                println!("Config: UTF-8 key=value, version=1, optional install_dir/data_dir.");
                println!("This prototype validates and prints a plan; nothing is installed.");
                return Ok(());
            }
            _ => return Err((2, format!("unsupported argument: {arg}"))),
        }
    }
    if !silent || (defaults == config_file.is_some()) {
        return Err((
            2,
            "require --silent and exactly one of --defaults or --config FILE".to_string(),
        ));
    }
    let mut config = if let Some(file) = config_file {
        let text = std::fs::read_to_string(&file)
            .map_err(|err| (3, format!("cannot read config: {err}")))?;
        InstallerConfig::parse(&text).map_err(|err| (3, format!("invalid config: {err}")))?
    } else {
        InstallerConfig::defaults()
            .map_err(|err| (3, format!("cannot determine defaults: {err:?}")))?
    };
    if let Some(path) = install_dir {
        config.install_dir = path;
    }
    let plan = config
        .preview(Mode::Silent)
        .map_err(|err| (3, format!("invalid installation plan: {err:?}")))?;
    println!("PLAN ONLY (no files changed, no Host claimed): {plan:?}");
    Ok(())
}

fn main() -> ExitCode {
    match run(env::args().skip(1)) {
        Ok(()) => ExitCode::SUCCESS,
        Err((code, message)) => {
            eprintln!("{message}");
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
}
