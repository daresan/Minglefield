/**
 * UI boundary for the consented files-only Alpha application copy.
 * No SQLCipher or sign-in credentials are inputs to this operation.
 * Native Rust performs the actual path and digest checks.
 */
const ACK = "INSTALL MINGLEFIELD ALPHA FILES";
const STATUS = "alpha_application_files_installed";
const RESULT_FIELDS = [
  "status", "installDir", "installedEntries",
  "hostProvisioningEnabled", "applicationLaunchEnabled"
];
export function prepareAlphaApplicationInstall({ installDir, confirmation }) {
  if (typeof installDir !== "string" || !installDir.trim() ||
      installDir.includes("\u0000")) {
    throw new Error("Ein neuer, gültiger Installationspfad ist erforderlich.");
  }
  if (confirmation !== ACK) {
    throw new Error("Die separate Bestätigung für das Kopieren der Anwendung fehlt.");
  }
  return { installDir: installDir.trim(), confirmation: ACK };
}
export function verifyAlphaApplicationInstallResult(response) {
  if (!response || typeof response !== "object" || Array.isArray(response) ||
      Object.keys(response).length !== RESULT_FIELDS.length ||
      Object.keys(response).some(key => !RESULT_FIELDS.includes(key))) {
    throw new Error("Unerwartete Antwort bei der Installation der Alpha-Dateien.");
  }
  if (response.status !== STATUS ||
      typeof response.installDir !== "string" || !response.installDir ||
      !Number.isSafeInteger(response.installedEntries) ||
      response.installedEntries <= 0 ||
      response.hostProvisioningEnabled !== false ||
      response.applicationLaunchEnabled !== false) {
    throw new Error("Die Anwendungsinstallation ist nicht als Dateienkopie verifiziert.");
  }
  return {
    status: STATUS, installDir: response.installDir,
    installedEntries: response.installedEntries
  };
}
