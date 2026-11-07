import assert from "node:assert/strict";
import test from "node:test";
import {
  prepareLocalFirstRun, verifyLocalFirstRunResult
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
    confirmation: "ACTIVATE LOCAL HOST ADMIN"
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
test("native result cannot grant remote Hosts or application launch", () => {
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
