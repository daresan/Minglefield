import test from "node:test";
import assert from "node:assert/strict";
import { previewArguments } from "./preview-arguments.js";

const defaults = { installDir: "/user/app", dataDir: "/user/data" };
const dirty = { defaults, installDir: "/custom/app", dataDir: "/custom/data", configText: "version=2\ninstall_optional_conda=true" };

test("standard mode ignores hidden advanced paths and optional component configuration", () => {
  for (const advancedSource of ["defaults", "config"]) {
    assert.deepEqual(previewArguments({ ...dirty, setupMode: "standard", advancedSource }), {
      installDir: "/user/app", dataDir: "/user/data", configText: null
    });
  }
});
test("advanced custom paths are forwarded without hidden config", () => {
  assert.deepEqual(previewArguments({ ...dirty, setupMode: "advanced", advancedSource: "defaults" }), {
    installDir: "/custom/app", dataDir: "/custom/data", configText: null
  });
});
test("advanced versioned config is forwarded without custom path overrides", () => {
  assert.deepEqual(previewArguments({ ...dirty, setupMode: "advanced", advancedSource: "config" }), {
    installDir: "/user/app", dataDir: "/user/data", configText: dirty.configText
  });
});
test("missing defaults and unknown modes fail closed", () => {
  assert.throws(() => previewArguments({ ...dirty, defaults: null, setupMode: "standard" }));
  assert.throws(() => previewArguments({ ...dirty, defaults: { installDir: "", dataDir: "" }, setupMode: "standard" }));
  assert.throws(() => previewArguments({ ...dirty, setupMode: "unexpected", advancedSource: "defaults" }));
  assert.throws(() => previewArguments({ ...dirty, setupMode: "advanced", advancedSource: "unexpected" }));
});
