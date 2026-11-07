import assert from "node:assert/strict";
import test from "node:test";
import {
  prepareLocalFirstRun, verifyLocalFirstRunResult,
  classifyImportedAlphaAuthorization
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
