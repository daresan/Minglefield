"""Local-only Minglefield Private Alpha gateway, simulation ONLY.

No B2 effect invocation, no ComfyUI, no password enrollment and no external
listener. Static tokens are TEST FIXTURES, not production authentication.
Do NOT expose this prototype via Tailscale Serve to invited users yet.
"""
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import time
from threading import Lock
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

MAX_BODY = 4096
MAX_JOBS_PER_USER = 5

PAGE = """<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Minglefield — Local Alpha / Private Alpha (lokal)</title>
<style>body{font:16px system-ui;margin:2rem auto;max-width:74rem;padding:0 1rem}
input,button{font:inherit;padding:.5rem;margin:.3rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}
fieldset{margin:1rem 0;border:1px solid #8885;border-radius:12px;padding:1rem;display:flex;flex-wrap:wrap;gap:.6rem;align-items:end}
fieldset>legend{font-weight:700;padding:0 .5rem}
fieldset>label{display:flex;flex-direction:column;gap:.25rem;min-width:13rem;flex:1 1 13rem}
fieldset>label:has(input[type=checkbox]){flex-direction:row;align-items:center}
fieldset>p,fieldset>pre,fieldset>fieldset{flex-basis:100%}
input,select{max-width:100%;box-sizing:border-box}
button{cursor:pointer;border-radius:7px;border:1px solid #8886}
#alphaNav{display:flex;flex-wrap:wrap;gap:.4rem;margin:1rem 0}
#alphaNav button[aria-current=page]{font-weight:800;outline:2px solid currentColor}
#alphaNav button:disabled{opacity:.4;cursor:not-allowed}
.alphaPanel[hidden]{display:none!important}
#hostJobsOutput{max-height:20rem;overflow:auto}</style>
<h1>Minglefield Private Alpha</h1>
<nav id="alphaNav" aria-label="Bereiche"></nav>
<p>Nur lokale Simulation. Kein Tailscale Serve und keine echten Effekte.</p>
<fieldset><legend>1. Einladung einlösen (nur Auth-v2-Test)</legend>
<label>Einladungscode <input id="invite" type="password" autocomplete="off"></label>
<p>Das Benutzerkonto ist unabhängig von deinen eigenen oder beauftragten Agenten.</p>
<label>Passwort für spätere Anmeldung (mind. 12 Zeichen) <input id="signupPassword" type="password" autocomplete="new-password"></label>
<button id="redeem">Einladung einlösen</button>
<p><small>Der Betreiber erstellt Einladungscodes weiterhin lokal per PowerShell.
Der erzeugte Session-Token bleibt nur in diesem Browsertab gespeichert.</small></p></fieldset>
<fieldset><legend>2. Wieder anmelden ohne neue Einladung</legend>
<label>Benutzer-ID <input id="loginUser" autocomplete="username" placeholder="user.alice"></label>
<label>Passwort <input id="loginPassword" type="password" autocomplete="current-password"></label>
<button id="login">Anmelden</button>
</fieldset>
<fieldset><legend>2b. Vorhandener Session-Token / Alt-Konto</legend>
<label>Session-Token (kein Einladungscode) <input id="token" type="password" autocomplete="off"></label>
<button id="connect">Connect</button><button id="logout">Logout</button>
<label>Passwort für bestehendes Alt-Konto setzen <input id="legacyPassword" type="password" autocomplete="new-password"></label>
<button id="setPassword">Passwort setzen</button></fieldset>
<fieldset><legend>3. Agenten verwalten oder beauftragen</legend>
<label>Neuen eigenen Agenten anlegen <input id="newAgent" placeholder="agent.example"></label>
<button id="addAgent">Agent anlegen</button>
<label>Eigenen Agenten freigeben <input id="grantAgent" placeholder="agent.example"></label>
<label>Für Benutzer <input id="grantee" placeholder="user.friend"></label>
<button id="grant">Freigeben</button><button id="revoke">Freigabe widerrufen</button>
<label>Agent für Simulation <select id="selectedAgent"></select></label>
<p><small>Eigene und ausdrücklich freigegebene fremde Agenten können ausgewählt werden. Freigabe gilt nur für demo.echo.</small></p>
</fieldset>
<fieldset><legend>4. Simulieren</legend>
<button id="create">Simulate action</button><button id="refresh">Jobs aktualisieren</button></fieldset>
<fieldset id="hostJobPanel"><legend>Host-Jobs: Einreichen und steuern (Simulation)</legend>
<label>Host für Job <select id="jobHostSelect"></select></label>
<label>Effekt für Job <select id="jobEffectSelect"></select></label>
<button id="effectManual">Job in Warteschlange einreihen</button>

<button id="hostJobsRefresh">Host-Jobs laden</button>
<label>Bestehenden Job auswählen <select id="hostJobSelect"></select></label>
<label>Job-ID <input id="hostJobId" placeholder="hostjob.…"></label>
<button id="hostJobCancel">Eingereihten Job abbrechen</button>
<button id="hostJobRetry">Abgebrochenen Job erneut einreihen</button>
<button id="hostJobEvaluate">Host-Regeln prüfen (Mock)</button>
<button id="hostJobReserve">Slot reservieren (Mock)</button>
<button id="hostJobRelease">Reservierung aufheben (Mock)</button>
<pre id="hostJobsOutput" aria-live="polite">Noch keine Host-Jobs geladen.</pre>
<pre id="jobActionOutput" aria-live="polite">Noch keine Jobaktion.</pre></fieldset>
<fieldset id="effectPanel"><legend>Effekte konfigurieren</legend>
<label>Host-Zuordnung <select id="effectHostSelect"></select></label>
<fieldset><legend>Effektdefinitionen (keine Jobeinreichung)</legend>
<label>Bestehenden Effekt auswählen <select id="effectSelect"></select></label>
<label>Effekt-ID <input id="effectId" placeholder="effect.example"></label>
<label>Beschreibung <input id="effectDescription" placeholder="Beschreibung des Effekts"></label>
<label><input type="checkbox" id="effectEnabled" checked> Effekt aktiviert</label>
<button id="effectSave">Effektdefinition speichern</button>

<p><small>Kein Befehl, keine externe Aktion: Es werden nur Metadaten gespeichert
beziehungsweise ein persistenter Mock-Job ohne Ausführung eingereiht.</small></p>
</fieldset>
<pre id="effectOutput" aria-live="polite">Effekt auswählen oder anlegen.</pre>
</fieldset>
<fieldset><legend>5. Host-Verwaltung (lokaler Alpha-Test)</legend>
<p>Eigene Hosts werden deinem angemeldeten Minglefield-Benutzer zugeordnet.
Keine Systemadministratorrechte nötig. Nur lokale Simulation; keine echten Effekte.</p>
<label>Eigene Host-ID <input id="claimHost" placeholder="host.local"></label>
<label>Lokaler Bestätigungscode aus der Gateway-Konsole
<input id="claimSecret" type="password" autocomplete="off"></label>
<button id="claimHostButton">Diesen lokalen Host übernehmen</button>
<p><small>Den Bestätigungscode zeigt das lokal mit --auth-db gestartete Gateway beim Start.
Die Hostübernahme ist nur einmalig erforderlich.</small></p>
<button id="hostRefresh">Hosts und Regeln laden</button>\n<label>Vorhandene Regel <select id="hostRuleSelect"></select></label>\n<button id="hostLoadRule">Regel bearbeiten</button>
<label>Host <select id="hostSelect"></select></label>
<label>Regel-ID <input id="hostRuleId" placeholder="rule.night"></label>
<label>Priorität <input id="hostPriority" type="number" value="10" min="0"></label>
<label><input id="hostEnabled" type="checkbox" checked> Regel aktiv</label>
<label>Freigabe <select id="hostMode"><option value="automatic">Automatisch</option>
<option value="manual">Manuell</option></select></label>
<label><input id="hostIdle" type="checkbox"> Nur wenn kein anderer Effekt läuft</label>
<label>GPU-Auslastung unter % (leer = ohne Grenze)
<input id="hostGpu" type="number" min="0" max="100"></label>
<label>Maximal parallele Effekte (leer = ohne Grenze)
<input id="hostParallel" type="number" min="1" max="1024"></label>
<label>Zeitzone <input id="hostTimezone" value="Europe/Berlin"></label>
<label>Wochentage (0=Mo bis 6=So, komma-getrennt)
<input id="hostDays" value="0,1,2,3,4,5,6"></label>
<label>Beginn <input id="hostStart" type="time" value="00:00"></label>
<label>Ende <input id="hostEnd" type="time" value="23:59"></label>
<button id="hostSave">Regel speichern</button>
<button id="hostDelete">Regel löschen</button>
<button id="hostToggle">Regel aktivieren/deaktivieren</button>
<p><small>Regeln gelten pro Host; die erste zeitlich passende aktive Regel entscheidet.
Manuelle Bestätigung und Slots sind nur simuliert. Zeitfenster über Mitternacht
werden derzeit abgelehnt.</small></p>
<label>Effekte auf diesem Host <select id="hostEffectShortcut"></select></label>
<button id="hostOpenEffect">Effekt im Effekte-Tab öffnen</button>

<pre id="hostOutput" aria-live="polite">Bitte anmelden und Hosts laden.</pre>
</fieldset>
<p id="sessionStatus" role="status" aria-live="polite">Keine aktive Session.</p>
<pre id="output" aria-live="polite">Einladung einlösen oder gültigen Session-Token eingeben.</pre>
<script>
let credential="";
let expiresAt=0;
const out=document.getElementById("output");
const statusLine=document.getElementById("sessionStatus");
const alphaSections=[...document.querySelectorAll("body>fieldset")];
const alphaNav=document.getElementById("alphaNav");
const alphaPanels={
  login:alphaSections.slice(0,3),
  agents:[alphaSections[3]],
  jobs:[alphaSections[4],document.getElementById("hostJobPanel")],
  hosts:[alphaSections[7]],
  effects:[document.getElementById("effectPanel")]
};
let alphaTab="login";
for(const [key,label] of [["login","Anmeldung"],["hosts","Hosts"],
                           ["effects","Effekte"],["jobs","Jobs"],["agents","Agenten"]]){
  const button=document.createElement("button");
  button.textContent=label;button.type="button";button.dataset.tab=key;
  button.onclick=()=>{alphaTab=key;renderAlphaTabs();};
  alphaNav.append(button);
}
function renderAlphaTabs(){
  if(!credential)alphaTab="login";
  for(const button of alphaNav.querySelectorAll("button")){
    button.disabled=!credential&&button.dataset.tab!=="login";
    button.setAttribute("aria-current",button.dataset.tab===alphaTab?"page":"false");
  }
  for(const section of alphaSections){
    section.classList.add("alphaPanel");
    section.hidden=!(alphaPanels[alphaTab]||[]).includes(section);
  }

}
renderAlphaTabs();
const updateStatus=()=>{
  renderAlphaTabs();
  if(!credential){statusLine.textContent="Keine aktive Session.";return;}
  if(!expiresAt){statusLine.textContent="Session-Token im Tab aktiv (Ablaufzeit nicht bekannt).";return;}
  const seconds=Math.max(0,Math.ceil((expiresAt-Date.now())/1000));
  statusLine.textContent=seconds>0?
    "Session im Tab aktiv. Verbleibend bei letzter Aktualisierung: "+seconds+" Sekunden.":
    "Session vermutlich abgelaufen – bitte neu anmelden.";
};
async function request(path,options={}){
  const headers={...(options.headers||{})};
  if(credential)headers.Authorization="Bearer "+credential;
  const response=await fetch(path,{...options,headers,cache:"no-store"});
  return {status:response.status,data:await response.json()};
}
const show=v=>out.textContent=JSON.stringify(v,null,2);
const agentSelect=document.getElementById("selectedAgent");
function fillAgents(agents){
  const last=agentSelect.value;
  agentSelect.replaceChildren();
  for(const agent of agents){
    const option=document.createElement("option");
    option.value=agent.agent_id;
    option.textContent=agent.agent_id+" ("+agent.relationship+", owner: "+agent.owner+")";
    agentSelect.append(option);
  }
  if(agents.some(a=>a.agent_id===last))agentSelect.value=last;
}
const handleUnauthorized=(reply)=>{
  if(reply.status===401){credential="";expiresAt=0;updateStatus();
    statusLine.textContent="Session ungültig, widerrufen oder abgelaufen. Erneut anmelden.";}
};
const api=async(path,body)=>request(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
const refresh=async()=>{
  if(!credential){show({message:"Bitte zuerst anmelden."});return;}
  const agents=await request("/api/agents");
  const jobs=await request("/api/jobs");
  handleUnauthorized(agents);
  handleUnauthorized(jobs);
  if(credential && agents.status===200)fillAgents(agents.data.agents);
  if(credential)await refreshHosts();
  if(credential)updateStatus();
  show({agents,jobs});
};
document.getElementById("redeem").onclick=async()=>{
  const secret=document.getElementById("invite").value;
  document.getElementById("invite").value="";
  const password=document.getElementById("signupPassword").value;
  document.getElementById("signupPassword").value="";
  const result=await api("/api/redeem",{invitation:secret,password});
  if(result.status===201){
    credential=result.data.session_token;
    expiresAt=Date.now()+result.data.expires_in*1000;
    updateStatus();
    show({status:201,message:"Session aktiviert. Connect zeigt Benutzer und Agent getrennt."});
  }
  else show(result);
};
document.getElementById("login").onclick=async()=>{
  const user_id=document.getElementById("loginUser").value;
  const password=document.getElementById("loginPassword").value;
  document.getElementById("loginPassword").value="";
  const result=await api("/api/login",{user_id,password});
  if(result.status===200){
    credential=result.data.session_token;
    expiresAt=Date.now()+result.data.expires_in*1000;
    updateStatus();
    await refresh();
  } else {
    const explanations={
      400:"Ungültige Anmeldedaten oder Anfrage.",
      401:"Benutzer-ID oder Passwort nicht akzeptiert.",
      403:"Lokale Origin-/Host-Prüfung fehlgeschlagen.",
      429:"Zu viele Login-/Registrierungsversuche. Bitte mindestens 60 Sekunden warten."
    };
    show({status:result.status,error:result.data.error||"login_failed",
          message:explanations[result.status]||"Anmeldung fehlgeschlagen."});
  }
};
document.getElementById("setPassword").onclick=async()=>{
  if(!credential){show({message:"Für Alt-Konto zuerst gültigen Session-Token eingeben."});return;}
  const password=document.getElementById("legacyPassword").value;
  document.getElementById("legacyPassword").value="";
  const result=await api("/api/password/set",{password});
  show(result);
};
document.getElementById("connect").onclick=async()=>{
  const supplied=document.getElementById("token").value;
  if(supplied){credential=supplied;expiresAt=0;updateStatus();}
  document.getElementById("token").value="";
  await refresh();
};
document.getElementById("refresh").onclick=refresh;
document.getElementById("addAgent").onclick=async()=>{
  if(!credential){show({message:"Zuerst mit Benutzer-ID anmelden."});return;}
  const agent_id=document.getElementById("newAgent").value;
  const result=await api("/api/agents",{agent_id});
  if(result.status===201){
    document.getElementById("newAgent").value="";
    await refresh();agentSelect.value=agent_id;
  } else show(result);
};
async function changeGrant(revoke){
  if(!credential){show({message:"Zuerst anmelden."});return;}
  const result=await api("/api/grants",{agent_id:document.getElementById("grantAgent").value,
    grantee_user_id:document.getElementById("grantee").value,revoke});
  show(result);
}
document.getElementById("grant").onclick=()=>changeGrant(false);
document.getElementById("revoke").onclick=()=>changeGrant(true);
document.getElementById("create").onclick=async()=>{
  if(!credential){show({message:"Bitte zuerst anmelden."});return;}
  if(!agentSelect.value){show({message:"Zuerst Agenten auswählen."});return;}
  const result=await api("/api/jobs",{agent_id:agentSelect.value,
    action:"demo.echo",idempotency_key:crypto.randomUUID()});
  handleUnauthorized(result);
  show(result);
};
const hostOut=document.getElementById("hostOutput");
const hostSelect=document.getElementById("hostSelect");
let hostCache=[];
const hv=id=>document.getElementById(id).value;
const hm=id=>document.getElementById(id).checked;
const minutes=s=>{const p=s.split(":").map(Number);return p[0]*60+p[1];};
const fmtMinutes=n=>String(Math.floor(n/60)).padStart(2,"0")+":"+
  String(n%60).padStart(2,"0");
function hostConfig(){
  const gpu=hv("hostGpu"),parallel=hv("hostParallel");
  return {mode:hv("hostMode"),idle_only:hm("hostIdle"),
    gpu_max_percent:gpu===""?null:Number(gpu),
    max_parallel_effects:parallel===""?null:Number(parallel),
    timezone:hv("hostTimezone"),
    weekdays:hv("hostDays").split(",").map(x=>Number(x.trim())),
    start_minute:minutes(hv("hostStart")),end_minute:minutes(hv("hostEnd"))};
}
function loadRule(rule){
  document.getElementById("hostRuleId").value=rule.rule_id;
  document.getElementById("hostPriority").value=rule.priority;
  document.getElementById("hostEnabled").checked=rule.enabled;
  document.getElementById("hostMode").value=rule.config.mode;
  document.getElementById("hostIdle").checked=rule.config.idle_only;
  document.getElementById("hostGpu").value=rule.config.gpu_max_percent??"";
  document.getElementById("hostParallel").value=rule.config.max_parallel_effects??"";
  document.getElementById("hostTimezone").value=rule.config.timezone;
  document.getElementById("hostDays").value=rule.config.weekdays.join(",");
  document.getElementById("hostStart").value=fmtMinutes(rule.config.start_minute);
  document.getElementById("hostEnd").value=fmtMinutes(rule.config.end_minute);
}
async function refreshHosts(){
  if(!credential){hostOut.textContent="Bitte zuerst anmelden.";return;}
  const result=await request("/api/hosts");
  handleUnauthorized(result);
  if(result.status!==200){hostOut.textContent=JSON.stringify(result,null,2);return;}
  const previous=hostSelect.value;
  hostCache=result.data.hosts;
  hostSelect.replaceChildren();
  const jobHost=document.getElementById("jobHostSelect");jobHost.replaceChildren();
  const effectHost=document.getElementById("effectHostSelect");effectHost.replaceChildren();
  for(const host of hostCache){
    const opt=document.createElement("option");
    opt.value=host.host_id;opt.textContent=host.host_id;hostSelect.append(opt);
    const copy=opt.cloneNode(true);jobHost.append(copy);
    effectHost.append(opt.cloneNode(true));
  }
  if(hostCache.some(h=>h.host_id===previous))hostSelect.value=previous;
  renderHost();
  jobHost.value=hostSelect.value;
  effectHost.value=hostSelect.value;
  renderJobEffects();
}
function renderHost(){
  const host=hostCache.find(h=>h.host_id===hostSelect.value);
  const select=document.getElementById("hostRuleSelect");
  select.replaceChildren();
  if(host)for(const rule of host.rules){
    const opt=document.createElement("option");opt.value=rule.rule_id;
    opt.textContent=rule.rule_id+" (Priorität "+rule.priority+")";select.append(opt);
  }
  const shortcuts=document.getElementById("hostEffectShortcut");shortcuts.replaceChildren();
  for(const effect of host?.effects||[]){const opt=document.createElement("option");opt.value=effect.effect_id;opt.textContent=effect.effect_id;shortcuts.append(opt);}
  const effects=document.getElementById("effectSelect");
  const previousEffect=effects.value;
  effects.replaceChildren();
  if(host)for(const effect of host.effects){
    const opt=document.createElement("option");opt.value=effect.effect_id;
    opt.textContent=effect.effect_id+(effect.enabled?"":" (deaktiviert)");
    effects.append(opt);
  }
  if(host?.effects.some(e=>e.effect_id===previousEffect))effects.value=previousEffect;
  if(effects.value)loadSelectedEffect();
  hostOut.textContent=host?JSON.stringify(host,null,2):
    "Noch kein eigener Host vorhanden. Oben Host-ID und lokalen Bestätigungscode eingeben und Host übernehmen.";
}
function renderJobEffects(){
  const host=hostCache.find(h=>h.host_id===hv("jobHostSelect"));
  const select=document.getElementById("jobEffectSelect");
  const previous=select.value;select.replaceChildren();
  for(const effect of host?.effects||[]){
    if(!effect.enabled)continue;
    const opt=document.createElement("option");opt.value=effect.effect_id;
    opt.textContent=effect.effect_id;select.append(opt);
  }
  if([...select.options].some(o=>o.value===previous))select.value=previous;
}
document.getElementById("jobHostSelect").onchange=()=>{
  hostSelect.value=hv("jobHostSelect");renderHost();renderJobEffects();
};
function loadSelectedEffect(){
  const host=hostCache.find(h=>h.host_id===hv("effectHostSelect"));
  const effect=host?.effects.find(e=>e.effect_id===document.getElementById("effectSelect").value);
  if(!effect)return;
  document.getElementById("effectId").value=effect.effect_id;
  document.getElementById("effectDescription").value=effect.description;
  document.getElementById("effectEnabled").checked=effect.enabled;
}
document.getElementById("effectSelect").onchange=loadSelectedEffect;
document.getElementById("hostRuleSelect").onchange=()=>{
  const host=hostCache.find(h=>h.host_id===hostSelect.value);
  const rule=host?.rules.find(r=>r.rule_id===hv("hostRuleSelect"));
  if(rule)loadRule(rule);
};
hostSelect.onchange=renderHost;
document.getElementById("effectHostSelect").onchange=()=>{
  hostSelect.value=hv("effectHostSelect");renderHost();
};
document.getElementById("hostOpenEffect").onclick=()=>{
  document.getElementById("effectHostSelect").value=hostSelect.value;
  document.getElementById("effectSelect").value=hv("hostEffectShortcut");
  loadSelectedEffect();alphaTab="effects";renderAlphaTabs();
};
document.getElementById("hostLoadRule").onclick=()=>{
  const host=hostCache.find(h=>h.host_id===hostSelect.value);
  const rule=host?.rules.find(r=>r.rule_id===hv("hostRuleSelect"));
  if(rule)loadRule(rule);
};
document.getElementById("hostRefresh").onclick=refreshHosts;
document.getElementById("claimHostButton").onclick=async()=>{
  const secret=hv("claimSecret");
  document.getElementById("claimSecret").value="";
  const result=await api("/api/host/claim",
    {host_id:hv("claimHost"),bootstrap_secret:secret});
  hostOut.textContent=JSON.stringify(result,null,2);
  if(result.status===200)await refreshHosts();
};
for(const [id,path] of [
  ["hostJobReserve","/api/host/jobs/reserve"],
  ["hostJobRelease","/api/host/jobs/release"]]){
  document.getElementById(id).onclick=async()=>{
    const result=await api(path,{host_id:hostSelect.value,job_id:hv("hostJobId")});
    document.getElementById("jobActionOutput").textContent=JSON.stringify(result,null,2);
    if(result.status===200)document.getElementById("hostJobsRefresh").click();
  };
}
document.getElementById("hostJobEvaluate").onclick=async()=>{
  const result=await api("/api/host/jobs/evaluate",
    {host_id:hostSelect.value,job_id:hv("hostJobId")});
  document.getElementById("jobActionOutput").textContent=JSON.stringify(result,null,2);
  if(result.status===200)document.getElementById("hostJobsRefresh").click();
};
document.getElementById("hostJobCancel").onclick=async()=>{
  const result=await api("/api/host/jobs/cancel",
    {host_id:hostSelect.value,job_id:hv("hostJobId")});
  document.getElementById("jobActionOutput").textContent=JSON.stringify(result,null,2);
  if(result.status===200)document.getElementById("hostJobsRefresh").click();
};
document.getElementById("hostJobRetry").onclick=async()=>{
  const result=await api("/api/host/jobs/retry",
    {host_id:hv("jobHostSelect"),job_id:hv("hostJobId")});
  document.getElementById("jobActionOutput").textContent=JSON.stringify(result,null,2);
  if(result.status===200)document.getElementById("hostJobsRefresh").click();
};
document.getElementById("hostJobSelect").onchange=()=>{
  document.getElementById("hostJobId").value=hv("hostJobSelect");
};
document.getElementById("hostJobsRefresh").onclick=async()=>{
  const result=await request("/api/host/jobs?host_id="+encodeURIComponent(hostSelect.value));
  document.getElementById("hostJobsOutput").textContent=JSON.stringify(result,null,2);
  if(result.status===200){
    const select=document.getElementById("hostJobSelect");
    const old=select.value;select.replaceChildren();
    for(const job of result.data.jobs){
      const opt=document.createElement("option");opt.value=job.job_id;
      opt.textContent=job.effect_id+" · "+job.state+" · "+job.job_id;
      select.append(opt);
    }
    if(result.data.jobs.some(j=>j.job_id===old))select.value=old;
    if(select.value)document.getElementById("hostJobId").value=select.value;
  }
};
document.getElementById("effectSave").onclick=async()=>{
  const result=await api("/api/host/effects",
    {host_id:hostSelect.value,effect_id:hv("effectId"),
     description:hv("effectDescription"),enabled:hm("effectEnabled")});
  document.getElementById("jobActionOutput").textContent=JSON.stringify(result,null,2);
  if(result.status===200)await refreshHosts();
};
document.getElementById("effectManual").onclick=async()=>{
  const result=await api("/api/host/effects/manual",
    {host_id:hostSelect.value,effect_id:hv("effectId")});
  document.getElementById("jobActionOutput").textContent=JSON.stringify(result,null,2);
  if(result.status===200)document.getElementById("hostJobsRefresh").click();
};
document.getElementById("hostSave").onclick=async()=>{
  const result=await api("/api/host/rules",{host_id:hostSelect.value,
    rule_id:hv("hostRuleId"),priority:Number(hv("hostPriority")),
    enabled:hm("hostEnabled"),config:hostConfig()});
  hostOut.textContent=JSON.stringify(result,null,2);
  if(result.status===200)await refreshHosts();
};
document.getElementById("hostDelete").onclick=async()=>{
  const result=await api("/api/host/rules/delete",
    {host_id:hostSelect.value,rule_id:hv("hostRuleId")});
  hostOut.textContent=JSON.stringify(result,null,2);
  if(result.status===200)await refreshHosts();
};
document.getElementById("hostToggle").onclick=async()=>{
  document.getElementById("hostEnabled").checked=!hm("hostEnabled");
  document.getElementById("hostSave").click();
};
hostOut.onclick=e=>{
  if(!e.target)return;
};
document.getElementById("logout").onclick=async()=>{
  const result=credential?await request("/api/logout",{method:"POST"}):{status:401};
  credential="";expiresAt=0;updateStatus();
  show(result);
};
</script></html>"""


