// A named, testable contract for the VALIDATED installation plan and Step-6
// summary. This is UI evidence only, not permission to migrate or install.
import { assessLegacyAlphaSchema } from "./legacy-schema.js";
import { assessRegisteredSchemaObjects } from "./schema-object-assessment.js";

export const DATABASE_REVIEW_CONTRACT = "sqlite-existing-values-only-schema-objects-v2";

export function databaseReviewEvidence(inspection) {
  return {
    reviewContract: DATABASE_REVIEW_CONTRACT,
    schemaAssessment: inspection ? assessLegacyAlphaSchema(inspection) : null,
    // Always include this key in a validated plan. Missing backend evidence
    // reports an explicit fail-closed reason rather than silently disappearing.
    schemaObjectAssessment: inspection ? assessRegisteredSchemaObjects(inspection) : null
  };
}
