// Only present evidence; never derive a permission to retry, delete,
// install or activate a Host from a saved recovery receipt.
const statuses = Object.freeze({
  no_recorded_operation: "Kein Recovery-Beleg und keine Zieldatei erfasst. Dies ist keine Freigabe für einen erneuten Schreibversuch.",
  unrecorded_destination: "Eine Zieldatei existiert ohne gültige Vorgangsreservierung. Manuelle Prüfung notwendig; nicht überschreiben.",
  reserved_without_destination: "Der Zielpfad ist durch einen Recovery-Beleg reserviert, aber die finale Datenbank fehlt. Nicht erneut starten oder löschen.",
  published_content_matches_untrusted_receipt: "Beleg, Quelldaten, Backup und verschlüsselte Zieldatei stimmen überein. Dies ist keine Installations- oder Recovery-Autorisierung.",
  manual_review_required: "Recovery-Beleg, Inhalt oder Eingaben konnten nicht gemeinsam verifiziert werden. Manuelle Prüfung erforderlich."
});

export function assessReadOnlyRecoveryStatus(value, { mode = "full" } = {}) {
  if (mode !== "full" && mode !== "reservation_only") {
    throw new Error("Unknown recovery inspection scope.");
  }
  if (!value || !Object.hasOwn(statuses, value.status) ||
      value.automaticRetryPermitted !== false ||
      value.automaticDeletePermitted !== false ||
      value.installationEnabled !== false ||
      !(value.operationId == null ||
        (typeof value.operationId === "string" && /^[0-9a-f]{32}$/.test(value.operationId)))) {
    throw new Error("Unexpected recovery response; no recovery action is permitted.");
  }
  // The backend's read-only IPC envelope is intentionally closed. A new
  // field, even an apparently harmless boolean, needs an explicit security
  // review before this UI can interpret it: silently accepting additional
  // capability fields could turn future schema drift into recovery authority.
  const allowedFields = [
    "status", "operationId", "automaticRetryPermitted",
    "automaticDeletePermitted", "installationEnabled"
  ];
  if (Reflect.ownKeys(value).some(name => !allowedFields.includes(name))) {
    throw new Error("Unexpected recovery response field; manual review required.");
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
  // The destination-only pass never verifies DB contents, and must not
  // present a forged or newly introduced "verified ciphertext" response.
  if (mode === "reservation_only" &&
      value.status === "published_content_matches_untrusted_receipt") {
    throw new Error("Content verification requires the full recovery inspection.");
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
