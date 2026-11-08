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
    ];
    let mut results: Vec<DataCandidate> = known
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
                        sqlite_user_version = Some(u32::from_be_bytes([
                            header[60], header[61], header[62], header[63],
                        ]));
                        sqlite_application_id = Some(u32::from_be_bytes([
                            header[68], header[69], header[70], header[71],
                        ]));
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
        .collect();
    // Scan only direct children of the selected data directory, not arbitrary
    // source trees. The SQLite magic header, not the filename, identifies candidates.
    if let Ok(entries) = std::fs::read_dir(root) {
        for entry in entries.flatten().take(4096) {
            let path = entry.path();
            let Ok(meta) = std::fs::symlink_metadata(&path) else {
                continue;
            };
            if !meta.file_type().is_file() || meta.len() < 100 || meta.len() > 1024 * 1024 * 1024 {
                continue;
            }
            use std::io::Read;
            let mut header = [0u8; 100];
            let Ok(mut file) = std::fs::File::open(&path) else {
                continue;
            };
            if file.read_exact(&mut header).is_err() {
                continue;
            }
            let plaintext = &header[..16] == b"SQLite format 3\0";
            let looks_like_database =
                path.extension()
                    .and_then(|ext| ext.to_str())
                    .is_some_and(|ext| {
                        matches!(
                            ext.to_ascii_lowercase().as_str(),
                            "db" | "sqlite" | "sqlite3" | "sqlcipher"
                        )
                    });
            // SQLCipher encrypts even the SQLite header. Known extensions
            // remain read-only *candidates*, never proofs of a valid DB.
            if !plaintext && !looks_like_database {
                continue;
            }
            let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
                continue;
            };
            let size = u16::from_be_bytes([header[16], header[17]]);
            results.push(DataCandidate {
                relative_path: name.to_owned(),
                kind: "sqlite_database",
                status: if plaintext {
                    "sqlite_header_valid_unverified"
                } else {
                    "encrypted_or_unknown_header_unverified"
                },
                sqlite_page_size: plaintext.then_some(if size == 1 {
                    65536
                } else {
                    u32::from(size)
                }),
                sqlite_user_version: plaintext.then_some(u32::from_be_bytes([
                    header[60], header[61], header[62], header[63],
                ])),
                sqlite_application_id: plaintext.then_some(u32::from_be_bytes([
                    header[68], header[69], header[70], header[71],
                ])),
            });
        }
    }
    results.sort_by(|a, b| a.relative_path.cmp(&b.relative_path));
    results
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
        std::fs::write(root.join("custom-name.anything"), header).unwrap();
        std::fs::write(root.join("not-a-database.sqlite3"), b"not sqlite").unwrap();
        // Ciphertext headers are indistinguishable from random bytes.
        // These are offered for password-based inspection, not trusted.
        std::fs::write(root.join("already-migrated.sqlcipher"), [0x83u8; 100]).unwrap();
        std::fs::write(
            root.join("untrusted.py"),
            b"raise Exception('must not execute')",
        )
        .unwrap();
        let found = inspect_data_directory(&root);
        assert_eq!(found.len(), 3);
        assert_eq!(found[0].relative_path, ".minglefield/project.json");
        assert_eq!(found[0].status, "json_candidate_unvalidated");
        assert_eq!(found[1].relative_path, "already-migrated.sqlcipher");
        assert_eq!(found[1].status, "encrypted_or_unknown_header_unverified");
        assert_eq!(found[1].sqlite_page_size, None);
        assert_eq!(found[2].relative_path, "custom-name.anything");
        assert_eq!(found[2].status, "sqlite_header_valid_unverified");
        assert_eq!(found[2].sqlite_page_size, Some(4096));
        assert_eq!(found[2].sqlite_user_version, Some(0));
        std::fs::remove_dir_all(root).unwrap();
    }
}
