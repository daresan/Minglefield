// Validated, in-memory corrections to allowlisted Minglefield Alpha fields.
// Identity, ownership, execution state, paths and permissions are read-only.
const id = value => typeof value === "string" && /^[A-Za-z0-9._-]{1,128}$/.test(value);
const categories = ["hosts", "effects", "hostJobs", "games"];
const keyFor = (category, item) => category === "hosts" ? item.hostId
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
      const required = category === "hosts" ? ["hostId", "ownerId"]
        : category === "effects" ? ["hostId", "effectId"]
        : category === "hostJobs" ? ["jobId", "hostId", "effectId", "requestedBy"]
        : ["projectId", "hostId", "ownerId"];
      if (!required.every(field => id(row[field]))) throw new Error("Invalid " + category + " identity");
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
          row.repositoryRoot.length > 1024)) {
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
  const allowed = { effects: "description", games: "name" };
  if (allowed[category] !== field || typeof value !== "string") {
    throw new Error("Field is not editable");
  }
  if (category === "effects" && value.length > 256) throw new Error("Description exceeds 256 characters");
  if (category === "games" && (!value.trim() || value.trim().length > 120)) {
    throw new Error("Game name must contain 1–120 characters");
  }
  const next = createLegacyReview(records);
  const row = next[category].find(record => keyFor(category, record) === key);
  if (!row) throw new Error("Unknown record");
  row[field] = category === "games" ? value.trim() : value;
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
      const field = category === "effects" ? "description" : category === "games" ? "name" : null;
      for (const [name, value] of Object.entries(previous)) {
        if (name !== field && current[name] !== value) {
          throw new Error("Read-only field changed: " + name);
        }
      }
      if (field && current[field] !== previous[field]) {
        changes.push({ category, key, field, previous: previous[field], next: current[field] });
      }
    }
  }
  return changes;
}
