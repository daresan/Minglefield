import assert from "node:assert/strict";
import test from "node:test";
import {
  prepareAlphaApplicationInstall,
  verifyAlphaApplicationInstallResult
} from "./alpha-application-install.js";
const valid = {
  status: "alpha_application_files_installed",
  installDir: "/existing/new-minglefield-alpha",
  installedEntries: 123,
  hostProvisioningEnabled: false,
  applicationLaunchEnabled: false
};
test("only explicit file-install consent reaches native invocation", () => {
  assert.deepEqual(prepareAlphaApplicationInstall({
    installDir: "  /existing/new-minglefield-alpha  ",
    confirmation: "INSTALL MINGLEFIELD ALPHA FILES"
  }), { installDir: "/existing/new-minglefield-alpha", confirmation: "INSTALL MINGLEFIELD ALPHA FILES" });
  for (const confirmation of ["", "INSTALL MINGLEFIELD ALPHA", "install minglefield alpha files"]) {
    assert.throws(() => prepareAlphaApplicationInstall({
      installDir: "/valid", confirmation
    }));
  }
  assert.throws(() => prepareAlphaApplicationInstall({
    installDir: "  ", confirmation: "INSTALL MINGLEFIELD ALPHA FILES"
  }));
  assert.throws(() => prepareAlphaApplicationInstall({
    installDir: "/hello\u0000world",
    confirmation: "INSTALL MINGLEFIELD ALPHA FILES"
  }));
});
test("files-only response never grants first-run or launch authority", () => {
  assert.deepEqual(verifyAlphaApplicationInstallResult(valid), {
    status: valid.status, installDir: valid.installDir,
    installedEntries: valid.installedEntries
  });
  for (const changed of [
    { ...valid, hostProvisioningEnabled: true },
    { ...valid, applicationLaunchEnabled: true },
    { ...valid, installedEntries: 0 },
    { ...valid, installedEntries: "123" },
    { ...valid, status: "installed" },
    { ...valid, unexpectedAuthorization: true },
    { ...valid, installDir: "" },
  ]) {
    assert.throws(() => verifyAlphaApplicationInstallResult(changed));
  }
  assert.throws(() => verifyAlphaApplicationInstallResult(null));
});
