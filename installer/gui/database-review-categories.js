// Verified Alpha SQLite table-family mapping for the five installer review tabs.
// Unrecognized extension tables stay accessible under "Sonstige DB-Tabellen".
// This is presentation only: the underlying typed SQLite correction path is shared.
export const REVIEW_CATEGORIES = Object.freeze(["login", "hosts", "effects", "jobs", "games", "all"]);

export const TABLE_FAMILIES = Object.freeze({
  login: Object.freeze([
    "alpha_users", "alpha_agents", "alpha_passwords",
    "alpha_sessions", "alpha_invites", "alpha_agent_grants"
  ]),
  hosts: Object.freeze([
    "alpha_executor_hosts", "alpha_agent_host_assignments",
    "sec01_host_owners", "sec01_host_admins", "sec01_host_settings",
    "sec01_host_rules", "sec01_host_runtimes", "sec01_host_approvals",
    "alpha_git_profiles"
  ]),
  effects: Object.freeze([
    "sec01_host_effect_definitions", "sec01_host_comfy_workflows"
  ]),
  jobs: Object.freeze([
    "alpha_jobs", "sec01_host_jobs", "sec01_host_job_parameters",
    "sec01_host_comfy_executions", "sec01_host_active_slots",
    "sec01_host_commits", "alpha_sec01_admissions"
  ]),
  games: Object.freeze([
    "alpha_game_projects", "alpha_game_installation_evidence",
    "sec01_game_install_journal"
  ])
});

const LOOKUP = new Map();
for (const [category, names] of Object.entries(TABLE_FAMILIES)) {
  for (const name of names) {
    if (LOOKUP.has(name)) throw new Error("Table assigned to multiple review categories: " + name);
    LOOKUP.set(name, category);
  }
}
export function categoryForTable(name) {
  if (typeof name !== "string" || !name) throw new Error("Invalid table name");
  return LOOKUP.get(name) ?? "all";
}

export function groupReviewedTables(review) {
  if (!review || !Array.isArray(review.tables)) throw new Error("No verified table inventory");
  const grouped = Object.fromEntries(REVIEW_CATEGORIES.map(category => [category, []]));
  const seen = new Set();
  for (const table of review.tables) {
    if (!table || typeof table.name !== "string" || seen.has(table.name)) {
      throw new Error("Invalid or duplicate SQLite table");
    }
    seen.add(table.name);
    grouped[categoryForTable(table.name)].push(table);
  }
  for (const category of REVIEW_CATEGORIES) {
    const rank = TABLE_FAMILIES[category] ?? [];
    grouped[category].sort((left, right) => {
      const a = rank.indexOf(left.name), b = rank.indexOf(right.name);
      return (a === -1 ? rank.length : a) - (b === -1 ? rank.length : b) ||
        left.name.localeCompare(right.name);
    });
  }
  return grouped;
}