@dataclass(frozen=True)
class TestPrincipal:
    user_id: str
    agent_id: str


class AlphaSimulation:
    def __init__(self, tokens):
        """Caller supplies generated test-only bearer tokens."""
        if (type(tokens) is not dict or not tokens
                or any(type(t) is not str or len(t) < 32
                       or type(p) is not TestPrincipal or not p.user_id or not p.agent_id
                       for t, p in tokens.items())):
            raise ValueError("invalid test-only identities")
        if len(set(tokens)) != len(tokens):
            raise ValueError("duplicate token")
        self._digests = {hashlib.sha256(t.encode()).digest(): p for t, p in tokens.items()}
        self._jobs = {}
        from threading import Lock
        self._lock = Lock()

    def principal(self, authorization):
        if type(authorization) is not str or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:]
        if not token or len(token) > 256:
            return None
        digest = hashlib.sha256(token.encode()).digest()
        for known, principal in self._digests.items():
            if hmac.compare_digest(digest, known):
                return principal
        return None

    def agents(self, principal):
        return [{"agent_id": principal.agent_id, "owner": principal.user_id,
                 "allowed_actions": ["demo.echo"]}]

    def jobs(self, principal):
        with self._lock:
            return [dict(value) for (user, _), value in self._jobs.items()
                    if user == principal.user_id]

    def submit(self, principal, payload):
        if (type(payload) is not dict or set(payload) != {"action", "idempotency_key"}
                or payload["action"] != "demo.echo"
                or type(payload["idempotency_key"]) is not str
                or not 1 <= len(payload["idempotency_key"]) <= 128):
            return 400, {"error": "invalid_simulated_action"}
        with self._lock:
            key = (principal.user_id, payload["idempotency_key"])
            if key in self._jobs:
                return 200, dict(self._jobs[key])
            if sum(u == principal.user_id for u, _ in self._jobs) >= MAX_JOBS_PER_USER:
                return 429, {"error": "simulation_quota_exceeded"}
            record = {"job_id": "sim." + secrets.token_hex(12),
                      "user_id": principal.user_id, "agent_id": principal.agent_id,
                      "action": "demo.echo", "state": "simulated_no_effect"}
            self._jobs[key] = record
            return 201, dict(record)


