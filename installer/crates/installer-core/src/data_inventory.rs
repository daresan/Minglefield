//! Read-only discovery of user data, independent of source checkout recognition.
//! No source code execution, DB connections, or filesystem mutation.
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DataCandidate {
    pub relative_path: String,
    pub kind: &'static str,
    pub status: &'static str,
    pub sqlite_page_size: Option<u32>,
    pub sqlite_user_version: Option<u32>,
    pub sqlite_application_id: Option<u32>,
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
    known
        .iter()
        .filter_map(|(relative, kind)| {
            let path = root.join(relative);
            let meta = std::fs::symlink_metadata(&path).ok()?;
            // Never follow symlinked candidates, including parent directories.
            if !meta.file_type().is_file() || meta.len() > 1024 * 1024 * 1024 {
                return None;
            }
            if path
                .ancestors()
                .take_while(|p| *p != root)
                .any(|p| std::fs::symlink_metadata(p).is_ok_and(|m| m.file_type().is_symlink()))
            {
                return None;
            }
            let mut sqlite_page_size = None;
            let mut sqlite_user_version = None;
            let mut sqlite_application_id = None;
            let status = if *kind == "sqlite_database" {
                use std::io::Read;
                let mut header = [0u8; 100];
                match std::fs::File::open(&path).and_then(|mut f| f.read_exact(&mut header)) {
                    Ok(()) if &header[..16] == b"SQLite format 3\0" => {
                        let size = u16::from_be_bytes([header[16], header[17]]);
                        sqlite_page_size = Some(if size == 1 { 65536 } else { u32::from(size) });
                        sqlite_user_version = Some(u32::from_be_bytes([header[60], header[61], header[62], header[63]]));
                        sqlite_application_id = Some(u32::from_be_bytes([header[68], header[69], header[70], header[71]]));
                        "sqlite_header_valid_unverified"
                    }
                    _ => "unrecognized_database",
                }
            } else {
                match std::fs::read(&path) {
                    Ok(bytes) if bytes.len() <= 4 * 1024 * 1024 => {
                        let text = std::str::from_utf8(&bytes).unwrap_or("");
                        if text
                            .trim_start_matches('\u{feff}')
                            .trim_start()
                            .starts_with('{')
                            && text.trim_end().ends_with('}')
                        {
                            "json_candidate_unvalidated"
                        } else {
                            "unrecognized_config"
                        }
                    }
                    _ => "unreadable_or_too_large",
                }
            };
            Some(DataCandidate {
                relative_path: (*relative).to_owned(),
                kind,
                status,
                sqlite_page_size,
                sqlite_user_version,
                sqlite_application_id,
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn detects_data_without_repo_markers_and_ignores_code() {
        let root =
            std::env::temp_dir().join(format!("minglefield-inventory-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join(".minglefield")).unwrap();
        std::fs::write(
            root.join(".minglefield/project.json"),
            b"{\"name\":\"test\"}",
        )
        .unwrap();
        let mut header = [0u8; 100];
        header[..16].copy_from_slice(b"SQLite format 3\0");
        header[16..18].copy_from_slice(&4096u16.to_be_bytes());
        std::fs::write(root.join("minglefield.db"), header).unwrap();
        std::fs::write(
            root.join("untrusted.py"),
            b"raise Exception('must not execute')",
        )
        .unwrap();
        let found = inspect_data_directory(&root);
        assert_eq!(found.len(), 2);
        assert_eq!(found[0].status, "json_candidate_unvalidated");
        assert_eq!(found[1].status, "sqlite_header_valid_unverified");
        assert_eq!(found[1].sqlite_page_size, Some(4096));
        assert_eq!(found[1].sqlite_user_version, Some(0));
        std::fs::remove_dir_all(root).unwrap();
    }
}
