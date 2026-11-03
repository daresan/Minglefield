//! Explicit publisher-trust boundary for installer artifacts.
//!
//! SHA-256 only establishes integrity relative to a manifest. Neither an
//! unsigned manifest nor a caller-supplied digest establishes publisher trust.
//! Release provenance is tied to the selected GitHub repository and protected
//! release commit, not to a paid publisher certificate. A fork may be its own
//! publisher. Until repository/release provenance is verifiable, verification
//! MUST fail closed. This module performs no filesystem or network operations.

use crate::manifest::ArtifactManifest;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrustError {
    RepositoryProvenanceUnavailable,
    InvalidManifest,
    InvalidArtifact,
}

/// A publisher verification policy, not an overrideable success flag.
///
/// The release policy does not yet verify the selected GitHub repository,
/// protected release commit, and artifact-to-commit provenance. A checksum
/// alone cannot establish those properties.
#[derive(Debug, Clone, Copy, Default)]
pub struct PublisherPolicy;

impl PublisherPolicy {
    /// Intentionally fails closed until repository release provenance exists.
    pub fn verify_release(&self, manifest_text: &str, artifact: &[u8]) -> Result<(), TrustError> {
        let manifest =
            ArtifactManifest::parse(manifest_text).map_err(|_| TrustError::InvalidManifest)?;
        manifest
            .verify_bytes(artifact)
            .map_err(|_| TrustError::InvalidArtifact)?;
        Err(TrustError::RepositoryProvenanceUnavailable)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const MANIFEST: &str = concat!(
        "version=1\n",
        "filename=payload.bin\n",
        "size=3\n",
        "sha256=ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\n"
    );

    #[test]
    fn matching_checksum_never_grants_publisher_trust() {
        let result = PublisherPolicy.verify_release(MANIFEST, b"abc");
        assert_eq!(result, Err(TrustError::RepositoryProvenanceUnavailable));
    }

    #[test]
    fn rejects_tampered_artifacts_before_publisher_check() {
        let result = PublisherPolicy.verify_release(MANIFEST, b"abd");
        assert_eq!(result, Err(TrustError::InvalidArtifact));
    }

    #[test]
    fn rejects_unsigned_malformed_manifest() {
        let result = PublisherPolicy.verify_release("version=2", b"abc");
        assert_eq!(result, Err(TrustError::InvalidManifest));
    }

    #[test]
    fn integrity_api_remains_distinct_from_trust_api() {
        let manifest = ArtifactManifest::parse(MANIFEST).unwrap();
        assert_eq!(manifest.verify_bytes(b"abc"), Ok(()));
        assert!(PublisherPolicy.verify_release(MANIFEST, b"abc").is_err());
    }
}
