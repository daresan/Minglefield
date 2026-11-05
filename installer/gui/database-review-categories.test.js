import test from "node:test";
import assert from "node:assert/strict";
import {
  REVIEW_CATEGORIES, TABLE_FAMILIES, categoryForTable, groupReviewedTables
} from "./database-review-categories.js";

test("all 27 current Alpha tables map exactly once to five owner-facing tabs", () => {
  assert.deepEqual(REVIEW_CATEGORIES, ["login","hosts","effects","jobs","games","all"]);
  assert.deepEqual(Object.fromEntries(Object.entries(TABLE_FAMILIES).map(
    ([category,names]) => [category, names.length])),
    { login: 6, hosts: 9, effects: 2, jobs: 7, games: 3 });
  const names = Object.values(TABLE_FAMILIES).flat();
  assert.equal(names.length, 27);
  assert.equal(new Set(names).size, 27);
  for (const [category, list] of Object.entries(TABLE_FAMILIES)) {
    for (const name of list) assert.equal(categoryForTable(name), category);
  }
});

test("Comfy workflow JSON belongs to Effects and host Rules/Settings to Hosts", () => {
  for (const name of ["sec01_host_comfy_workflows","sec01_host_effect_definitions"]) {
    assert.equal(categoryForTable(name), "effects");
  }
  for (const name of ["sec01_host_rules","sec01_host_settings","sec01_host_runtimes"]) {
    assert.equal(categoryForTable(name), "hosts");
  }
  for (const name of ["sec01_host_jobs","sec01_host_comfy_executions"]) {
    assert.equal(categoryForTable(name), "jobs");
  }
  assert.equal(categoryForTable("unknown_extension_table"), "all");
});

test("each verified table appears in one domain; unknown extensions stay accessible", () => {
  const names = Object.values(TABLE_FAMILIES).flat().reverse();
  const tables = [...names.map(name => ({name, rows:[]})),
    {name:"user_extension",rows:[]}];
  const result = groupReviewedTables({tables});
  assert.deepEqual(REVIEW_CATEGORIES.map(c => result[c].length), [6,9,2,7,3,1]);
  assert.deepEqual(result.effects.map(t=>t.name), TABLE_FAMILIES.effects);
  assert.equal(result.all[0].name,"user_extension");
  assert.equal(Object.values(result).flat().length,tables.length);
});

test("unknown, duplicate or missing inventories fail closed", () => {
  assert.throws(() => categoryForTable(""), /Invalid/);
  assert.throws(() => groupReviewedTables(null), /No verified/);
  assert.throws(() => groupReviewedTables({tables:[{name:"alpha_users"},{name:"alpha_users"}]}),
    /duplicate/);
});
