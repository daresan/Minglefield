// Validated, in-memory corrections to allowlisted Minglefield Alpha fields.
// Identity, ownership, execution state, paths and permissions are read-only.
const id = value => typeof value === "string" && /^[A-Za-z0-9._-]{1,128}$/.test(value);
const absolutePath = value => typeof value === "string" && value.length > 0 &&
  value.length <= 1024 && !value.includes("\0") &&
  (value.startsWith("/") || /^[A-Za-z]:[\\/]/.test(value) ||
    /^\\\\[^\\]+\\[^\\]+/.test(value)) &&
  !/(^|[\\/])\.\.([\\/]|$)/.test(value);
const editableFields = {
  agents: ["disabled"],
  gitProfiles: ["label", "authorName", "authorEmail"],
  effects: ["description", "enabled"],
  games: ["name", "repositoryRoot", "jobAttachmentsRoot", "outputRoot"]
};
const categories = ["agents", "hosts", "hostRuntimes", "gitProfiles", "effects", "hostJobs", "games"];
const keyFor = (category, item) => category === "agents" ? item.agentId
  : category === "hosts" ? item.hostId
  : category === "hostRuntimes" ? JSON.stringify([item.hostId, item.runtimeId])
  : category === "gitProfiles" ? JSON.stringify([item.hostId, item.profileId])
  : category === "effects" ? JSON.stringify([item.hostId, item.effectId])
  : category === "hostJobs" ? item.jobId : item.projectId;

function verify(records) {
  if (!records || typeof records !== "object") throw new Error("Invalid legacy review");
  for (const category of categories) {
    if (!Array.isArray(records[category]) || records[category].length > 500) {
      throw new Error("Invalid or oversized " + category + " records");
    }
    const seen = new Set();
    for (const row of records[category]) {
      const key = keyFor(category, row);
      if (!key || seen.has(key)) throw new Error("Duplicate " + category + " identity");
      seen.add(key);
      const allowed = category === "agents" ? ["agentId","userId","disabled"]
        : category === "hosts" ? ["hostId","ownerId"]
        : category === "hostRuntimes" ? ["hostId","runtimeId","runtimeType","endpoint","enabled","inputFolder"]
        : category === "gitProfiles" ? ["hostId","profileId","ownerId","label","authMethod","gitExecutable","authorName","authorEmail"] : category === "effects" ? ["hostId","effectId","description","enabled"] : category === "hostJobs" ? ["jobId","hostId","effectId","requestedBy","state"] : ["projectId","hostId","ownerId","name","repositoryRoot","jobAttachmentsRoot","outputRoot","settingsRevision"];
      if (Object.keys(row).sort().join("|") !== allowed.sort().join("|")) throw new Error("Unexpected record fields");
      const required = category === "agents" ? ["agentId", "userId"]
        : category === "hosts" ? ["hostId", "ownerId"]
        : category === "hostRuntimes" ? ["hostId", "runtimeId"]
        : category === "gitProfiles" ? ["hostId", "profileId", "ownerId"]
        : category === "effects" ? ["hostId", "effectId"]
        : category === "hostJobs" ? ["jobId", "hostId", "effectId", "requestedBy"]
        : ["projectId", "hostId", "ownerId"];
      if (!required.every(field => id(row[field]))) throw new Error("Invalid " + category + " identity");
      if (category === "agents" && typeof row.disabled !== "boolean") {
        throw new Error("Invalid Alpha agent disabled flag");
      }
      if (category === "gitProfiles" && (
          typeof row.label !== "string" || !row.label.trim() ||
          row.label.trim() !== row.label || row.label.length > 120 ||
          typeof row.authMethod !== "string" ||
          !["local", "ssh", "credential_manager", "github_cli"].includes(row.authMethod) ||
          typeof row.gitExecutable !== "string" ||
          !row.gitExecutable.trim() || row.gitExecutable.length > 256 ||
          typeof row.authorName !== "string" || row.authorName.length > 256 ||
          typeof row.authorEmail !== "string" || row.authorEmail.length > 256)) {
        throw new Error("Invalid Git profile metadata");
      }
      if (category === "hostRuntimes" && (typeof row.runtimeType !== "string" ||
          !row.runtimeType || row.runtimeType.length > 32 ||
          typeof row.endpoint !== "string" || row.endpoint.length > 256 ||
          typeof row.enabled !== "boolean" ||
          typeof row.inputFolder !== "string" || row.inputFolder.length > 512)) {
        throw new Error("Invalid host runtime metadata");
      }
      if (category === "effects" && (typeof row.description !== "string" ||
          row.description.length > 256 || typeof row.enabled !== "boolean")) {
        throw new Error("Invalid effect fields");
      }
      if (category === "hostJobs" && (typeof row.state !== "string" || row.state.length > 128)) {
        throw new Error("Invalid host job state");
      }
      if (category === "games" && (typeof row.name !== "string" ||
          !row.name.trim() || row.name.trim().length > 120 ||
          typeof row.repositoryRoot !== "string" || !row.repositoryRoot ||
          !absolutePath(row.repositoryRoot) ||
          !absolutePath(row.jobAttachmentsRoot) ||
          !absolutePath(row.outputRoot) ||
          !Number.isSafeInteger(row.settingsRevision) || row.settingsRevision < 1)) {
        throw new Error("Invalid game project fields");
      }
    }
  }
  if (!Array.isArray(records.unavailable) || !records.unavailable.every(x => typeof x === "string")) {
    throw new Error("Invalid unavailable tables");
  }
}

