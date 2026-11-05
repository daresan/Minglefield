import test from "node:test";
import assert from "node:assert/strict";
import { renderDomainDatabaseReview } from "./domain-database-review.js";

class Node {
  constructor(tag="div") {
    this.tagName=tag.toUpperCase();this.children=[];this.listeners={};
    this.style={};this.hidden=false;this.value="";this.textContent="";
  }
  append(...elements) {this.children.push(...elements);}
  replaceChildren(...elements) {this.children=[...elements];this.textContent="";}
  setAttribute(name,value){this[name]=value;}
  addEventListener(name,cb){this.listeners[name]=cb;}
}

function fixture() {
  const elements = Object.fromEntries(["login","hosts","effects","jobs","games","all"]
    .flatMap(name=>[["#data-fields-"+name,new Node()],
      ["#data-editor-"+name,new Node()],
      ["#data-tab-"+name,new Node()]]));
  elements["#data-editor-all"].hidden=true;
  return { doc: { createElement: t=>new Node(t),
      querySelector: id => {if(!elements[id])throw Error("unexpected DOM selector "+id);
        return elements[id];} }, elements };
}
const typed = value => ({kind:"text",value});
const source = () => ({tables:[
  {name:"sec01_host_rules",columns:["host_id","config"],rows:[{
    rowId:"1",cells:[typed("shadow"),typed('{"priority":1}')]
  }]},
  {name:"sec01_host_comfy_workflows",columns:["effect_id","workflow"],rows:[{
    rowId:"2",cells:[typed("comfy.rig"),typed('{"4":{"class_type":"KSampler"}}')]
  }]},
  {name:"alpha_users",columns:["user_id","disabled"],rows:[{
    rowId:"3",cells:[typed("user"),{kind:"integer",value:"0"}]
  }]}
]});

test("comfy JSON is edited inside Effects; host rules inside Hosts; no duplicate editor",()=>{
  const {doc,elements} = fixture();
  let review=source(), edits=[];
  renderDomainDatabaseReview(doc,()=>review,(...args)=>edits.push(args),()=>{});
  assert.equal(elements["#data-tab-all"].hidden,true);
  assert.match(elements["#data-fields-effects"].children[1].children[0].children[0].textContent,
    /sec01_host_comfy_workflows/);
  assert.match(elements["#data-fields-hosts"].children[1].children[0].children[0].textContent,
    /sec01_host_rules/);
  const effects = elements["#data-fields-effects"];
  const grid = effects.children[2].children[1].children[0];
  const firstRow=grid.children[1].children[0];
  const workflow = firstRow.children[2].children[1];
  workflow.value='{"4":{"class_type":"CLIPTextEncode"}}';
  workflow.listeners.change();
  assert.deepEqual(edits[0],
    ["sec01_host_comfy_workflows",0,"workflow","text",'{"4":{"class_type":"CLIPTextEncode"}}']);
});

test("only unrecognized extensions appear in fallback tab",()=>{
  const {doc,elements}=fixture();
  let review=source();
  review.tables.push({name:"third_party_schema",columns:["k"],rows:[]});
  renderDomainDatabaseReview(doc,()=>review,()=>{},()=>{});
  assert.equal(elements["#data-tab-all"].hidden,false);
  assert.match(elements["#data-fields-all"].children[1].children[0].children[0].textContent,
    /third_party_schema/);
  assert.equal(elements["#data-fields-effects"].children[1].children[0].children.length,1);
});

test("switching a table renders latest staged state rather than old snapshot",()=>{
  const {doc,elements}=fixture();
  let review=source();
  review.tables.push({name:"sec01_host_settings",columns:["host_id","settings"],
    rows:[{rowId:"4",cells:[typed("shadow"),typed('{"limit":2}')]}]});
  renderDomainDatabaseReview(doc,()=>review,()=>{},()=>{});
  review = structuredClone(review);
  review.tables.find(t=>t.name==="sec01_host_rules").rows[0].cells[1].value='{"priority":5}';
  const select=elements["#data-fields-hosts"].children[1].children[0];
  select.value="sec01_host_settings";select.listeners.change();
  select.value="sec01_host_rules";select.listeners.change();
  const content=elements["#data-fields-hosts"].children[2];
  const grid=content.children[1].children[0];
  assert.equal(grid.children[1].children[0].children[2].children[1].value,'{"priority":5}');
});
