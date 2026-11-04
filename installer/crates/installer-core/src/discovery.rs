//! Read-only, conservative detection of an explicitly selected source checkout.
//! Structural recognition is NOT publisher verification or launch readiness.
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CandidateKind {
    SourceCheckout,
    Unrecognized,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Candidate {
    pub kind: CandidateKind,
    pub location: String,
    pub provenance_verified: bool,
    pub launch_ready: bool,
}

pub fn inspect_source_directory(path: &Path) -> Candidate {
    let kind = if path.is_dir()
        && path.join("README.md").is_file()
        && path.join("AGENTS.md").is_file()
        && path.join("schemas").is_dir()
        && path.join("server").is_dir()
        && path.join("installer").is_dir()
        && std::fs::read_to_string(path.join("README.md"))
            .is_ok_and(|text| text.starts_with("# Minglefield\n"))
    {
        CandidateKind::SourceCheckout
    } else {
        CandidateKind::Unrecognized
    };
    Candidate {
        kind,
        location: path.to_string_lossy().into_owned(),
        provenance_verified: false,
        launch_ready: false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn recognizes_source_without_git_or_executable() {
        let tmp = tempfile::tempdir().unwrap();
        let root = tmp.path();
        fs::write(root.join("README.md"), "# Minglefield\nTest").unwrap();
        fs::write(root.join("AGENTS.md"), "rules").unwrap();
        for dir in ["schemas", "server", "installer"] {
            fs::create_dir(root.join(dir)).unwrap();
        }
        let candidate = inspect_source_directory(root);
        assert_eq!(candidate.kind, CandidateKind::SourceCheckout);
        assert!(!candidate.provenance_verified);
        assert!(!candidate.launch_ready);
        assert!(!root.join(".git").exists());
        fs::remove_file(root.join("AGENTS.md")).unwrap();
        assert_eq!(inspect_source_directory(root).kind, CandidateKind::Unrecognized);
    }

    #[test]
    fn rejects_unrelated_and_missing_paths() {
        let tmp = tempfile::tempdir().unwrap();
        assert_eq!(inspect_source_directory(tmp.path()).kind, CandidateKind::Unrecognized);
        assert_eq!(
            inspect_source_directory(&tmp.path().join("missing")).kind,
            CandidateKind::Unrecognized
        );
    }
}
