import test from "node:test";
import assert from "node:assert/strict";
import { effectiveReviewPaths, replaceVersionedPath, versionedPath } from "./review-settings.js";

const defaults = { installDir: "/standard/app", dataDir: "/standard/data" };
const configText = "version=2\ninstall_dir=/old/app\ndata_dir=/old/data\ninstall_optional_conda=false\nexplicit_optional_consent=false";
const base = { setupMode: "advanced", advancedSource: "config", defaults,
  installDir: "/hidden/custom", dataDir: "/hidden/data", configText };

test("review displays effective paths, not hidden advanced field values", () => {
  assert.deepEqual(effectiveReviewPaths({ ...base, setupMode: "standard" }), defaults);
  assert.deepEqual(effectiveReviewPaths(base), { installDir: "/old/app", dataDir: "/old/data" });
  assert.deepEqual(effectiveReviewPaths({ ...base, advancedSource: "defaults" }),
    { installDir: "/hidden/custom", dataDir: "/hidden/data" });
});

test("explicit standard correction remains effective without changing setup mode", () => {
  assert.deepEqual(effectiveReviewPaths({ ...base, setupMode: "standard",
    standardOverrides: { installDir: "/corrected/app", dataDir: null } }),
    { installDir: "/corrected/app", dataDir: "/standard/data" });
});

test("versioned config correction preserves optional component and consent keys", () => {
  const updated = replaceVersionedPath(configText, "data_dir", "/corrected/data");
  assert.equal(versionedPath(updated, "data_dir"), "/corrected/data");
  assert.equal(versionedPath(updated, "install_dir"), "/old/app");
  assert.ok(updated.includes("install_optional_conda=false"));
  assert.ok(updated.includes("explicit_optional_consent=false"));
  assert.throws(() => replaceVersionedPath(configText + "\ndata_dir=/duplicate", "data_dir", "/new"));
  assert.throws(() => replaceVersionedPath("version=2", "data_dir", "/new"));
  assert.throws(() => replaceVersionedPath(configText, "data_dir", " "));
});
