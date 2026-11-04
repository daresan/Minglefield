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
            .is_ok_and(|text| {
                text.trim_start_matches('\u{feff}')
                    .lines()
                    .next()
                    .is_some_and(|line| line.trim_end_matches('\r') == "# Minglefield")
            })
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
    use std::time::{SystemTime, UNIX_EPOCH};

    fn test_root() -> std::path::PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!(
            "minglefield-discovery-{}-{unique}",
            std::process::id()
        ));
        fs::create_dir(&root).unwrap();
        root
    }

    #[test]
    fn recognizes_source_without_git_or_executable() {
        let owned_root = test_root();
        let root = owned_root.as_path();
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
        assert_eq!(
            inspect_source_directory(root).kind,
            CandidateKind::Unrecognized
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn recognizes_windows_crlf_and_utf8_bom_readme() {
        let root = test_root();
        fs::write(root.join("AGENTS.md"), "rules").unwrap();
        for dir in ["schemas", "server", "installer"] {
            fs::create_dir(root.join(dir)).unwrap();
        }
        for readme in ["# Minglefield\r\nWindows", "\u{feff}# Minglefield\r\nWindows"] {
            fs::write(root.join("README.md"), readme).unwrap();
            assert_eq!(
                inspect_source_directory(&root).kind,
                CandidateKind::SourceCheckout
            );
        }
        fs::write(root.join("README.md"), "# Unrelated\r\n").unwrap();
        assert_eq!(inspect_source_directory(&root).kind, CandidateKind::Unrecognized);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn rejects_unrelated_and_missing_paths() {
        let root = test_root();
        assert_eq!(
            inspect_source_directory(&root).kind,
            CandidateKind::Unrecognized
        );
        assert_eq!(
            inspect_source_directory(&root.join("missing")).kind,
            CandidateKind::Unrecognized
        );
        fs::remove_dir_all(root).unwrap();
    }
}
