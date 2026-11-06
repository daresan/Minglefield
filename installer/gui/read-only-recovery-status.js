// Only present evidence; never derive a permission to retry, delete,
// install or activate a Host from a saved recovery receipt.
const statuses = Object.freeze({
  no_recorded_operation: "Kein Recovery-Beleg und keine Zieldatei erfasst. Dies ist keine Freigabe für einen erneuten Schreibversuch.",
  unrecorded_destination: "Eine Zieldatei existiert ohne gültige Vorgangsreservierung. Manuelle Prüfung notwendig; nicht überschreiben.",
  reserved_without_destination: "Der Zielpfad ist durch einen Recovery-Beleg reserviert, aber die finale Datenbank fehlt. Nicht erneut starten oder löschen.",
  published_content_matches_untrusted_receipt: "Beleg, Quelldaten, Backup und verschlüsselte Zieldatei stimmen überein. Dies ist keine Installations- oder Recovery-Autorisierung.",
  manual_review_required: "Recovery-Beleg, Inhalt oder Eingaben konnten nicht gemeinsam verifiziert werden. Manuelle Prüfung erforderlich."
});

export function assessReadOnlyRecoveryStatus(value) {
  if (!value || !Object.hasOwn(statuses, value.status) ||
      value.automaticRetryPermitted !== false ||
      value.automaticDeletePermitted !== false ||
      value.installationEnabled !== false ||
      !(value.operationId == null ||
        (typeof value.operationId === "string" && /^[0-9a-f]{32}$/.test(value.operationId)))) {
    throw new Error("Unexpected recovery response; no recovery action is permitted.");
  }
  // Future backend fields must not silently turn this informational view
  // into an authorization-bearing response. Unknown non-capability metadata
  // is harmless, but any explicit positive mutation capability fails closed.
  const forbiddenCapabilities = [
    "executionEnabled", "migrationEnabled", "applicationInstallationEnabled",
    "hostProvisioningEnabled", "automaticResumePermitted", "automaticRollbackPermitted",
    "automaticCleanupPermitted", "receiptTrusted", "recoveryAuthorized"
  ];
  if (forbiddenCapabilities.some(name => Object.hasOwn(value, name) && value[name] !== false)) {
    throw new Error("Recovery response attempted to grant execution authority.");
  }
  // A reservation or positively matched ciphertext MUST refer to an actual
  // operation. Conversely, a state without a recorded operation cannot name
  // one. Manual-review states may contain either because corrupt receipts
  // can fail before or after extracting an operation ID.
  const requiresOperationId = value.status === "reserved_without_destination" ||
    value.status === "published_content_matches_untrusted_receipt";
  const forbidsOperationId = value.status === "no_recorded_operation" ||
    value.status === "unrecorded_destination";
  if ((requiresOperationId && value.operationId == null) ||
      (forbidsOperationId && value.operationId != null)) {
    throw new Error("Inconsistent recovery status and operation ID; manual review required.");
  }
  return {
    status: value.status,
    operationId: value.operationId ?? null,
    message: statuses[value.status],
    automaticRetryPermitted: false,
    automaticDeletePermitted: false,
    installationEnabled: false
  };
}
