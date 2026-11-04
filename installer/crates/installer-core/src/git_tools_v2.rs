//! Strict, non-executing v2 optional Git/gh selection contract.
//! Kept separate from v1 until the CLI and GUI can consume v2 atomically.

use std::collections::HashSet;

pub const VERSION: u32 = 2;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GitToolOptions {
    pub install_optional_git: bool,
    pub install_optional_gh: bool,
    pub offer_gh_login: bool,
    pub consent_git: bool,
    pub consent_gh: bool,
    pub consent_login: bool,
}

impl GitToolOptions {
    pub fn disabled() -> Self {
        Self {
            install_optional_git: false,
            install_optional_gh: false,
            offer_gh_login: false,
            consent_git: false,
            consent_gh: false,
            consent_login: false,
        }
    }

    /// This is a planning contract only. It never installs tools or signs in.
    pub fn validate(&self) -> Result<(), &'static str> {
        if self.install_optional_git && !self.consent_git {
            return Err("git installation requires separate explicit consent");
        }
        if self.install_optional_gh && !self.consent_gh {
            return Err("gh installation requires separate explicit consent");
        }
        if self.offer_gh_login && !self.consent_login {
            return Err("gh login offer requires separate explicit consent");
        }
        // gh may be preinstalled; requesting login does not require installing gh.
        Ok(())
    }

    /// Parse only the v2 Git-tool selection block. The full installer config
    /// remains v1 and must reject these keys until v2 is integrated end-to-end.
    pub fn parse(text: &str) -> Result<Self, &'static str> {
        let mut options = Self::disabled();
        let mut seen = HashSet::new();
        for line in text.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let (key, value) = line.split_once('=').ok_or("invalid configuration line")?;
            let key = key.trim();
            if !seen.insert(key.to_owned()) {
                return Err("duplicate configuration key");
            }
            let value = match value.trim() {
                "true" => true,
                "false" => false,
                _ => return Err("boolean must be true or false"),
            };
            match key {
                "install_optional_git" => options.install_optional_git = value,
                "install_optional_gh" => options.install_optional_gh = value,
                "offer_gh_login" => options.offer_gh_login = value,
                "consent_git" => options.consent_git = value,
                "consent_gh" => options.consent_gh = value,
                "consent_login" => options.consent_login = value,
                _ => return Err("unknown configuration key"),
            }
        }
        if seen.len() != 6 {
            return Err("missing configuration key");
        }
        options.validate()?;
        Ok(options)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const BASE: &str = "install_optional_git=false\ninstall_optional_gh=false\noffer_gh_login=false\nconsent_git=false\nconsent_gh=false\nconsent_login=false\n";

    #[test]
    fn defaults_are_off_and_valid() {
        assert_eq!(
            GitToolOptions::parse(BASE).unwrap(),
            GitToolOptions::disabled()
        );
    }

    #[test]
    fn git_and_gh_are_independent() {
        let gh = BASE
            .replace("install_optional_gh=false", "install_optional_gh=true")
            .replace("consent_gh=false", "consent_gh=true");
        let parsed = GitToolOptions::parse(&gh).unwrap();
        assert!(!parsed.install_optional_git);
        assert!(parsed.install_optional_gh);
        let git = BASE
            .replace("install_optional_git=false", "install_optional_git=true")
            .replace("consent_git=false", "consent_git=true");
        let parsed = GitToolOptions::parse(&git).unwrap();
        assert!(parsed.install_optional_git);
        assert!(!parsed.install_optional_gh);
    }

    #[test]
    fn consent_is_independent_and_fail_closed() {
        for key in [
            "install_optional_git",
            "install_optional_gh",
            "offer_gh_login",
        ] {
            let candidate = BASE.replace(&format!("{key}=false"), &format!("{key}=true"));
            assert!(GitToolOptions::parse(&candidate).is_err());
        }
        let login = BASE
            .replace("offer_gh_login=false", "offer_gh_login=true")
            .replace("consent_login=false", "consent_login=true");
        assert!(GitToolOptions::parse(&login).unwrap().offer_gh_login);
    }

    #[test]
    fn strict_parser_rejects_ambiguous_input() {
        assert!(GitToolOptions::parse(&format!("{BASE}consent_gh=false\n")).is_err());
        assert!(GitToolOptions::parse(&format!("{BASE}unknown=false\n")).is_err());
        assert!(GitToolOptions::parse(&BASE.replace("consent_git=false\n", "")).is_err());
        assert!(
            GitToolOptions::parse(&BASE.replace("consent_git=false", "consent_git=TRUE")).is_err()
        );
    }
}
