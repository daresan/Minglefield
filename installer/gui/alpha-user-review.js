// Preserve Alpha user identities. Only the existing disabled flag is editable.
// The source database is never mutated by this review model.
export function createAlphaUserReview(records) {
  if (!Array.isArray(records) || records.length > 500) throw new Error("Invalid user record collection.");
  const seen = new Set();
  return records.map(record => {
    if (!record || typeof record.userId !== "string" || !record.userId ||
        typeof record.disabled !== "boolean" || seen.has(record.userId)) {
      throw new Error("Invalid or duplicate Alpha user record.");
    }
    seen.add(record.userId);
    return { userId: record.userId, disabled: record.disabled };
  });
}

export function updateAlphaUserReview(records, userId, disabled) {
  if (typeof disabled !== "boolean" || !records.some(record => record.userId === userId))
    throw new Error("Unknown user or invalid disabled value.");
  return records.map(record => record.userId === userId
    ? { ...record, disabled } : { ...record });
}

export function alphaUserCorrections(original, edited) {
  if (original.length !== edited.length) throw new Error("User count changed.");
  const before = new Map(original.map(record => [record.userId, record]));
  if (before.size !== original.length) throw new Error("Duplicate source users.");
  const seen = new Set();
  const changes = [];
  for (const record of edited) {
    if (!before.has(record.userId) || seen.has(record.userId) || typeof record.disabled !== "boolean")
      throw new Error("User identity changed or invalid record.");
    seen.add(record.userId);
    if (before.get(record.userId).disabled !== record.disabled)
      changes.push({ userId: record.userId, disabled: record.disabled });
  }
  return changes;
}
