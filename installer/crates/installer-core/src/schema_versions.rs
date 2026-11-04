//! Pure migration planning. No database connections or mutations.
//! The current unversioned Alpha schema is not assigned a version here.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MigrationStep {
    pub from: u32,
    pub to: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MigrationPlanError {
    UnversionedLegacy,
    UnknownApplication,
    UnsupportedVersion,
    MissingStep(u32),
    AmbiguousStep(u32),
    InvalidRegistry,
}

/// Plan consecutive, explicitly registered migrations. Never infer steps.
pub fn plan_migrations(
    application_id: u32,
    expected_application_id: u32,
    source_version: u32,
    target_version: u32,
    steps: &[MigrationStep],
) -> Result<Vec<MigrationStep>, MigrationPlanError> {
    if application_id == 0 || application_id != expected_application_id {
        return Err(MigrationPlanError::UnknownApplication);
    }
    if source_version == 0 {
        return Err(MigrationPlanError::UnversionedLegacy);
    }
    if target_version == 0 || source_version > target_version {
        return Err(MigrationPlanError::UnsupportedVersion);
    }
    if steps
        .iter()
        .any(|step| step.from == 0 || step.to <= step.from)
    {
        return Err(MigrationPlanError::InvalidRegistry);
    }
    let mut result = Vec::new();
    let mut current = source_version;
    while current < target_version {
        let mut matches = steps.iter().filter(|step| step.from == current);
        let step = matches
            .next()
            .ok_or(MigrationPlanError::MissingStep(current))?;
        if matches.next().is_some() {
            return Err(MigrationPlanError::AmbiguousStep(current));
        }
        if step.to > target_version {
            return Err(MigrationPlanError::MissingStep(current));
        }
        result.push(*step);
        current = step.to;
    }
    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    const APP: u32 = 0x4d_47_46_44;

    #[test]
    fn supports_multiple_version_steps() {
        let steps = [
            MigrationStep { from: 1, to: 2 },
            MigrationStep { from: 2, to: 3 },
            MigrationStep { from: 3, to: 4 },
        ];
        assert_eq!(plan_migrations(APP, APP, 1, 4, &steps).unwrap(), steps);
        assert!(plan_migrations(APP, APP, 4, 4, &steps).unwrap().is_empty());
    }

    #[test]
    fn rejects_unrecognized_and_unversioned_sources() {
        assert_eq!(
            plan_migrations(0, APP, 0, 2, &[]),
            Err(MigrationPlanError::UnknownApplication)
        );
        assert_eq!(
            plan_migrations(APP, APP, 0, 2, &[]),
            Err(MigrationPlanError::UnversionedLegacy)
        );
        assert_eq!(
            plan_migrations(42, APP, 1, 2, &[]),
            Err(MigrationPlanError::UnknownApplication)
        );
    }

    #[test]
    fn rejects_missing_ambiguous_and_downgrade_paths() {
        let step = MigrationStep { from: 1, to: 2 };
        assert_eq!(
            plan_migrations(APP, APP, 1, 3, &[step]),
            Err(MigrationPlanError::MissingStep(2))
        );
        assert_eq!(
            plan_migrations(APP, APP, 1, 2, &[step, step]),
            Err(MigrationPlanError::AmbiguousStep(1))
        );
        assert_eq!(
            plan_migrations(APP, APP, 3, 2, &[]),
            Err(MigrationPlanError::UnsupportedVersion)
        );
    }
}
