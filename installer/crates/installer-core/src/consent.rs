//! Side-effect-free consent and completion gates for future installation execution.
//! This module does not perform installation, persist consent, open files or launch apps.

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LicenseIdentity {
    pub release: String,
    pub license_id: String,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LicenseAcceptance {
    pub identity: LicenseIdentity,
    pub explicitly_accepted: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConsentError {
    MissingLicense,
    MissingAcceptance,
    LicenseMismatch,
    InvalidLicenseIdentity,
}

pub fn require_license_acceptance(
    offered: Option<&LicenseIdentity>,
    acceptance: Option<&LicenseAcceptance>,
) -> Result<(), ConsentError> {
    let offered = offered.ok_or(ConsentError::MissingLicense)?;
    if offered.release.is_empty()
        || offered.license_id.is_empty()
        || offered.sha256.len() != 64
        || !offered.sha256.bytes().all(|b| b.is_ascii_hexdigit())
    {
        return Err(ConsentError::InvalidLicenseIdentity);
    }
    let acceptance = acceptance.ok_or(ConsentError::MissingAcceptance)?;
    if !acceptance.explicitly_accepted {
        return Err(ConsentError::MissingAcceptance);
    }
    if &acceptance.identity != offered {
        return Err(ConsentError::LicenseMismatch);
    }
    Ok(())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CompletionOptions {
    pub show_readme: bool,
    pub launch_application: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InstallationOutcome {
    Succeeded,
    Failed,
    Cancelled,
}

pub fn completion_actions(
    outcome: InstallationOutcome,
    selected: CompletionOptions,
) -> CompletionOptions {
    if outcome == InstallationOutcome::Succeeded {
        selected
    } else {
        CompletionOptions {
            show_readme: false,
            launch_application: false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn license() -> LicenseIdentity {
        LicenseIdentity {
            release: "0.1.0-alpha.1".to_owned(),
            license_id: "GPL-3.0-or-later".to_owned(),
            sha256: "a".repeat(64),
        }
    }

    #[test]
    fn missing_or_declined_license_fails_closed() {
        let identity = license();
        assert_eq!(
            require_license_acceptance(None, None),
            Err(ConsentError::MissingLicense)
        );
        assert_eq!(
            require_license_acceptance(Some(&identity), None),
            Err(ConsentError::MissingAcceptance)
        );
        let declined = LicenseAcceptance {
            identity: identity.clone(),
            explicitly_accepted: false,
        };
        assert_eq!(
            require_license_acceptance(Some(&identity), Some(&declined)),
            Err(ConsentError::MissingAcceptance)
        );
    }

    #[test]
    fn license_acceptance_is_bound_to_release_and_digest() {
        let identity = license();
        let accepted = LicenseAcceptance {
            identity: identity.clone(),
            explicitly_accepted: true,
        };
        assert_eq!(
            require_license_acceptance(Some(&identity), Some(&accepted)),
            Ok(())
        );
        let mut changed = identity.clone();
        changed.sha256 = "b".repeat(64);
        assert_eq!(
            require_license_acceptance(Some(&changed), Some(&accepted)),
            Err(ConsentError::LicenseMismatch)
        );
        changed.sha256 = "not-a-digest".to_owned();
        assert_eq!(
            require_license_acceptance(Some(&changed), Some(&accepted)),
            Err(ConsentError::InvalidLicenseIdentity)
        );
    }

    #[test]
    fn completion_is_optional_and_requires_success() {
        let selected = CompletionOptions {
            show_readme: true,
            launch_application: true,
        };
        assert_eq!(
            completion_actions(InstallationOutcome::Succeeded, selected),
            selected
        );
        for outcome in [InstallationOutcome::Failed, InstallationOutcome::Cancelled] {
            assert_eq!(
                completion_actions(outcome, selected),
                CompletionOptions {
                    show_readme: false,
                    launch_application: false,
                }
            );
        }
    }
}
