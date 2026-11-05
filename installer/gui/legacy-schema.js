// Strict, read-only identification of the known unversioned Alpha database family.
// This is an eligibility preflight, NOT authorization to execute a migration.
export const ALPHA_REQUIRED_TABLES = Object.freeze([
  "alpha_agent_grants", "alpha_agent_host_assignments", "alpha_agents",
  "alpha_executor_hosts", "alpha_game_installation_evidence", "alpha_game_projects",
  "alpha_git_profiles", "alpha_invites", "alpha_jobs", "alpha_passwords",
  "alpha_sec01_admissions", "alpha_sessions", "alpha_users",
  "sec01_game_install_journal", "sec01_host_active_slots", "sec01_host_admins",
  "sec01_host_approvals", "sec01_host_comfy_executions",
  "sec01_host_comfy_workflows", "sec01_host_commits",
  "sec01_host_effect_definitions", "sec01_host_job_parameters",
  "sec01_host_jobs", "sec01_host_owners", "sec01_host_rules",
  "sec01_host_runtimes", "sec01_host_settings"
]);

export function assessLegacyAlphaSchema(inspection) {
  if (!inspection || inspection.integrityOk !== true || inspection.foreignKeysOk !== true ||
      inspection.foreignKeyViolations !== 0) {
    return { recognized: false, reason: "integrity_or_foreign_keys_unverified", migrationEnabled: false };
  }
  if (inspection.applicationId !== 0 || inspection.userVersion !== 0) {
    return { recognized: false, reason: "not_unversioned_alpha", migrationEnabled: false };
  }
  if (!Array.isArray(inspection.tables) || !Array.isArray(inspection.schemaObjects)) {
    return { recognized: false, reason: "schema_inventory_incomplete", migrationEnabled: false };
  }
  const names = inspection.tables.map(table => table?.name);
  if (names.some(name => typeof name !== "string") || new Set(names).size !== names.length) {
    return { recognized: false, reason: "invalid_or_duplicate_tables", migrationEnabled: false };
  }
  const missing = ALPHA_REQUIRED_TABLES.filter(name => !names.includes(name));
  if (missing.length) {
    return { recognized: false, reason: "required_alpha_tables_missing", missing,
      migrationEnabled: false };
  }
  // Registered signatures are verified in Rust against SQLite PRAGMA
  // table_xinfo on a consistent snapshot. Never infer them from table names.
  const registered = inspection.registeredMapping;
  if (!registered || registered.migrationEnabled !== false ||
      typeof registered.reason !== "string" ||
      !Number.isSafeInteger(registered.matchedTableCount) ||
      !Number.isSafeInteger(registered.matchedColumnCount) ||
      !Array.isArray(registered.missingTables) ||
      !Array.isArray(registered.incompatibleTables) ||
      !Array.isArray(registered.extensionTables)) {
    return { recognized: false, reason: "registered_schema_mapping_unavailable",
      migrationEnabled: false };
  }
  if (registered.recognized !== true ||
      registered.matchedTableCount !== ALPHA_REQUIRED_TABLES.length ||
      registered.matchedColumnCount !== 111 ||
      registered.missingTables.length || registered.incompatibleTables.length ||
      registered.extensionTables.length) {
    return { recognized: false, reason: registered.reason,
      matchedTableCount: registered.matchedTableCount,
      matchedColumnCount: registered.matchedColumnCount,
      missingTables: registered.missingTables,
      incompatibleTables: registered.incompatibleTables,
      extensionTables: registered.extensionTables, migrationEnabled: false };
  }
  // A structural contract is not yet a durable migration or operational
  // SQLCipher runtime. This result must never set migrationEnabled=true.
  return { recognized: true, reason: "registered_alpha_column_signatures_verified",
    matchedTableCount: registered.matchedTableCount,
    matchedColumnCount: registered.matchedColumnCount,
    migrationEnabled: false };

}
