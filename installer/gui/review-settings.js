// Preview-only path resolution and editing for the existing five-step wizard.
// Preserve the selected setup mode and all non-path versioned configuration keys.
export function versionedPath(text, key) {
  const values = text.split(/\r?\n/).map(line => line.trim())
    .filter(line => line && line.split("=", 1)[0].trim() === key)
    .map(line => line.slice(line.indexOf("=") + 1).trim());
  if (values.length !== 1) throw new Error("Expected exactly one " + key + " in versioned configuration.");
  return values[0];
}

export function replaceVersionedPath(text, key, value) {
  if (key !== "install_dir" && key !== "data_dir") throw new Error("Unknown configuration path key.");
  if (!value.trim()) throw new Error(key + " cannot be empty.");
  // Detect missing/duplicate keys before editing. The Rust parser remains authoritative.
  versionedPath(text, key);
  return text.split(/\r?\n/).map(line => {
    const index = line.indexOf("=");
    return index !== -1 && line.slice(0, index).trim() === key
      ? key + "=" + value
      : line;
  }).join("\n");
}

export function effectiveReviewPaths({ setupMode, advancedSource, defaults, installDir, dataDir, configText, standardOverrides }) {
  if (!defaults) throw new Error("Installation defaults not available.");
  if (setupMode === "standard") {
    return { installDir: standardOverrides?.installDir ?? defaults.installDir,
      dataDir: standardOverrides?.dataDir ?? defaults.dataDir };
  }
  if (setupMode !== "advanced") throw new Error("Unknown setup mode.");
  if (advancedSource === "defaults") return { installDir, dataDir };
  if (advancedSource === "config") return {
    installDir: versionedPath(configText, "install_dir"),
    dataDir: versionedPath(configText, "data_dir")
  };
  throw new Error("Unknown advanced configuration source.");
}
