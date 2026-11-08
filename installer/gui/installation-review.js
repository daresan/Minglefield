/** Product-facing single-consent installer review. Filesystem/DB validation
 * stays in the native installer engine, never as manual wizard tests. */
export const WIZARD_PAGES = [
  "Willkommen", "Installationsmodus", "Speicherorte",
  "Datenbank", "Host-Administrator", "Zusammenfassung"
];
export function validateInstallSelections(form) {
  if (!form || typeof form !== "object") return "Einstellungen fehlen.";
  for (const name of ["installDir", "databasePath", "databasePassword"]) {
    if (typeof form[name] !== "string" || !form[name].trim()) {
      return name === "databasePassword" ? "Bitte SQLCipher-Passwort angeben." :
        "Bitte Installations- und Datenbankpfad angeben.";
    }
  }
  if (form.databasePassword !== form.databasePasswordConfirmation) {
    return "SQLCipher-Passwörter stimmen nicht überein.";
  }
  if (form.loginPassword !== form.loginPasswordConfirmation) {
    return "Loginpasswörter stimmen nicht überein.";
  }
  if (form.loginPassword &&
      (form.loginPassword.length < 12 ||
       form.loginPassword.length > 256 ||
       form.loginPassword === form.databasePassword)) {
    return "Loginpasswort: mindestens 12 Zeichen, verschieden vom Datenbankpasswort.";
  }
  return null;
}
export function reviewRows(form) {
  return [
    ["Modus", form.mode === "advanced" ? "Erweitert" : "Standard"],
    ["Anwendung", form.installDir],
    ["Datenbank", form.databasePath],
    ["Datenquelle", form.sourceDatabase || "Neue verschlüsselte Datenbank"],
    ["SQLCipher-Passwort", form.databasePassword ? "Festgelegt" : "Fehlt"],
    ["Host-Administrator", "mingleadmin (vorhandenen Zugang beibehalten)"],
    ["Neues Loginpasswort", form.loginPassword ? "Festgelegt (nur bei Neuanlage)" : "Vorhandenen Zugang verwenden"],
    ["Anwendungsstart", "Automatisch nach erfolgreicher Installation"]
  ];
}
export function isExistingTargetWarning(error) {
  return String(error).startsWith("INSTALL_WARNING_EXISTING:");
}
export function installationRequest(form, continueExisting = false) {
  return {
    installDir: form.installDir, databasePath: form.databasePath,
    sourceDatabase: form.sourceDatabase || null,
    sourcePassword: form.sourcePassword,
    databasePassword: form.databasePassword,
    loginPassword: form.loginPassword,
    loginPasswordConfirmation: form.loginPasswordConfirmation,
    approved: true, continueExisting
  };
}
export function verifyInstalledRunning(result) {
  if (!result || result.status !== "minglefield_installed_and_running" ||
      result.encryptedDatabaseVerified !== true ||
      result.nativeApplicationRunning !== true ||
      result.localAdminUser !== "mingleadmin" ||
      typeof result.installedApplication !== "string" ||
      typeof result.encryptedDatabase !== "string" ||
      typeof result.localHostId !== "string" ||
      !/^local\.[a-zA-Z0-9._-]+$/.test(result.localHostId) ||
      !Number.isInteger(result.nativeProcessId) || result.nativeProcessId < 1 ||
      typeof result.localUrl !== "string" ||
      !/^http:\/\/127\.0\.0\.1:[0-9]{1,5}\/$/.test(result.localUrl)) {
    throw new Error("Die native Minglefield-Installation und ihr Start wurden nicht vollständig bestätigt.");
  }
  return result;
}
