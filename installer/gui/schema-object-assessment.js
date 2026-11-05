// Read-only evidence from the Rust comparison with registered Alpha CREATE
// statements and SQLite's independently constructed reference schema.
// Names are not a substitute for structural proof or installation consent.
export function assessRegisteredSchemaObjects(inspection) {
  const raw = inspection?.registeredSchemaObjects;
  const disabled = { verified: false, reason: "registered_schema_object_audit_unavailable",
    migrationEnabled: false };
  if (!raw || typeof raw !== "object" || raw.migrationEnabled !== false ||
      typeof raw.reason !== "string" ||
      !Number.isSafeInteger(raw.expectedSchemaEntryCount) ||
      !Number.isSafeInteger(raw.matchedSchemaEntryCount) ||
      !Number.isSafeInteger(raw.expectedIndexCount) ||
      !Array.isArray(raw.missingObjects) ||
      !Array.isArray(raw.extraObjects) ||
      !Array.isArray(raw.incompatibleObjects) ||
      [raw.missingObjects, raw.extraObjects, raw.incompatibleObjects].some(
        names => names.some(name => typeof name !== "string"))) {
    return disabled;
  }
  const columns = inspection.registeredMapping;
  const verified = raw.verified === true &&
    raw.reason === "registered_alpha_schema_objects_verified" &&
    columns?.recognized === true &&
    columns?.matchedTableCount === 27 &&
    columns?.matchedColumnCount === 111 &&
    raw.expectedSchemaEntryCount >= 27 + raw.expectedIndexCount &&
    raw.expectedIndexCount >= 27 &&
    raw.matchedSchemaEntryCount === raw.expectedSchemaEntryCount &&
    raw.missingObjects.length === 0 &&
    raw.extraObjects.length === 0 &&
    raw.incompatibleObjects.length === 0;
  return {
    verified,
    reason: verified ? raw.reason
      : raw.verified === true ? "registered_schema_object_evidence_inconsistent" : raw.reason,
    expectedSchemaEntryCount: raw.expectedSchemaEntryCount,
    matchedSchemaEntryCount: raw.matchedSchemaEntryCount,
    expectedIndexCount: raw.expectedIndexCount,
    missingObjects: raw.missingObjects,
    extraObjects: raw.extraObjects,
    incompatibleObjects: raw.incompatibleObjects,
    // Structural verification does not authorize a durable SQLCipher database
    // or installation. Those require separate backend-enforced gates.
    migrationEnabled: false
  };
}
