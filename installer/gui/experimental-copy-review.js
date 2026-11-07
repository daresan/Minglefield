// Pure UI eligibility guard for the controlled Alpha SQLCipher copy.
// The Rust core independently enforces consent and backup verification.
export const EXPERIMENTAL_COPY_CONFIRMATION = "CREATE EXPERIMENTAL ENCRYPTED COPY";

export function validateExperimentalCopyRequest({
  sourcePath, destinationPath, backupPath, confirmation,
  stagedCorrections,
  credentialsValid
}) {
  if (!sourcePath || !destinationPath) {
    throw new Error("Choose a reviewed source and a new destination filename.");
  }
  // Optional development rehearsals must not block actual execution.
  // Native SQLCipher execution repeats source, backup and ciphertext checks.
  if (!Array.isArray(stagedCorrections)) {
    throw new Error("Invalid staged changes.");
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
