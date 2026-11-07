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

/** Read-only classification of the already verified, typed data-review rows.
 * Migrated sessions/password verifiers and Host grants belong to the app.
 * This UI helper never returns secret cell contents or authorizes Host claims.
 */
export function classifyImportedAlphaAuthorization(review) {
  if (!review || !Array.isArray(review.tables)) return "unverified";
  const tables = new Map(review.tables.map(table => [table.name, table]));
  const users = tables.get("alpha_users");
  const owners = tables.get("sec01_host_owners");
  const executors = tables.get("alpha_executor_hosts");
  for (const [table, required] of [
    [users, ["user_id"]],
    [owners, ["host_id", "owner_id"]],
    [executors, ["host_id", "operator_id"]]
  ]) {
    if (!table || !Array.isArray(table.columns) || !Array.isArray(table.rows) ||
        !required.every(name => table.columns.includes(name))) {
      return "unverified";
    }
  }
  // There may be non-mingleadmin owners, token-only legacy users and remote
  // Hosts. Their existing rights are *not* a request to recreate local rights.
  if (owners.rows.length > 0 && executors.rows.length > 0) {
    return "existing_host_authorization";
  }
  if (users.rows.length > 0 || owners.rows.length > 0 ||
      executors.rows.length > 0) {
    return "existing_identity_or_host";
  }
  return "empty_first_run";
}