def handler_for(service, *, local_bootstrap_secret=None):
    # In-memory abuse throttle for the LOCAL browser onboarding prototype.
    attempts = {}
    throttle = Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Never log Authorization or request bodies.
            return

        def reply(self, status, payload):
            body = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/":
                page = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
                self.end_headers()
                self.wfile.write(page)
                return
            if path == "/health":
                self.reply(200, {"status": "simulation_only"})
                return
            principal = service.principal(self.headers.get("Authorization"))
            if not principal:
                self.reply(401, {"error": "unauthorized"})
                return
            if path == "/api/agents":
                if hasattr(service, "available_agents"):
                    self.reply(200, {"agents": service.available_agents(
                        self.headers.get("Authorization"))})
                else:
                    self.reply(200, {"agents": service.agents(principal)})
            elif path == "/api/jobs":
                self.reply(200, {"jobs": service.jobs(principal)})
            elif path == "/api/host/jobs":
                policy=getattr(service,"_host_policy",None)
                host_id=parse_qs(urlsplit(self.path).query).get("host_id",[])
                if policy is None or len(host_id)!=1:
                    self.reply(400,{"error":"invalid_host_jobs_query"})
                else:
                    jobs=policy.list_host_jobs(host_id[0],principal.user_id)
                    self.reply(403 if jobs is None else 200,
                        {"error":"not_host_owner"} if jobs is None else
                        {"jobs":jobs,"simulation_only":True})
            elif path == "/api/hosts":
                if not hasattr(service,"_host_policy"):
                    self.reply(200, {"hosts":[],"simulation_only":True})
                else:
                    self.reply(200, {"hosts":service._host_policy.list_hosts(
                        principal.user_id),"simulation_only":True})
            else:
                self.reply(404, {"error": "not_found"})

        def do_POST(self):
            path = urlsplit(self.path).path
            if path not in ("/api/jobs", "/api/agents", "/api/grants", "/api/logout", "/api/redeem", "/api/login", "/api/password/set", "/api/host/rules", "/api/host/rules/delete", "/api/host/claim", "/api/host/effects", "/api/host/effects/manual", "/api/host/jobs/cancel", "/api/host/jobs/evaluate", "/api/host/jobs/reserve", "/api/host/jobs/release"):
                self.reply(404, {"error": "not_found"})
                return
            if path in ("/api/redeem", "/api/login", "/api/password/set"):
                # Local test only: no reverse-proxy trust or remote registration.
                if self.client_address[0] not in ("127.0.0.1", "::1"):
                    self.reply(404, {"error": "unavailable"})
                    return
                origin = self.headers.get("Origin")
                host = self.headers.get("Host", "")
                allowed = ("127.0.0.1:" + str(self.server.server_port),
                           "localhost:" + str(self.server.server_port))
                if (host not in allowed
                        or (origin is not None and origin not in
                            tuple("http://" + name for name in allowed))):
                    self.reply(403, {"error": "local_origin_required"})
                    return
                with throttle:
                    now = time.monotonic()
                    recent = [t for t in attempts.get("local", []) if now - t < 60]
                    if len(recent) >= 5:
                        attempts["local"] = recent
                        self.reply(429, {"error": "try_again_later"})
                        return
                    recent.append(now)
                    attempts["local"] = recent
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    self.reply(415, {"error": "json_required"})
                    return
                raw_length = self.headers.get("Content-Length", "")
                if not raw_length.isdecimal() or int(raw_length) > MAX_BODY:
                    self.reply(413, {"error": "invalid_body_length"})
                    return
                try:
                    data = json.loads(self.rfile.read(int(raw_length)))
                except (UnicodeDecodeError, ValueError):
                    self.reply(400, {"error": "invalid_json"})
                    return
                if type(data) is not dict:
                    self.reply(400, {"error": "invalid_request"})
                    return
                if path == "/api/redeem":
                    if not hasattr(service, "redeem") or set(data) not in (
                            {"invitation", "agent_id"}, {"invitation", "agent_id", "password"},
                            {"invitation"}, {"invitation", "password"}):
                        self.reply(400, {"error": "invalid_registration"})
                        return
                    session = service.redeem(data["invitation"], agent_id=data.get("agent_id"),
                                             password=data.get("password"))
                    if session is None:
                        self.reply(400, {"error": "invitation_invalid_or_used"})
                        return
                    self.reply(201, {"session_token": session, "expires_in": 900})
                    return
                if path == "/api/login":
                    if not hasattr(service, "login") or set(data) != {"user_id", "password"}:
                        self.reply(400, {"error": "invalid_login"})
                        return
                    session = service.login(data["user_id"], data["password"])
                    if session is None:
                        self.reply(401, {"error": "invalid_credentials"})
                        return
                    self.reply(200, {"session_token": session, "expires_in": 900})
                    return
                if (not hasattr(service, "set_password_authenticated")
                        or set(data) != {"password"}):
                    self.reply(400, {"error": "invalid_password_change"})
                    return
                if not service.set_password_authenticated(
                        self.headers.get("Authorization"), data["password"]):
                    self.reply(403, {"error": "invalid_session_or_password"})
                    return
                self.reply(200, {"status": "password_set"})
                return
            principal = service.principal(self.headers.get("Authorization"))
            if not principal:
                self.reply(401, {"error": "unauthorized"})
                return
            if path == "/api/logout":
                revoke = getattr(service, "revoke_session", None)
                if revoke is None:
                    self.reply(404, {"error": "unavailable"})
                else:
                    revoke(self.headers.get("Authorization"))
                    self.reply(200, {"status": "session_revoked"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self.reply(415, {"error": "json_required"})
                return
            length = self.headers.get("Content-Length", "")
            if not length.isdecimal() or int(length) > MAX_BODY:
                self.reply(413, {"error": "invalid_body_length"})
                return
            try:
                body = json.loads(self.rfile.read(int(length)))
            except (UnicodeDecodeError, ValueError):
                self.reply(400, {"error": "invalid_json"})
                return
            if path in ("/api/host/claim","/api/host/effects",
                        "/api/host/effects/manual","/api/host/jobs/cancel",
                        "/api/host/jobs/retry",
                        "/api/host/jobs/evaluate", "/api/host/jobs/reserve",
                        "/api/host/jobs/release"):
                policy=getattr(service,"_host_policy",None)
                if policy is None or type(body) is not dict:
                    self.reply(404,{"error":"host_management_unavailable"})
                    return
                if path in ("/api/host/jobs/reserve","/api/host/jobs/release"):
                    if set(body)!={"host_id","job_id"}:
                        self.reply(400,{"error":"invalid_job_reservation"})
                        return
                    if path=="/api/host/jobs/reserve":
                        result=policy.reserve_waiting_host_job_mock(
                            body["host_id"],principal.user_id,body["job_id"],
                            now=int(time.time()))
                    else:
                        result=policy.release_reserved_host_job_mock(
                            body["host_id"],principal.user_id,body["job_id"])
                    self.reply(200 if result.state in ("reserved_mock","waiting_mock")
                               else 409 if result.state=="waiting" else 403,
                        {"state":result.state,"reason":result.reason,
                         "simulation_only":True})
                    return
                if path=="/api/host/jobs/evaluate":
                    if set(body)!={"host_id","job_id"}:
                        self.reply(400,{"error":"invalid_job_evaluation"})
                        return
                    result=policy.evaluate_queued_host_job(
                        body["host_id"],principal.user_id,body["job_id"],
                        now=int(time.time()))
                    self.reply(200 if result.state=="waiting" else 403,
                        {"state":result.state,"reason":result.reason,
                         "simulation_only":True})
                    return
                if path=="/api/host/jobs/retry":
                    if set(body)!={"host_id","job_id"}:
                        self.reply(400,{"error":"invalid_job_retry"})
                        return
                    result=policy.retry_cancelled_host_job(
                        body["host_id"],principal.user_id,body["job_id"])
                    self.reply(200 if result.state=="queued_mock" else 403,
                        {"state":result.state,"reason":result.reason,
                         "simulation_only":True})
                    return
                if path=="/api/host/jobs/cancel":
                    if set(body)!={"host_id","job_id"}:
                        self.reply(400,{"error":"invalid_job_cancel"})
                        return
                    result=policy.cancel_queued_host_job(
                        body["host_id"],principal.user_id,body["job_id"])
                    self.reply(200 if result.state=="cancelled_mock" else 403,
                        {"state":result.state,"reason":result.reason,
                         "simulation_only":True})
                    return
                if path=="/api/host/claim":
                    if set(body)!={"host_id","bootstrap_secret"}:
                        self.reply(400,{"error":"invalid_host_claim"})
                        return
                    # Loopback-only plus exact local Host/Origin AND console secret.
                    host_header=self.headers.get("Host","")
                    allowed=("127.0.0.1:"+str(self.server.server_port),
                             "localhost:"+str(self.server.server_port))
                    origin=self.headers.get("Origin")
                    if (self.client_address[0] not in ("127.0.0.1","::1")
                            or host_header not in allowed
                            or (origin is not None and origin not in
                                tuple("http://"+h for h in allowed))):
                        self.reply(403,{"error":"local_origin_required"})
                        return
                    supplied=body["bootstrap_secret"]
                    if (local_bootstrap_secret is None or type(supplied) is not str
                            or not hmac.compare_digest(supplied,local_bootstrap_secret)):
                        self.reply(403,{"error":"local_bootstrap_required"})
                        return
                    result=policy.claim_local_host(body["host_id"],principal.user_id)
                elif path=="/api/host/effects":
                    if set(body)!={"host_id","effect_id","description","enabled"}:
                        self.reply(400,{"error":"invalid_effect_definition"})
                        return
                    result=policy.define_effect(body["host_id"],principal.user_id,
                        body["effect_id"],body["description"],body["enabled"])
                else:
                    if set(body)!={"host_id","effect_id"}:
                        self.reply(400,{"error":"invalid_manual_intent"})
                        return
                    result=policy.manual_start_mock(body["host_id"],principal.user_id,
                        body["effect_id"])
                self.reply(200 if result.state in ("claimed","saved","requested_mock","queued_mock")
                           else 403,{"state":result.state,"reason":result.reason,
                                    "simulation_only":True})
                return
            if path in ("/api/host/rules","/api/host/rules/delete"):
                policy=getattr(service,"_host_policy",None)
                if policy is None:
                    self.reply(404, {"error":"host_policy_unavailable"})
                    return
                if type(body) is not dict:
                    self.reply(400, {"error":"invalid_host_rule"})
                    return
                if path.endswith("/delete"):
                    if set(body)!={"host_id","rule_id"}:
                        self.reply(400, {"error":"invalid_host_rule"})
                        return
                    result=policy.delete_rule(body["host_id"],principal.user_id,
                                              body["rule_id"])
                else:
                    if set(body)!={"host_id","rule_id","priority","enabled","config"}:
                        self.reply(400, {"error":"invalid_host_rule"})
                        return
                    result=policy.upsert_rule(body["host_id"],principal.user_id,
                        body["rule_id"],priority=body["priority"],
                        enabled=body["enabled"],config=body["config"])
                self.reply(200 if result.state in ("saved","deleted") else 403,
                           {"state":result.state,"reason":result.reason,
                            "simulation_only":True})
                return
            if path == "/api/agents":
                if not hasattr(service, "create_agent") or set(body) != {"agent_id"}:
                    self.reply(400, {"error":"invalid_agent_request"})
                    return
                status,result=service.create_agent(self.headers.get("Authorization"),
                                                  body["agent_id"])
            elif path == "/api/grants":
                if not hasattr(service, "grant_agent") or set(body) != {
                        "agent_id","grantee_user_id","revoke"}:
                    self.reply(400, {"error":"invalid_grant_request"})
                    return
                status,result=service.grant_agent(
                    self.headers.get("Authorization"),
                    agent_id=body["agent_id"],grantee_user_id=body["grantee_user_id"],
                    revoke=body["revoke"])
            elif hasattr(service,"submit_agent") and "agent_id" in body:
                status,result=service.submit_agent(self.headers.get("Authorization"),body)
            else:
                status, result = service.submit(principal, body)
            self.reply(status, result)
    return Handler


def run_local():
    parser = argparse.ArgumentParser(description="LOCAL simulation only; NEVER publish as-is")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--auth-db", help="local-only SQLite test identity store")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024..65535")
    if args.auth_db:
        from private_alpha_auth import AlphaAuthStore
        service = AlphaAuthStore(args.auth_db)
        from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
        from sec01_host_commit_policy_sim import HostCommitPolicy
        service._host_policy=HostCommitPolicy(IntegratedAlphaAdmission(service))
        token = None
    else:
        token = secrets.token_urlsafe(36)
        service = AlphaSimulation({token: TestPrincipal("demo.local", "agent.demo")})
    bootstrap=secrets.token_urlsafe(32) if args.auth_db else None
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                 handler_for(service,local_bootstrap_secret=bootstrap))
    print("LOCAL-ONLY simulation, no real effects. DO NOT EXPOSE VIA SERVE YET.")
    if token:
        print("Local test token (do not share):", token, flush=True)
    else:
        print("Auth v4 SQLite mode: create invitations with private_alpha_admin.py.", flush=True)
        print("LOCAL host claim bootstrap code (do not share):",bootstrap,flush=True)
    print("URL: http://127.0.0.1:" + str(args.port), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    run_local()
