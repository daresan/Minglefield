// Explicit optional component selection for the existing Rust v1/v2 plan contract.
// No component is installed by selecting it here.
const FIELDS = ["install_optional_conda", "install_optional_comfyui", "explicit_optional_consent",
  "install_optional_git", "install_optional_gh", "offer_gh_login",
  "consent_git", "consent_gh", "consent_login"];

export function optionalSelection(values) {
  const result = {};
  for (const field of FIELDS) result[field] = values[field] === true;
  if ((result.install_optional_conda || result.install_optional_comfyui) && !result.explicit_optional_consent)
    throw new Error("Conda and ComfyUI require explicit optional-runtime consent.");
  for (const [selection, consent] of [
    ["install_optional_git", "consent_git"], ["install_optional_gh", "consent_gh"],
    ["offer_gh_login", "consent_login"]
  ]) if (result[selection] && !result[consent]) throw new Error(selection + " requires separate consent.");
  return result;
}

export function optionalPlanArguments(args, selection, setupMode, advancedSource) {
  const options = optionalSelection(selection);
  const any = Object.values(options).some(Boolean);
  if (!any) return args;
  if (setupMode === "advanced" && advancedSource === "config") {
    // Never override the user's versioned configuration silently.
    throw new Error("Optional selections conflict with the selected versioned configuration. Update the v2 configuration explicitly or clear the optional selections.");
  }
  if (!args.installDir || !args.dataDir) throw new Error("Effective installation paths are missing.");
  const config = [
    "version=2", "install_dir=" + args.installDir, "data_dir=" + args.dataDir,
    ...FIELDS.map(field => field + "=" + String(options[field]))
  ];
  return { ...args, configText: config.join("\n") };
}
