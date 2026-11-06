import test from "node:test";
import assert from "node:assert/strict";
import { assessRegisteredSchemaObjects } from "./schema-object-assessment.js";

function source() {
  return {
    registeredMapping: { recognized: true, matchedTableCount: 27, matchedColumnCount: 111,
      migrationEnabled: false },
    registeredSchemaObjects: {
      verified: true, reason: "registered_alpha_schema_objects_verified",
      expectedSchemaEntryCount: 58, matchedSchemaEntryCount: 58,
      expectedIndexCount: 31, missingObjects: [], extraObjects: [],
      incompatibleObjects: [], migrationEnabled: false
    }
  };
}

test("verified DDL and index evidence remains separate from migration authorization",()=>{
  assert.deepEqual(assessRegisteredSchemaObjects(source()), {
    verified: true, reason: "registered_alpha_schema_objects_verified",
    expectedSchemaEntryCount: 58, matchedSchemaEntryCount: 58,
    expectedIndexCount: 31, missingObjects: [], extraObjects: [],
    incompatibleObjects: [], migrationEnabled: false
  });
});

test("missing backend or attempted migration elevation fails closed",()=>{
  assert.equal(assessRegisteredSchemaObjects({}).verified,false);
  assert.equal(assessRegisteredSchemaObjects(null).migrationEnabled,false);
  const original = source();
  for (const value of [undefined, { ...original.registeredSchemaObjects, migrationEnabled:true },
    { ...original.registeredSchemaObjects, matchedSchemaEntryCount:57 },
    { ...original.registeredSchemaObjects, expectedIndexCount:0 },
    { ...original.registeredSchemaObjects, missingObjects:["alpha_users"] },
    { ...original.registeredSchemaObjects, extraObjects:["unexpected_index"] },
    { ...original.registeredSchemaObjects, incompatibleObjects:["sec01_host_rules"] }
  ]) {
    const report = assessRegisteredSchemaObjects({ ...original, registeredSchemaObjects:value });
    assert.equal(report.verified,false);
    assert.equal(report.migrationEnabled,false);
  }
});

test("full-object equality is not accepted if column registry did not match",()=>{
  const src = source();
  for (const mapping of [
    undefined, { ...src.registeredMapping, recognized:false },
    { ...src.registeredMapping, matchedColumnCount:110 },
    { ...src.registeredMapping, matchedTableCount:26 }
  ]) {
    const result = assessRegisteredSchemaObjects({ ...src, registeredMapping: mapping });
    assert.equal(result.verified,false);
    assert.equal(result.migrationEnabled,false);
  }
});

test("mismatched source objects are shown by name without copying SQL or secrets",()=>{
  const src = source();
  src.registeredSchemaObjects = { ...src.registeredSchemaObjects,
    verified:false, reason:"alpha_unregistered_schema_objects",
    matchedSchemaEntryCount:57, extraObjects:["local_extension"] };
  const report = assessRegisteredSchemaObjects(src);
  assert.equal(report.verified,false);
  assert.equal(report.reason,"alpha_unregistered_schema_objects");
  assert.deepEqual(report.extraObjects,["local_extension"]);
  assert.equal(report.migrationEnabled,false);
});

test("any missing registered schema object is reported as optional version compatibility, not full approval", () => {
  const original = source();
  const expected = {
    ...original.registeredSchemaObjects,
    verified: false,
    reason: "alpha_required_schema_objects_missing",
    expectedSchemaEntryCount: 59,
    matchedSchemaEntryCount: 58,
    expectedIndexCount: 32,
    missingObjects: ["uq_game_install_one_active_project"]
  };
  const result = assessRegisteredSchemaObjects({
    ...original,
    registeredSchemaObjects: expected
  });
  assert.equal(result.reason, "alpha_required_schema_objects_missing");
  assert.equal(result.verified, false);
  assert.equal(result.migrationEnabled, false);
  assert.deepEqual(result.missingObjects, ["uq_game_install_one_active_project"]);
});

test("generic missing schema remains unverified regardless of existing row state", () => {
  const original = source();
  const result = assessRegisteredSchemaObjects({
    ...original,
    registeredSchemaObjects: {
      ...original.registeredSchemaObjects,
      verified: false,
      reason: "alpha_required_schema_objects_missing",
      expectedSchemaEntryCount: 59,
      matchedSchemaEntryCount: 58,
      expectedIndexCount: 32,
      missingObjects: ["uq_game_install_one_active_project"]
    }
  });
  assert.equal(result.reason, "alpha_required_schema_objects_missing");
  assert.equal(result.verified, false);
  assert.equal(result.migrationEnabled, false);
});
