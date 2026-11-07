/** Private current-session local Host activation UI contract.
 *  These checks improve UX; only the native Tauri in-memory proof state
 *  authorizes the privileged first-run operation.
 */
const RESPONSE = [
  "status", "loginUserId", "localHostId",
  "remoteHostAuthorityGranted", "applicationLaunchEnabled"
];
export function prepareLocalFirstRun({
  reviewedCopy, installedFiles, currentDestination,
  databasePassword, loginUserId, loginPassword, repeatPassword,
  consent
}) {
  if (reviewedCopy?.status !== "experimental_encrypted_copy_created" ||
      reviewedCopy.destinationPath !== currentDestination ||
      installedFiles?.status !== "alpha_application_files_installed") {
    throw new Error("Erst die aktuelle Datenbankkopie und Alpha-Anwendung installieren.");
  }
  if (!consent) {
    throw new Error("Die Zustimmung zur lokalen Host-Aktivierung fehlt.");
  }
  if (typeof loginUserId !== "string" ||
      !/^[a-zA-Z0-9._-]{1,128}$/.test(loginUserId)) {
    throw new Error("Der Loginname darf nur Buchstaben, Zahlen, Punkt, _ und - enthalten.");
  }
  if (typeof loginPassword !== "string" ||
      loginPassword.length < 12 || loginPassword.length > 256 ||
      loginPassword !== repeatPassword ||
      loginPassword === databasePassword ||
      typeof databasePassword !== "string" || !databasePassword) {
    throw new Error("Loginpasswort (12–256 Zeichen) getrennt vom SQLCipher-Passwort festlegen und bestätigen.");
  }
  return {
    loginUserId, loginPassword, databasePassword,
    confirmation: "ACTIVATE LOCAL HOST ADMIN"
  };
}

export function verifyLocalFirstRunResult(response, requestedUser) {
  if (!response || typeof response !== "object" ||
      Array.isArray(response) ||
      Object.keys(response).length !== RESPONSE.length ||
      Object.keys(response).some(key => !RESPONSE.includes(key)) ||
      response.status !== "local_host_admin_created" ||
      response.loginUserId !== requestedUser ||
      typeof response.localHostId !== "string" ||
      !/^local\.[0-9a-f]{32}$/.test(response.localHostId) ||
      response.remoteHostAuthorityGranted !== false ||
      response.applicationLaunchEnabled !== false) {
    throw new Error("Die Antwort bestätigt keine autorisierte lokale Erstaktivierung.");
  }
  return {
    loginUserId: response.loginUserId,
    localHostId: response.localHostId
  };
}
