//! Read-only discovery of user data, independent of source checkout recognition.
//! No source code execution, DB connections, or filesystem mutation.
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DataCandidate {
    pub relative_path: String,
    pub kind: &'static str,
    pub status: &'static str,
}

pub fn inspect_data_directory(root: &Path) -> Vec<DataCandidate> {
    if !root.is_dir() {
        return Vec::new();
    }
    // Known locations only: do not recurse through arbitrary source trees.
    let known = [
        (".minglefield/project.json", "project_config"),
        ("project.json", "project_config"),
        ("hosts.json", "host_config"),
        ("config.json", "app_config"),
        ("minglefield.db", "sqlite_database"),
        ("data/minglefield.db", "sqlite_database"),
        ("data/alpha.db", "sqlite_database"),
        ("alpha.sqlite3", "sqlite_database"),
    ];
    known.iter().filter_map(|(relative, kind)| {
        let path = root.join(relative);
        let meta = std::fs::symlink_metadata(&path).ok()?;
        // Never follow symlinked candidates, including parent directories.
        if !meta.file_type().is_file() || meta.len() > 1024 * 1024 * 1024 {
            return None;
        }
        if path.ancestors().take_while(|p| *p != root).any(|p| {
            std::fs::symlink_metadata(p).is_ok_and(|m| m.file_type().is_symlink())
        }) {
            return None;
        }
        let status = if *kind == "sqlite_database" {
            use std::io::Read;
            let mut header = [0u8; 16];
            match std::fs::File::open(&path).and_then(|mut f| f.read_exact(&mut header)) {
                Ok(()) if &header == b"SQLite format 3\0" => "sqlite_header_valid_unverified",
                _ => "unrecognized_database",
            }
        } else {
            match std::fs::read(&path) {
                Ok(bytes) if bytes.len() <= 4 * 1024 * 1024 => {
                    let text = std::str::from_utf8(&bytes).unwrap_or("");
                    if text.trim_start_matches('\u{feff}').trim_start().starts_with('{')
                        && text.trim_end().ends_with('}') {
                        "json_candidate_unvalidated"
                    } else {
                        "unrecognized_config"
                    }
                }
                _ => "unreadable_or_too_large",
            }
        };
        Some(DataCandidate { relative_path: (*relative).to_owned(), kind, status })
    }).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn detects_data_without_repo_markers_and_ignores_code() {
        let root = std::env::temp_dir().join(format!("minglefield-inventory-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join(".minglefield")).unwrap();
        std::fs::write(root.join(".minglefield/project.json"), b"{\"name\":\"test\"}").unwrap();
        std::fs::write(root.join("minglefield.db"), b"SQLite format 3\0dummy").unwrap();
        std::fs::write(root.join("untrusted.py"), b"raise Exception('must not execute')").unwrap();
        let found = inspect_data_directory(&root);
        assert_eq!(found.len(), 2);
        assert_eq!(found[0].status, "json_candidate_unvalidated");
        assert_eq!(found[1].status, "sqlite_header_valid_unverified");
        std::fs::remove_dir_all(root).unwrap();
    }
}
