import test from "node:test";
import assert from "node:assert/strict";
import { renderFullDatabaseTable } from "./full-database-table.js";

class Element {
  constructor(tag="div") {
    this.tagName=tag.toUpperCase();this.children=[];this.events={};
    this.value="";this.textContent="";this.disabled=false;
  }
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=[...items];this.textContent="";}
  setAttribute(name,value){this[name]=value;}
  addEventListener(name,callback){this.events[name]=callback;}
}
const documentFixture={createElement:tag=>new Element(tag)};
const cell=(kind,value)=>({kind,value});
const source={
  name:"sec01_host_rules",
  columns:["rule_id","priority","config","optional"],
  rows:[{rowId:"1",cells:[
    cell("text","rule1"),cell("integer","3"),
    cell("text",'{"priority":3}'),cell("null",null)
  ]}]
};
function render(onEdit=()=>{},onError=()=>{}){
  const root=new Element();
  renderFullDatabaseTable(root,source,onEdit,onError,documentFixture);
  const tr=root.children[1].children[0].children[1].children[0];
  return {root,cells:tr.children.slice(1)};
}
test("cell types are visible but fixed; no editable type selector exists",()=>{
  const {cells}=render();
  assert.deepEqual(cells.map(c=>c.children[0].textContent),
    ["TEXT","INTEGER","TEXT","NULL"]);
  assert.ok(cells.every(c=>c.children[0].tagName==="SPAN"));
  assert.ok(cells.every(c=>c.children.every(child=>child.tagName!=="SELECT")));
  assert.equal(cells[3].children[1].disabled,true);
  assert.equal(cells[3].children[1].value,"(NULL)");
});

test("only stored values are sent for edits with original immutable kinds",()=>{
  const edits=[];const {cells}=render((...args)=>edits.push(args));
  const intInput=cells[1].children[1];
  intInput.value="7";intInput.events.change();
  const jsonInput=cells[2].children[1];
  jsonInput.value='{"priority":4}';jsonInput.events.change();
  assert.deepEqual(edits,[
    [0,"priority","integer","7"],
    [0,"config","text",'{"priority":4}']
  ]);
});

test("a rejected value edit restores the last accepted value",()=>{
  const errors=[];
  const {cells}=render((...args)=>{
    if(args[2]==="integer" && args[3]==="bad")throw Error("invalid integer");
  },error=>errors.push(error.message));
  const input=cells[1].children[1];
  input.value="bad";input.events.change();
  assert.equal(input.value,"3");
  assert.deepEqual(errors,["invalid integer"]);
});
