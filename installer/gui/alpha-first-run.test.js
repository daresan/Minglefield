import assert from "node:assert/strict";
import test from "node:test";
import {
  prepareLocalFirstRun, verifyLocalFirstRunResult,
  classifyImportedAlphaAuthorization, prepareInstalledNativeStart,
  verifyRunningNativeResult
} from "./alpha-first-run.js";
const fixture = {
  reviewedCopy: {
    status: "experimental_encrypted_copy_created",
    destinationPath: "/target/new-encrypted.sqlite3"
  },
  installedFiles: {
    status: "alpha_application_files_installed",
    installDir: "/opt/minglefield"
  },
  currentDestination: "/target/new-encrypted.sqlite3",
  databasePassword: "DatabaseSecret123!",
  loginUserId: "mingleadmin",
  loginPassword: "SeparateLoginSecret456!",
  repeatPassword: "SeparateLoginSecret456!",
  consent: true
};
const result = {
  status: "local_host_admin_created",
  loginUserId: "mingleadmin",
  localHostId: "local.0123456789abcdef0123456789abcdef",
  remoteHostAuthorityGranted: false,
  applicationLaunchEnabled: false
};
test("activation requires verified current-session user actions", () => {
  assert.deepEqual(prepareLocalFirstRun(fixture), {
    loginUserId: "mingleadmin",
    loginPassword: "SeparateLoginSecret456!",
    databasePassword: "DatabaseSecret123!",
    confirmation: "ACTIVATE LOCAL HOST ADMIN",
    verifyNativeStart: false
  });
  for (const change of [
    { reviewedCopy: null },
    { installedFiles: null },
    { currentDestination: "/another-target" },
    { consent: false },
    { loginPassword: fixture.databasePassword },
    { loginPassword: "short" },
    { repeatPassword: "mismatch" },
    { loginUserId: "../malformed" },
    { loginUserId: "" }
  ]) {
    assert.throws(() => prepareLocalFirstRun({ ...fixture, ...change }));
  }
});
test("native result cannot grant remote Hosts or unrequested application launch", () => {
  assert.deepEqual(verifyLocalFirstRunResult(result, "mingleadmin"), {
    loginUserId: "mingleadmin", localHostId: result.localHostId
  });
  for (const change of [
    { remoteHostAuthorityGranted: true },
    { applicationLaunchEnabled: true },
    { localHostId: "host.remote" },
    { loginUserId: "another-user" },
    { status: "granted" },
    { unknownTrustedFlag: true }
  ]) {
    assert.throws(() => verifyLocalFirstRunResult(
      { ...result, ...change }, "mingleadmin"));
  }
});

test("explicit native probe must match its reported outcome", () => {
  assert.equal(prepareLocalFirstRun({
    ...fixture, verifyNativeStart: true
  }).verifyNativeStart, true);
  const checked = { ...result, applicationLaunchEnabled: true };
  assert.deepEqual(verifyLocalFirstRunResult(
    checked, "mingleadmin", true
  ), { loginUserId: "mingleadmin", localHostId: result.localHostId });
  assert.throws(() => verifyLocalFirstRunResult(checked, "mingleadmin", false));
  assert.throws(() => verifyLocalFirstRunResult(result, "mingleadmin", true));
  assert.throws(() => prepareLocalFirstRun({
    ...fixture, verifyNativeStart: "true"
  }));
});

function authTable(name, columns, rows) {
  return {name, columns, rows: rows.map(values => ({
    rowId: null, cells: values.map(value => ({kind: "text", value}))
  }))};
}
test("existing encrypted-database authorization is retained without first-run", () => {
  const review = {tables: [
    authTable("alpha_users", ["user_id"], [["mingleadmin"], ["user.other"]]),
    authTable("alpha_executor_hosts", ["host_id", "operator_id"],
      [["host.local", "mingleadmin"], ["host.remote", "user.other"]]),
    authTable("sec01_host_owners", ["host_id", "owner_id"],
      [["host.local", "mingleadmin"], ["host.remote", "user.other"]]),
    authTable("alpha_sessions", ["token_hash", "user_id"],
      [["private-existing-hash-never-exposed", "mingleadmin"]])
  ]};
  const before = JSON.stringify(review);
  assert.equal(classifyImportedAlphaAuthorization(review),
    "existing_host_authorization");
  assert.equal(JSON.stringify(review), before);
  assert.ok(!classifyImportedAlphaAuthorization(review).includes("private"));
});
test("partial legacy account/Host data never becomes a fresh admin", () => {
  assert.equal(classifyImportedAlphaAuthorization({tables: [
    authTable("alpha_users", ["user_id"], [["mingleadmin"]])
  ]}), "existing_identity_or_host");
  assert.equal(classifyImportedAlphaAuthorization({tables: [
    authTable("sec01_host_owners", ["host_id", "owner_id"],
      [["host.local", "mingleadmin"]])
  ]}), "existing_identity_or_host");
});
test("only a verified empty authentication schema permits initial setup", () => {
  const fresh = {tables: [
    authTable("alpha_users", ["user_id"], []),
    authTable("alpha_executor_hosts", ["host_id", "operator_id"], []),
    authTable("sec01_host_owners", ["host_id", "owner_id"], [])
  ]};
  assert.equal(classifyImportedAlphaAuthorization(fresh), "empty_first_run");
  assert.equal(classifyImportedAlphaAuthorization({tables: [
    authTable("imported_data", ["value"], [["preserved"]])
  ]}), "empty_first_run");
  assert.equal(classifyImportedAlphaAuthorization(null), "unverified");
  assert.equal(classifyImportedAlphaAuthorization({tables: []}), "unverified");
  assert.equal(classifyImportedAlphaAuthorization({tables: [
    authTable("alpha_users", ["unexpected_field"], [])
  ]}), "unverified");
});

test("native running start requires session proof and a verified Host", () => {
  const selected = {
    reviewedCopy: fixture.reviewedCopy,
    installedFiles: fixture.installedFiles,
    currentDestination: fixture.currentDestination,
    databasePassword: fixture.databasePassword,
    hostReady: true
  };
  assert.deepEqual(prepareInstalledNativeStart(selected), {
    databasePassword: fixture.databasePassword,
    confirmation: "START INSTALLED MINGLEFIELD"
  });
  for (const change of [
    { reviewedCopy: null }, { installedFiles: null },
    { currentDestination: "/forged.sqlite3" }, { hostReady: false },
    { hostReady: "true" }, { databasePassword: "" }
  ]) {
    assert.throws(() => prepareInstalledNativeStart({ ...selected, ...change }));
  }
});

test("native launch response must be live loopback and deny Host claim", () => {
  const receipt = {
    status: "native_minglefield_running", bind: "127.0.0.1",
    port: 45123, processId: 2345, encryptedDatabase: true,
    hostProvisioningEnabled: false, hostClaimBootstrapEnabled: false
  };
  assert.deepEqual(verifyRunningNativeResult(receipt), {
    port: 45123, processId: 2345, url: "http://127.0.0.1:45123/"
  });
  for (const change of [
    { status: "native_minglefield_startup_verified" }, { bind: "0.0.0.0" },
    { port: 0 }, { port: 65536 }, { processId: 0 },
    { encryptedDatabase: false }, { hostProvisioningEnabled: true },
    { hostClaimBootstrapEnabled: true }, { forged: true }
  ]) {
    assert.throws(() => verifyRunningNativeResult({ ...receipt, ...change }));
  }
});