export function createLegacyReview(records) {
  verify(records);
  return Object.fromEntries([...categories.map(key => [key, records[key].map(row => ({ ...row }))]),
    ["unavailable", [...records.unavailable]]]);
}

export function stageLegacyText(records, category, key, field, value) {
  if (!editableFields[category]?.includes(field) || field === "enabled" || field === "disabled" ||
      typeof value !== "string") throw new Error("Field is not editable as text");
  if (category === "effects" && value.length > 256) {
    throw new Error("Description exceeds 256 characters");
  }
  if (category === "gitProfiles") {
    if (field === "label" && (!value.trim() || value.trim().length > 120)) {
      throw new Error("Git label must contain 1–120 characters");
    }
    if (field !== "label" && value.length > 256) {
      throw new Error("Git author field exceeds 256 characters");
    }
  }
  if (category === "games") {
    if (field === "name" && (!value.trim() || value.trim().length > 120))
      throw new Error("Game name must contain 1–120 characters");
    if (field !== "name" && !absolutePath(value))
      throw new Error("Game path must be absolute, without parent traversals, and at most 1024 characters");
  }
  const next = createLegacyReview(records);
  const row = next[category].find(record => keyFor(category, record) === key);
  if (!row) throw new Error("Unknown record");
  row[field] = field === "name" || field === "label" ? value.trim() : value;
  return next;
}

export function stageLegacyToggle(records, category, key, field, value) {
  if (typeof value !== "boolean" ||
      !((category === "effects" && field === "enabled") ||
        (category === "agents" && field === "disabled"))) {
    throw new Error("Field is not editable as a toggle");
  }
  const next = createLegacyReview(records);
  const row = next[category].find(record => keyFor(category, record) === key);
  if (!row) throw new Error("Unknown record");
  row[field] = value;
  return next;
}

export function legacyCorrections(original, edited) {
  const before = createLegacyReview(original);
  const after = createLegacyReview(edited);
  if (JSON.stringify(before.unavailable) !== JSON.stringify(after.unavailable)) {
    throw new Error("Table availability cannot be changed");
  }
  const changes = [];
  for (const category of categories) {
    const originals = new Map(before[category].map(row => [keyFor(category, row), row]));
    if (originals.size !== after[category].length) throw new Error("Record count changed");
    for (const current of after[category]) {
      const key = keyFor(category, current);
      const previous = originals.get(key);
      if (!previous) throw new Error("Record identity changed");
      const editable = editableFields[category] ?? [];
      for (const [name, value] of Object.entries(previous)) {
        if (current[name] === value) continue;
        if (!editable.includes(name)) {
          throw new Error("Read-only field changed: " + name);
        }
        changes.push({ category, key, field: name, previous: value, next: current[name] });
      }
    }
  }
  return changes;
}
