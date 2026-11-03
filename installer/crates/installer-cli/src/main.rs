//! Read-only bootstrap CLI. Never writes application files or claims a Host.
use minglefield_installer_core::{default_destination, plan, InstallRequest, Mode};
use std::env;
use std::process::ExitCode;

fn main() -> ExitCode {
    let mut args = env::args().skip(1);
    let mut silent = false;
    let mut defaults = false;
    let mut install_dir: Option<String> = None;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--silent" => silent = true,
            "--defaults" => defaults = true,
            "--install-dir" => {
                install_dir = args.next();
                if install_dir.is_none() {
                    eprintln!("--install-dir requires a value");
                    return ExitCode::from(2);
                }
            }
            "--help" | "-h" => {
                println!("Usage: minglefield-installer-cli --silent --defaults [--install-dir ABSOLUTE_PATH]");
                println!("This initial prototype only validates and prints an installation plan.");
                return ExitCode::SUCCESS;
            }
            _ => {
                eprintln!("unsupported argument: {arg}");
                return ExitCode::from(2);
            }
        }
    }
    if !silent || !defaults {
        eprintln!(
            "prototype requires --silent --defaults; GUI and config loading are not implemented"
        );
        return ExitCode::from(2);
    }
    let destination = match install_dir {
        Some(path) => path,
        None => match default_destination() {
            Ok(path) => path,
            Err(error) => {
                eprintln!("cannot determine installation directory: {error}");
                return ExitCode::from(3);
            }
        },
    };
    let request = InstallRequest {
        mode: Mode::Silent,
        install_dir: destination,
        install_optional_conda: false,
        install_optional_comfyui: false,
        explicit_optional_consent: false,
    };
    match plan(&request) {
        Ok(p) => {
            println!("PLAN ONLY (no files changed, no Host claimed): {p:?}");
            ExitCode::SUCCESS
        }
        Err(err) => {
            eprintln!("invalid installation plan: {err:?}");
            ExitCode::from(3)
        }
    }
}
