import test from "node:test";
import assert from "node:assert/strict";
import { databaseReviewEvidence, DATABASE_REVIEW_CONTRACT } from "./database-review-evidence.js";
import { ALPHA_REQUIRED_TABLES } from "./legacy-schema.js";

function source() {
  return {
    integrityOk: true, foreignKeysOk: true, foreignKeyViolations: 0,
    applicationId: 0, userVersion: 0, schemaObjects: [],
    tables: ALPHA_REQUIRED_TABLES.map(name=>({name})),
    registeredMapping: {
      recognized: true, reason: "registered_alpha_column_signatures_verified",
      matchedTableCount: 27, matchedColumnCount: 111,
      missingTables: [], incompatibleTables: [], extensionTables: [],
      migrationEnabled: false
    },
    registeredSchemaObjects: {
      verified: true, reason: "registered_alpha_schema_objects_verified",
      expectedSchemaEntryCount: 58, matchedSchemaEntryCount: 58,
      expectedIndexCount: 31, missingObjects: [], extraObjects: [],
      incompatibleObjects: [], migrationEnabled: false
    }
  };
}
test("validated plan includes both schema proofs and an unambiguous review contract",()=>{
  const evidence=databaseReviewEvidence(source());
  assert.equal(evidence.reviewContract,DATABASE_REVIEW_CONTRACT);
  assert.equal(evidence.schemaAssessment.recognized,true);
  assert.equal(evidence.schemaObjectAssessment.verified,true);
  assert.equal(evidence.schemaObjectAssessment.reason,
    "registered_alpha_schema_objects_verified");
  assert.equal(evidence.schemaObjectAssessment.expectedSchemaEntryCount,58);
  assert.equal(evidence.schemaObjectAssessment.expectedIndexCount,31);
  assert.equal(evidence.schemaObjectAssessment.migrationEnabled,false);
});

test("missing object proof is explicit, never silently omitted or promoted",()=>{
  const missing=source();delete missing.registeredSchemaObjects;
  const evidence=databaseReviewEvidence(missing);
  assert.equal(Object.hasOwn(evidence,"schemaObjectAssessment"),true);
  assert.equal(evidence.schemaObjectAssessment.verified,false);
  assert.equal(evidence.schemaObjectAssessment.reason,"registered_schema_object_audit_unavailable");
  assert.equal(evidence.schemaObjectAssessment.migrationEnabled,false);
  const empty=databaseReviewEvidence(null);
  assert.equal(empty.schemaAssessment,null);
  assert.equal(empty.schemaObjectAssessment,null);
});
