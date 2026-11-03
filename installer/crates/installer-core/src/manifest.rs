//! Strict, read-only single-artifact manifest verification.
//! SHA-256 detects corruption, but an unsigned manifest is NOT trusted publisher evidence.
use crate::integrity::sha256_hex;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArtifactManifest {
    pub version: u32,
    pub filename: String,
    pub size: u64,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ManifestError {
    InvalidFormat,
    InvalidField,
    InvalidVersion,
    InvalidFilename,
    SizeMismatch,
    DigestMismatch,
}

impl ArtifactManifest {
    /// UTF-8 key=value format; exactly four keys, no implicit defaults.
    pub fn parse(input: &str) -> Result<Self, ManifestError> {
        let mut fields = std::collections::HashMap::new();
        for line in input.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let (key, value) = line.split_once('=').ok_or(ManifestError::InvalidFormat)?;
            let key = key.trim();
            let value = value.trim();
            if !matches!(key, "version" | "filename" | "size" | "sha256")
                || fields.insert(key, value).is_some()
            {
                return Err(ManifestError::InvalidField);
            }
        }
        if fields.len() != 4 {
            return Err(ManifestError::InvalidField);
        }
        let version = fields["version"].parse().map_err(|_| ManifestError::InvalidVersion)?;
        if version != 1 {
            return Err(ManifestError::InvalidVersion);
        }
        let filename = fields["filename"];
        if filename.is_empty()
            || filename == "."
            || filename == ".."
            || filename.chars().any(|c| matches!(c, '/' | '\\' | ':'))
            || filename.chars().any(|c| c.is_control())
        {
            return Err(ManifestError::InvalidFilename);
        }
        let size = fields["size"].parse().map_err(|_| ManifestError::InvalidField)?;
        let sha256 = fields["sha256"];
        if sha256.len() != 64 || !sha256.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err(ManifestError::InvalidField);
        }
        Ok(Self {
            version,
            filename: filename.to_owned(),
            size,
            sha256: sha256.to_ascii_lowercase(),
        })
    }

    pub fn verify_bytes(&self, bytes: &[u8]) -> Result<(), ManifestError> {
        if u64::try_from(bytes.len()).map_err(|_| ManifestError::SizeMismatch)? != self.size {
            return Err(ManifestError::SizeMismatch);
        }
        if sha256_hex(bytes) != self.sha256 {
            return Err(ManifestError::DigestMismatch);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn verifies_known_artifact_and_rejects_tampering() {
        let input = "version=1\nfilename=payload.bin\nsize=3\nsha256=ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\n";
        let manifest = ArtifactManifest::parse(input).unwrap();
        assert_eq!(manifest.verify_bytes(b"abc"), Ok(()));
        assert_eq!(manifest.verify_bytes(b"abd"), Err(ManifestError::DigestMismatch));
        assert_eq!(manifest.verify_bytes(b"ab"), Err(ManifestError::SizeMismatch));
    }

    #[test]
    fn rejects_traversal_duplicates_and_unsupported_version() {
        let input = "version=1\nfilename=payload.bin\nsize=3\nsha256=ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\n";
        assert!(ArtifactManifest::parse(&input.replace("payload.bin", "../payload.bin")).is_err());
        assert!(ArtifactManifest::parse(&input.replace("payload.bin", "..\\payload.bin")).is_err());
        assert!(ArtifactManifest::parse(&input.replace("version=1", "version=2")).is_err());
        assert!(ArtifactManifest::parse(&format!("{input}size=3\n")).is_err());
        assert!(ArtifactManifest::parse(&input.replace("size=3", "size=three")).is_err());
    }
}
