// Pure UI-to-backend mapping; no filesystem writes or installation authorization.
export function previewArguments({ setupMode, advancedSource, defaults, installDir, dataDir, configText }) {
  if (!defaults || typeof defaults.installDir !== "string" || typeof defaults.dataDir !== "string" ||
      !defaults.installDir || !defaults.dataDir) {
    throw new Error("Default configuration unavailable");
  }
  if (setupMode === "standard") {
    return { installDir: defaults.installDir, dataDir: defaults.dataDir, configText: null };
  }
  if (setupMode !== "advanced") throw new Error("Unknown setup mode");
  if (advancedSource === "config") {
    return { installDir: defaults.installDir, dataDir: defaults.dataDir, configText };
  }
  if (advancedSource === "defaults") {
    return { installDir, dataDir, configText: null };
  }
  throw new Error("Unknown advanced configuration source");
}
