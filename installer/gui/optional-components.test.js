import test from "node:test";
import assert from "node:assert/strict";
import { optionalSelection, optionalPlanArguments } from "./optional-components.js";

const base = { installDir: "/install", dataDir: "/data", configText: null };
test("all optional components default to disabled and leave v1 plan unchanged", () => {
  const result = optionalPlanArguments(base, {}, "standard", "defaults");
  assert.deepEqual(result, base);
});
test("independent Git, gh, Conda and ComfyUI consent is required", () => {
  for (const [component, consent] of [
    ["install_optional_git", "consent_git"],
    ["install_optional_gh", "consent_gh"],
    ["offer_gh_login", "consent_login"],
    ["install_optional_conda", "explicit_optional_consent"],
    ["install_optional_comfyui", "explicit_optional_consent"]
  ]) {
    assert.throws(() => optionalSelection({ [component]: true }));
    assert.equal(optionalSelection({ [component]: true, [consent]: true })[component], true);
  }
});
test("selected components are represented by a complete strict v2 config", () => {
  const plan = optionalPlanArguments(base,
    { install_optional_git: true, consent_git: true, install_optional_comfyui: true,
      explicit_optional_consent: true }, "standard", "defaults");
  assert.match(plan.configText, /^version=2\n/);
  assert.match(plan.configText, /install_optional_git=true/);
  assert.match(plan.configText, /install_optional_comfyui=true/);
  assert.match(plan.configText, /install_optional_gh=false/);
  assert.match(plan.configText, /consent_git=true/);
});
test("versioned advanced configuration is never silently overridden", () => {
  assert.throws(() => optionalPlanArguments(
    { ...base, configText: "version=2\n..." },
    { install_optional_git: true, consent_git: true }, "advanced", "config"));
});
