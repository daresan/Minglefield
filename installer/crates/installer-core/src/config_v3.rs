//! Version 3 adds the administrator-controlled Bee-like DB input contract.
//! The existing v1/v2 plan and Tauri-facing configuration rules stay intact.
//! No secret is returned by Debug output or written into a generated plan.
use crate::config_v2::InstallerConfigV2;
use crate::{InstallPlan, Mode};
use serde::Deserialize;
use std::collections::HashSet;
use std::io::Read;

const MAX_SECRET_BYTES: usize = 4096;
const MAX_STDIN_BYTES: u64 = 16 * 1024;

#[derive(Clone, Default, PartialEq, Eq)]
pub struct SecretInput {
    pub literal: Option<String>,
    pub file: Option<String>,
}

impl SecretInput {
    /// Resolve one explicitly chosen source. Absence is not a secret value;
    /// multiple simultaneous sources are rejected without printing values.
    pub fn resolve(
        &self,
        environment: Option<String>,
        stdin: Option<&str>,
    ) -> Result<Option<String>, &'static str> {
        let count = usize::from(self.literal.is_some())
            + usize::from(self.file.is_some())
            + usize::from(environment.is_some())
            + usize::from(stdin.is_some());
        if count > 1 {
            return Err("conflicting password sources");
        }
        let value = if let Some(value) = &self.literal {
            Some(value.clone())
        } else if let Some(path) = &self.file {
            let mut file =
                std::fs::File::open(path).map_err(|_| "password file unavailable")?;
            let mut bytes = Vec::new();
            file.by_ref()
                .take((MAX_SECRET_BYTES + 3) as u64)
                .read_to_end(&mut bytes)
                .map_err(|_| "cannot read password file")?;
            // Text password files commonly end with one newline; no other
            // trimming is permitted because spaces may be part of a password.
            if bytes.ends_with(b"\r\n") {
                bytes.truncate(bytes.len() - 2);
            } else if bytes.ends_with(b"\n") {
                bytes.truncate(bytes.len() - 1);
            }
            Some(String::from_utf8(bytes).map_err(|_| "password file is not UTF-8")?)
        } else if let Some(value) = environment {
            Some(value)
        } else {
            stdin.map(str::to_owned)
        };
        if let Some(value) = &value {
            if value.is_empty()
                || value.len() > MAX_SECRET_BYTES
                || value.as_bytes().contains(&0)
            {
                return Err("password value has invalid length or bytes");
            }
        }
        Ok(value)
    }
}

#[derive(Clone, Default, PartialEq, Eq)]
pub struct DatabaseOptions {
    pub database_path: Option<String>,
    pub source_path: Option<String>,
    pub backup_path: Option<String>,
    pub password: SecretInput,
    pub new_password: SecretInput,
}

impl DatabaseOptions {
    /// Explicit CLI flags override the same configuration key, but separate
    /// simultaneously-selected password source types remain conflicting.
    pub fn override_with(&mut self, flags: DatabaseOptions) {
        if flags.database_path.is_some() {
            self.database_path = flags.database_path;
        }
        if flags.source_path.is_some() {
            self.source_path = flags.source_path;
        }
        if flags.backup_path.is_some() {
            self.backup_path = flags.backup_path;
        }
        if flags.password.literal.is_some() {
            self.password.literal = flags.password.literal;
        }
        if flags.password.file.is_some() {
            self.password.file = flags.password.file;
        }
        if flags.new_password.literal.is_some() {
            self.new_password.literal = flags.new_password.literal;
        }
        if flags.new_password.file.is_some() {
            self.new_password.file = flags.new_password.file;
        }
    }

