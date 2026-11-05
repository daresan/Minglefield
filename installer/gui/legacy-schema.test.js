import test from "node:test";
import assert from "node:assert/strict";
import { ALPHA_REQUIRED_TABLES, assessLegacyAlphaSchema } from "./legacy-schema.js";

function inspection() {
  return { integrityOk: true, foreignKeysOk: true, foreignKeyViolations: 0,
    applicationId: 0, userVersion: 0, tables: ALPHA_REQUIRED_TABLES.map(name => ({ name })),
    schemaObjects: [],
    registeredMapping: { recognized: true, reason: "registered_alpha_column_signatures_verified",
      matchedTableCount: 27, matchedColumnCount: 111, missingTables: [],
      incompatibleTables: [], extensionTables: [], migrationEnabled: false } };
}

test("Rust-verified 27/111 legacy schema is recognized but migration stays disabled", () => {
  assert.equal(ALPHA_REQUIRED_TABLES.length, 27);
  assert.deepEqual(assessLegacyAlphaSchema(inspection()), {
    recognized: true, reason: "registered_alpha_column_signatures_verified",
    matchedTableCount: 27, matchedColumnCount: 111, migrationEnabled: false
  });
});

test("unrecognized or damaged source fails closed", () => {
  for (const change of [
    { integrityOk: false }, { foreignKeysOk: false }, { foreignKeyViolations: 1 },
    { applicationId: 123 }, { userVersion: 1 }, { tables: null },
    { schemaObjects: null }
  ]) {
    const result = assessLegacyAlphaSchema({ ...inspection(), ...change });
    assert.equal(result.migrationEnabled, false);
    assert.equal(result.recognized, false);
  }
});

test("missing and duplicate Alpha tables are rejected", () => {
  const base = inspection();
  const missing = assessLegacyAlphaSchema({ ...base, tables: base.tables.slice(1) });
  assert.equal(missing.reason, "required_alpha_tables_missing");
  assert.deepEqual(missing.missing, ["alpha_agent_grants"]);
  const duplicate = assessLegacyAlphaSchema({ ...base, tables: [...base.tables, base.tables[0]] });
  assert.equal(duplicate.reason, "invalid_or_duplicate_tables");
});

test("missing or incompatible backend mapping fails closed even with all table names", () => {
  const source = inspection();
  for (const registeredMapping of [
    undefined, { ...source.registeredMapping, recognized: false,
      reason: "alpha_column_signature_mismatch", incompatibleTables: ["alpha_users"] },
    { ...source.registeredMapping, matchedColumnCount: 110 },
    { ...source.registeredMapping, extensionTables: ["custom_plugin"] },
    { ...source.registeredMapping, migrationEnabled: true }
  ]) {
    const actual = assessLegacyAlphaSchema({ ...source, registeredMapping });
    assert.equal(actual.recognized, false);
    assert.equal(actual.migrationEnabled, false);
  }
});
