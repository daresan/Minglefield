//! Read-only source identity metadata for Minglefield release provenance.
//! Parsing a source claim does not verify GitHub ownership, ancestry or a build.
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReleaseSource {
    pub version: u32,
    pub repository_id: u64,
    pub repository: String,
    pub commit: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SourceError {
    InvalidField,
    InvalidVersion,
    InvalidRepository,
    InvalidCommit,
}

impl ReleaseSource {
    /// Strict versioned UTF-8 key=value metadata; no network calls or side effects.
    pub fn parse(input: &str) -> Result<Self, SourceError> {
        let mut fields = HashMap::new();
        for line in input.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let (key, value) = line.split_once('=').ok_or(SourceError::InvalidField)?;
            let key = key.trim();
            let value = value.trim();
            if !matches!(key, "version" | "repository_id" | "repository" | "commit")
                || fields.insert(key, value).is_some()
            {
                return Err(SourceError::InvalidField);
            }
        }
        if fields.len() != 4 {
            return Err(SourceError::InvalidField);
        }
        if fields["version"] != "1" {
            return Err(SourceError::InvalidVersion);
        }
        let repository_id: u64 = fields["repository_id"]
            .parse()
            .map_err(|_| SourceError::InvalidRepository)?;
        if repository_id == 0 {
            return Err(SourceError::InvalidRepository);
        }
        let repository = fields["repository"];
        let mut parts = repository.split('/');
        let owner = parts.next().unwrap_or_default();
        let name = parts.next().unwrap_or_default();
        let valid = |s: &str| {
            !s.is_empty()
                && s.len() <= 100
                && s.bytes()
                    .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.'))
        };
        if !valid(owner) || !valid(name) || parts.next().is_some() {
            return Err(SourceError::InvalidRepository);
        }
        let commit = fields["commit"];
        if commit.len() != 40 || !commit.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err(SourceError::InvalidCommit);
        }
        Ok(Self {
            version: 1,
            repository_id,
            repository: repository.to_owned(),
            commit: commit.to_ascii_lowercase(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const SOURCE: &str = concat!(
        "version=1\n",
        "repository_id=12345\n",
        "repository=daresan/Minglefield\n",
        "commit=0123456789abcdef0123456789abcdef01234567\n"
    );

    #[test]
    fn accepts_complete_immutable_source_claim() {
        let source = ReleaseSource::parse(SOURCE).unwrap();
        assert_eq!(source.repository_id, 12345);
        assert_eq!(source.commit.len(), 40);
    }

    #[test]
    fn rejects_missing_duplicate_and_invalid_fields() {
        assert!(ReleaseSource::parse(&SOURCE.replace("version=1", "version=2")).is_err());
        assert!(ReleaseSource::parse(&format!("{SOURCE}commit=abc\n")).is_err());
        assert!(ReleaseSource::parse(&SOURCE.replace("12345", "0")).is_err());
        assert!(ReleaseSource::parse(&SOURCE.replace("daresan/Minglefield", "../Minglefield")).is_err());
        assert!(ReleaseSource::parse(&SOURCE.replace("0123456789abcdef0123456789abcdef01234567", "abc")).is_err());
    }
}
