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
  return {
    status: value.status,
    operationId: value.operationId ?? null,
    message: statuses[value.status],
    automaticRetryPermitted: false,
    automaticDeletePermitted: false,
    installationEnabled: false
  };
}
