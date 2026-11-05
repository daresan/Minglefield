import { validateDestinationPassword } from "./database-password-policy.js";

export function selectTemporaryCopyCredentials({
  newPassword, confirmation, existingSourcePassword, rehearsalSourcePassword
}) {
  const policy = validateDestinationPassword(newPassword, confirmation);
  if (!policy.valid) throw new Error("Step 3: " + policy.message);
  return {
    newPassword,
    existingPassword: rehearsalSourcePassword || existingSourcePassword
  };
}

// Host UI must never promote a temporary encrypted file to the permanent destination.
export function assessTemporaryDiskCopy(preview, rehearsal) {
  if (!rehearsal || !Number.isSafeInteger(rehearsal.verifiedChanges) ||
      preview?.status !== "temporary_encrypted_copy_verified" ||
      preview.sourceIntegrityVerified !== true ||
      preview.fullSourceCopyVerified !== true ||
      preview.temporaryEncryptedCopyVerified !== true ||
      preview.ciphertextHeaderVerified !== true ||
      preview.wrongKeyRejected !== true ||
      preview.fullDiskCopyVerified !== true ||
      preview.stagedValuesMatchCiphertext !== true ||
      !Number.isSafeInteger(preview.verifiedStagedChanges) ||
      preview.verifiedStagedChanges !== rehearsal.verifiedChanges ||
      preview.temporaryFilesRemoved !== true ||
      preview.destinationCreated !== false ||
      preview.encryptedDestinationVerified !== false ||
      preview.executionEnabled !== false ||
      !Number.isSafeInteger(preview.checkedRows) ||
      !Number.isSafeInteger(preview.checkedTables) ||
      !Number.isSafeInteger(preview.checkedSchemaEntries) ||
      preview.checkedRows !== rehearsal.verifiedRowCount ||
      preview.checkedTables !== rehearsal.verifiedTableCount ||
      preview.checkedSchemaEntries !== rehearsal.verifiedSchemaEntryCount) {
    throw new Error("Temporary SQLCipher disk proof did not meet the non-execution requirements");
  }
  return {
    status: preview.status,
    temporaryEncryptedCopyVerified: true,
    ciphertextHeaderVerified: true,
    wrongKeyRejected: true,
    fullDiskCopyVerified: true,
    verifiedStagedChanges: preview.verifiedStagedChanges,
    stagedValuesMatchCiphertext: true,
    checkedRows: preview.checkedRows,
    checkedTables: preview.checkedTables,
    checkedSchemaEntries: preview.checkedSchemaEntries,
    temporaryFilesRemoved: true,
    destinationCreated: false,
    encryptedDestinationVerified: false,
    executionEnabled: false
  };
}
