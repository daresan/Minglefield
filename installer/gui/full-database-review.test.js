import test from "node:test";
import assert from "node:assert/strict";
import {createFullReview, stageFullCell, fullRowCorrections,
  fullReviewSummary, verifyFullCell} from "./full-database-review.js";
const source = () => ({tables: [
  {name:"sec01_host_comfy_workflows",
    columns:["host_id","workflow_id","workflow_json","path"],
    rows:[{rowId:"12",cells:[
      {kind:"text",value:"shadow"}, {kind:"text",value:"rig"},
      {kind:"text",value:'{"nodes":64}'}, {kind:"text",value:"C:\\ComfyUI\\workflows"}
    ]}]},
  {name:"sec01_host_rules", columns:["host_id","rule_id","settings"],
    rows:[{rowId:"17",cells:[
      {kind:"text",value:"shadow"}, {kind:"text",value:"r1"},
      {kind:"text",value:'{"max_parallel":2}'}
    ]}]},
  {name:"password_data", columns:["user","hash"], rows:[{rowId:"18",cells:[
    {kind:"text",value:"alice"}, {kind:"blob",value:"00ff"}
  ]}]}
]});
test("loads Comfy workflow paths and host rules from actual row values", () => {
  const x = createFullReview(source());
  assert.equal(x.tables[0].rows[0].cells[3].value,"C:\\ComfyUI\\workflows");
  assert.equal(x.tables[1].rows[0].cells[2].value,'{"max_parallel":2}');
});
test("allows edits in every table, preserving exact typed originals", () => {
  const before = source();
  let after = stageFullCell(before,"sec01_host_comfy_workflows",0,"path",
    "text","D:\\Models\\workflow");
  after = stageFullCell(after,"sec01_host_comfy_workflows",0,"workflow_json",
    "text",'{"nodes":65}');
  after = stageFullCell(after,"sec01_host_rules",0,"settings","text",'{"max_parallel":3}');
  after = stageFullCell(after,"password_data",0,"hash","blob","a0ff");
  const corrections = fullRowCorrections(before,after);
  assert.equal(corrections.length,3);
  assert.equal(corrections[0].row_id,"12");
  assert.equal(corrections[0].before[2].value,'{"nodes":64}');
  assert.equal(corrections[0].after[2].value,'{"nodes":65}');
  assert.equal(corrections[0].after[3].value,"D:\\Models\\workflow");
  assert.equal(before.tables[0].rows[0].cells[3].value,"C:\\ComfyUI\\workflows");
  const safe = JSON.stringify(fullReviewSummary(corrections));
  assert.equal(safe.includes("00ff"),false);
  assert.equal(safe.includes("a0ff"),false);
  assert.equal(safe.includes("D:\\\\Models"),false);
});
test("supports NULL, 64-bit integers and BLOBs without JS Number precision loss",()=>{
  verifyFullCell({kind:"integer",value:"9223372036854775807"});
  assert.throws(()=>verifyFullCell({kind:"integer",value:"9223372036854775808"}));
  verifyFullCell({kind:"blob",value:"00FF"});
  assert.throws(()=>verifyFullCell({kind:"blob",value:"001"}));
  verifyFullCell({kind:"null",value:null});
  assert.throws(()=>verifyFullCell({kind:"null",value:""}));
  assert.deepEqual(fullRowCorrections(source(), source()),[]);
});
test("rejects unverified rows, schema change and altered row identities",()=>{
  const before=source();
  const broken=source();broken.tables[0].rows[0].rowId="999";
  assert.throws(()=>fullRowCorrections(before,broken),/identity/);
  const extra=source();extra.tables[0].columns.push("untrusted");
  assert.throws(()=>createFullReview(extra),/Incomplete/);
  const invalid=source();invalid.tables[2].rows[0].cells[1].value="zz";
  assert.throws(()=>createFullReview(invalid),/BLOB/);
});
