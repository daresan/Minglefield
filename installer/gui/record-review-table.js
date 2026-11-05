// Tabular display of every field in the vetted application-record readers.
// Edits are dispatched only for already-approved correction fields. Protected
// columns are displayed as text and never routed into the migration stager.
const text = (name, label, maxLength) => ({ name, label, editor: "text", maxLength });
const toggle = (name, label) => ({ name, label, editor: "checkbox" });
const locked = (name, label) => ({ name, label });
export const REVIEW_COLUMNS = Object.freeze({
  users: [locked("userId", "User ID"), toggle("disabled", "Disabled")],
  agents: [locked("agentId", "Agent ID"), locked("userId", "Owner"),
    toggle("disabled", "Disabled")],
  hosts: [locked("hostId", "Host ID"), locked("ownerId", "Owner")],
  hostRuntimes: [locked("hostId", "Host ID"), locked("runtimeId", "Runtime ID"),
    locked("runtimeType", "Type"), locked("endpoint", "Endpoint"),
    locked("enabled", "Enabled"), locked("inputFolder", "Input folder")],
  gitProfiles: [locked("hostId", "Host ID"), locked("profileId", "Profile ID"),
    locked("ownerId", "Owner"), text("label", "Profile label", 120),
    locked("authMethod", "Authentication"), locked("gitExecutable", "Git executable"),
    text("authorName", "Author name", 256), text("authorEmail", "Author email", 256)],
  effects: [locked("hostId", "Host ID"), locked("effectId", "Effect ID"),
    text("description", "Description", 256), toggle("enabled", "Enabled")],
  alphaJobs: [locked("jobId", "Job ID"), locked("userId", "User ID"),
    locked("agentId", "Agent ID")],
  hostJobs: [locked("jobId", "Job ID"), locked("hostId", "Host ID"),
    locked("effectId", "Effect ID"), locked("requestedBy", "Requester"),
    locked("state", "State")],
  games: [locked("projectId", "Project ID"), locked("hostId", "Host ID"),
    locked("ownerId", "Owner"), text("name", "Name", 120),
    text("repositoryRoot", "Repository", 1024),
    text("jobAttachmentsRoot", "Attachments", 1024),
    text("outputRoot", "Output", 1024),
    locked("settingsRevision", "Settings revision")]
});

export function appendReviewTable(root, category, rows, { onEdit, onError } = {}) {
  const columns = REVIEW_COLUMNS[category];
  if (!columns || !Array.isArray(rows) || rows.length > 500) {
    throw new Error("Invalid review table");
  }
  const heading = document.createElement("h4");
  heading.textContent = category + " (" + rows.length + ")";
  root.append(heading);
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.textContent = "No records found in this table.";
    root.append(empty);
    return;
  }
  const frame = document.createElement("div");
  frame.className = "data-table-scroll";
  const table = document.createElement("table");
  table.className = "data-review-table";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const col of columns) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = col.label + (col.editor ? " (editable)" : " (protected)");
    headRow.append(cell);
  }
  thead.append(headRow);
  table.append(thead);
  const tbody = document.createElement("tbody");
  for (const row of rows) {
    if (!row || columns.some(({name}) => !(name in row))) {
      throw new Error("Missing verified review field in " + category);
    }
    const line = document.createElement("tr");
    for (const column of columns) {
      const cell = document.createElement("td");
      const value = row[column.name];
      if (!column.editor) {
        cell.textContent = value == null || value === "" ? "—" : String(value);
      } else {
        if (typeof onEdit !== "function") throw new Error("Missing correction handler");
        const input = document.createElement("input");
        input.type = column.editor;
        if (column.maxLength) input.maxLength = column.maxLength;
        input.setAttribute("aria-label", category + " " + column.label + " " +
          String(row[columns[0].name]));
        if (column.editor === "checkbox") {
          input.checked = value;
          input.style.width = "auto";
        } else {
          input.value = value;
        }
        input.addEventListener("change", () => {
          try {
            const candidate = column.editor === "checkbox" ? input.checked : input.value;
            const accepted = onEdit(row, column.name, candidate);
            if (typeof accepted !== typeof candidate) throw new Error("Invalid correction result");
            row[column.name] = accepted;
          } catch (error) {
            if (typeof onError === "function") onError(error);
          }
          if (column.editor === "checkbox") input.checked = row[column.name];
          else input.value = row[column.name];
        });
        cell.append(input);
      }
      line.append(cell);
    }
    tbody.append(line);
  }
  table.append(tbody);
  frame.append(table);
  root.append(frame);
}
