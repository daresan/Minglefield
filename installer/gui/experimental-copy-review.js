// Pure UI eligibility guard for the controlled Alpha SQLCipher copy.
// The Rust core independently enforces consent and backup verification.
export const EXPERIMENTAL_COPY_CONFIRMATION = "CREATE EXPERIMENTAL ENCRYPTED COPY";

export function validateExperimentalCopyRequest({
  sourcePath, destinationPath, backupPath, confirmation,
  verifiedRehearsal, temporaryProof, stagedCorrections,
  credentialsValid
}) {
  if (!sourcePath || !destinationPath) {
    throw new Error("Choose a reviewed source and a new destination filename.");
  }
  if (!verifiedRehearsal || verifiedRehearsal.sourcePath !== sourcePath ||
      verifiedRehearsal.destinationPath !== destinationPath ||
      verifiedRehearsal.fullDataCopyVerified !== true ||
      verifiedRehearsal.sourcePreserved !== true) {
    throw new Error("Complete the migration rehearsal for this exact source and destination.");
  }
  if (!temporaryProof || temporaryProof.temporaryEncryptedCopyVerified !== true ||
      temporaryProof.stagedValuesMatchCiphertext !== true ||
      temporaryProof.temporaryFilesRemoved !== true ||
      temporaryProof.destinationCreated !== false) {
    throw new Error("Complete the current encrypted temporary-copy verification first.");
  }
  if (!Array.isArray(stagedCorrections) ||
      stagedCorrections.length !== verifiedRehearsal.verifiedChanges ||
      stagedCorrections.length !== temporaryProof.verifiedStagedChanges) {
    throw new Error("Staged data corrections changed; repeat the review.");
  }
  if (!credentialsValid) {
    throw new Error("Confirm the valid destination SQLCipher password.");
  }
  if (!backupPath || !backupPath.trim()) {
    throw new Error("Select a pre-existing independently created source backup.");
  }
  if (confirmation !== EXPERIMENTAL_COPY_CONFIRMATION) {
    throw new Error("Type the complete experimental-copy confirmation phrase.");
  }
  return { sourcePath, destinationPath, backupPath: backupPath.trim(),
    confirmation, corrections: stagedCorrections };
}
