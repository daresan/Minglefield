//! Pure, read-only schema compatibility evaluation.
//! This module does not open databases or perform migrations.

use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TableContract {
    pub name: String,
    pub required_columns: BTreeSet<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SchemaContract {
    pub application_id: u32,
    pub version: u32,
    pub tables: Vec<TableContract>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SchemaSnapshot {
    pub application_id: u32,
    pub version: u32,
    pub tables: BTreeMap<String, BTreeSet<String>>,
    pub integrity_ok: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Compatibility {
    IntegrityFailed,
    UnregisteredApplication,
    UnversionedLegacy,
    VersionMismatch {
        expected: u32,
        actual: u32,
    },
    MissingSchema {
        tables: Vec<String>,
        columns: Vec<String>,
    },
    Compatible {
        extra_tables: Vec<String>,
    },
}

/// Only positive results after a separate SQLite integrity check may be used
/// to authorize a future migration preview. Extra columns are not removed.
pub fn evaluate_schema(snapshot: &SchemaSnapshot, contract: &SchemaContract) -> Compatibility {
    if !snapshot.integrity_ok {
        return Compatibility::IntegrityFailed;
    }
    if contract.application_id == 0 || snapshot.application_id != contract.application_id {
        return Compatibility::UnregisteredApplication;
    }
    if snapshot.version == 0 {
        return Compatibility::UnversionedLegacy;
    }
    if snapshot.version != contract.version {
        return Compatibility::VersionMismatch {
            expected: contract.version,
            actual: snapshot.version,
        };
    }
    let mut missing_tables = Vec::new();
    let mut missing_columns = Vec::new();
    let expected: BTreeSet<&str> = contract.tables.iter().map(|t| t.name.as_str()).collect();
    for table in &contract.tables {
        match snapshot.tables.get(&table.name) {
            None => missing_tables.push(table.name.clone()),
            Some(columns) => {
                for column in &table.required_columns {
                    if !columns.contains(column) {
                        missing_columns.push(format!("{}.{}", table.name, column));
                    }
                }
            }
        }
    }
    if !missing_tables.is_empty() || !missing_columns.is_empty() {
        return Compatibility::MissingSchema {
            tables: missing_tables,
            columns: missing_columns,
        };
    }
    let extra_tables = snapshot
        .tables
        .keys()
        .filter(|name| !expected.contains(name.as_str()))
        .cloned()
        .collect();
    Compatibility::Compatible { extra_tables }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (SchemaSnapshot, SchemaContract) {
        let mut tables = BTreeMap::new();
        tables.insert(
            "alpha_users".to_owned(),
            BTreeSet::from(["user_id".to_owned()]),
        );
        (
            SchemaSnapshot {
                application_id: 123,
                version: 1,
                tables,
                integrity_ok: true,
            },
            SchemaContract {
                application_id: 123,
                version: 1,
                tables: vec![TableContract {
                    name: "alpha_users".to_owned(),
                    required_columns: BTreeSet::from(["user_id".to_owned()]),
                }],
            },
        )
    }

    #[test]
    fn matches_required_schema_and_tolerates_extra_tables() {
        let (mut snapshot, contract) = fixture();
        assert_eq!(
            evaluate_schema(&snapshot, &contract),
            Compatibility::Compatible {
                extra_tables: vec![]
            }
        );
        snapshot
            .tables
            .insert("future_extension".to_owned(), BTreeSet::new());
        assert_eq!(
            evaluate_schema(&snapshot, &contract),
            Compatibility::Compatible {
                extra_tables: vec!["future_extension".to_owned()]
            }
        );
    }

    #[test]
    fn rejects_bad_integrity_identity_and_version() {
        let (mut snapshot, contract) = fixture();
        snapshot.integrity_ok = false;
        assert_eq!(
            evaluate_schema(&snapshot, &contract),
            Compatibility::IntegrityFailed
        );
        snapshot.integrity_ok = true;
        snapshot.application_id = 0;
        assert_eq!(
            evaluate_schema(&snapshot, &contract),
            Compatibility::UnregisteredApplication
        );
        snapshot.application_id = 123;
        snapshot.version = 0;
        assert_eq!(
            evaluate_schema(&snapshot, &contract),
            Compatibility::UnversionedLegacy
        );
        snapshot.version = 2;
        assert_eq!(
            evaluate_schema(&snapshot, &contract),
            Compatibility::VersionMismatch {
                expected: 1,
                actual: 2
            }
        );
    }

    #[test]
    fn rejects_missing_tables_and_columns() {
        let (mut snapshot, contract) = fixture();
        snapshot.tables.clear();
        assert_eq!(
            evaluate_schema(&snapshot, &contract),
            Compatibility::MissingSchema {
                tables: vec!["alpha_users".to_owned()],
                columns: vec![],
            }
        );
        snapshot
            .tables
            .insert("alpha_users".to_owned(), BTreeSet::new());
        assert_eq!(
            evaluate_schema(&snapshot, &contract),
            Compatibility::MissingSchema {
                tables: vec![],
                columns: vec!["alpha_users.user_id".to_owned()],
            }
        );
    }
}