    pub fn has_any(&self) -> bool {
        self.database_path.is_some()
            || self.source_path.is_some()
            || self.backup_path.is_some()
            || self.password.literal.is_some()
            || self.password.file.is_some()
            || self.new_password.literal.is_some()
            || self.new_password.file.is_some()
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StdinSecrets {
    pub db_password: Option<String>,
    pub new_db_password: Option<String>,
}

/// One bounded JSON frame; never use stdin unless --secrets-stdin was selected.
pub fn parse_stdin_secrets(mut reader: impl Read) -> Result<StdinSecrets, &'static str> {
    let mut bytes = Vec::new();
    reader
        .by_ref()
        .take(MAX_STDIN_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "cannot read secrets stdin")?;
    if bytes.is_empty() || bytes.len() as u64 > MAX_STDIN_BYTES {
        return Err("secrets stdin frame length invalid");
    }
    serde_json::from_slice(&bytes).map_err(|_| "invalid secrets stdin JSON frame")
}

/// V3 keeps V2 keys and adds the DB paths/secret input fields to the same
/// versioned config structure used by GUI previews and the headless CLI.
pub struct InstallerConfigV3 {
    pub base: InstallerConfigV2,
    pub database: DatabaseOptions,
}

impl InstallerConfigV3 {
    pub fn parse(text: &str) -> Result<Self, &'static str> {
        let mut base = Vec::new();
        let mut db = DatabaseOptions::default();
        let mut seen = HashSet::new();
        let mut has_version = false;
        for line in text.lines() {
            let trimmed = line.trim();
            if trimmed.is_empty() || trimmed.starts_with('#') {
                continue;
            }
            let (key, value) = trimmed
                .split_once('=')
                .ok_or("invalid configuration line")?;
            let key = key.trim();
            let value = value.trim();
            if !seen.insert(key) {
                return Err("duplicate configuration key");
            }
            match key {
                "version" => {
                    if value != "3" {
                        return Err("unsupported configuration version");
                    }
                    has_version = true;
                    base.push("version=2".to_owned());
                }
                "database_path" => db.database_path = Some(value.to_owned()),
                "source_db_path" => db.source_path = Some(value.to_owned()),
                "backup_db_path" => db.backup_path = Some(value.to_owned()),
                "db_password" => db.password.literal = Some(value.to_owned()),
                "db_password_file" => db.password.file = Some(value.to_owned()),
                "new_db_password" => db.new_password.literal = Some(value.to_owned()),
                "new_db_password_file" => db.new_password.file = Some(value.to_owned()),
                _ => base.push(trimmed.to_owned()),
            }
        }
        if !has_version {
            return Err("missing configuration version");
        }
        Ok(Self {
            base: InstallerConfigV2::parse(&base.join("\n"))?,
            database: db,
        })
    }

    pub fn preview(&self, mode: Mode) -> Result<InstallPlan, &'static str> {
        self.base.preview(mode)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const BASE: &str = "version=3\ninstall_optional_conda=false\ninstall_optional_comfyui=false\nexplicit_optional_consent=false\ninstall_optional_git=false\ninstall_optional_gh=false\noffer_gh_login=false\nconsent_git=false\nconsent_gh=false\nconsent_login=false\n";

    #[test]
    fn v3_preserves_original_gui_and_cli_base_options() {
        let c = InstallerConfigV3::parse(&format!("{BASE}database_path=/tmp/owner.db\ndb_password=OwnerPass123!\n")).unwrap();
        assert_eq!(c.database.database_path.as_deref(), Some("/tmp/owner.db"));
        assert_eq!(c.database.password.literal.as_deref(), Some("OwnerPass123!"));
        assert!(c.preview(Mode::Silent).is_ok());
        assert!(InstallerConfigV3::parse(&format!("{BASE}db_password=x\ndb_password=y\n")).is_err());
        assert!(InstallerConfigV3::parse(&format!("{BASE}unexpected_key=value\n")).is_err());
    }

    #[test]
    fn accepts_all_noninteractive_secret_sources_and_no_implicit_choice() {
        let mut input = SecretInput { literal: Some("literal password".into()), file: None };
        assert_eq!(input.resolve(None, None).unwrap().as_deref(), Some("literal password"));
        assert!(input.resolve(Some("env".into()), None).is_err());
        input.literal = None;
        assert_eq!(input.resolve(Some("env".into()), None).unwrap().as_deref(), Some("env"));
        assert_eq!(input.resolve(None, Some("stdin")).unwrap().as_deref(), Some("stdin"));
        assert_eq!(input.resolve(None, None).unwrap(), None);
    }

    #[test]
    fn bounded_stdin_json_rejects_unknown_and_oversized_fields() {
        let f = parse_stdin_secrets(br#"{"db_password":"key","new_db_password":"next"}"#.as_slice()).unwrap();
        assert_eq!(f.db_password.as_deref(), Some("key"));
        assert_eq!(f.new_db_password.as_deref(), Some("next"));
        assert!(parse_stdin_secrets(br#"{"unknown":"key"}"#.as_slice()).is_err());
        assert!(parse_stdin_secrets(vec![b'a'; 16 * 1024 + 1].as_slice()).is_err());
    }
}
