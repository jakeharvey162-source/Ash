import { CONNECTOR_CATALOG } from './connectors.js';
import { nativeAvailable, getDeviceInfo, openUrl, shareText, copyText, notify, haptic } from './native.js';
const C=window.JARVIS_CONFIG||{};
const BASE=(C.SUPABASE_URL||"").replace(/\/$/,""),KEY=C.SUPABASE_PUBLISHABLE_KEY||"",GATEWAY=C.ASH_GATEWAY_URL||"",INTEGRATIONS=BASE+"/functions/v1/ash-integrations";
let session=JSON.parse(localStorage.getItem("ash-session")||"null");
let profile={assistant_name:"Ash",personality_preset:"adaptive",preferred_mode:"medium",wake_word:"Ash",custom_instructions:"",behavior_config:{verbosity:"balanced",proactivity:"balanced",humor:20},voice_config:{auto_speak:true,voice_id:"cjVigY5qzO86Huf0OWal"}};
let mode=localStorage.getItem("ash-mode")||"medium",view="home",authMode="signin",theme=localStorage.getItem("ash-theme")||"dark",messages=[],automations=[],jobs=[],devices=[],integrations=[],nativeState={available:false,device:null},sending=false,speaking=false;

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const headers=()=>({apikey:KEY,"Content-Type":"application/json",...(session?.access_token?{Authorization:"Bearer "+session.access_token}:{})});
async function supa(path,opt={}){const r=await fetch(BASE+path,{...opt,headers:{...headers(),...(opt.headers||{})}});let d={};try{d=await r.json()}catch{};if(!r.ok)throw new Error(d?.msg||d?.message||d?.error_description||d?.error||("HTTP "+r.status));return d}
function saveSession(s){session={access_token:s.access_token,refresh_token:s.refresh_token,user:s.user};localStorage.setItem("ash-session",JSON.stringify(session))}
async function login(email,password){saveSession(await supa("/auth/v1/token?grant_type=password",{method:"POST",body:JSON.stringify({email,password})}))}
async function signup(email,password,name){const d=await supa("/auth/v1/signup",{method:"POST",body:JSON.stringify({email,password,data:{full_name:name}})});if(d.access_token)saveSession(d);return d}
async function recoverPassword(email){return supa("/auth/v1/recover",{method:"POST",body:JSON.stringify({email})})}
async function loadProfile(){if(!session)return;const r=await supa("/rest/v1/jarvis_profiles?user_id=eq."+encodeURIComponent(session.user.id)+"&select=*");if(r?.[0])profile={...profile,...r[0],behavior_config:{...profile.behavior_config,...(r[0].behavior_config||{})},voice_config:{...profile.voice_config,...(r[0].voice_config||{})}};mode=profile.preferred_mode||mode}
async function loadOps(){
  if(!session)return;
  const q="?user_id=eq."+encodeURIComponent(session.user.id)+"&order=created_at.desc&limit=20";
  const [a,j,d,i]=await Promise.all([
    supa("/rest/v1/jarvis_automations"+q).catch(()=>[]),
    supa("/rest/v1/jarvis_remote_jobs"+q).catch(()=>[]),
    supa("/rest/v1/jarvis_devices"+q).catch(()=>[]),
    supa("/rest/v1/jarvis_integrations"+q).catch(()=>[])
  ]);
  automations=a||[];jobs=j||[];devices=d||[];integrations=i||[];
}
async function saveProfile(){
  const body={assistant_name:document.querySelector("#assistantName").value.trim()||"Ash",wake_word:document.querySelector("#wakeWord").value.trim()||"Ash",personality_preset:document.querySelector("#personality").value,preferred_mode:mode,custom_instructions:document.querySelector("#instructions").value.trim(),behavior_config:{...profile.behavior_config,verbosity:document.querySelector("#verbosity").value,proactivity:document.querySelector("#proactivity").value,humor:Number(document.querySelector("#humor").value)},voice_config:{...profile.voice_config,auto_speak:document.querySelector("#speak").checked,voice_id:document.querySelector("#voice").value}};
  const r=await supa("/rest/v1/jarvis_profiles?user_id=eq."+encodeURIComponent(session.user.id),{method:"PATCH",headers:{Prefer:"return=representation"},body:JSON.stringify(body)});
  profile={...profile,...(r?.[0]||body)};render();toast("Preferences saved");
}
function fmt(t){if(!t)return"—";const d=new Date(t);return d.toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})}
function relative(t){if(!t)return"never";const s=Math.round((Date.now()-new Date(t).getTime())/1000);if(s<60)return"just now";if(s<3600)return Math.floor(s/60)+"m ago";if(s<86400)return Math.floor(s/3600)+"h ago";return Math.floor(s/86400)+"d ago"}
function toast(t){const n=document.createElement("div");n.className="toast";n.textContent=t;document.body.append(n);setTimeout(()=>n.remove(),2200)}
function icon(name){const m={home:"⌂",chat:"↗",builder:"⌘",automation:"↻",activity:"◌",connections:"◎",settings:"⚙",team:"◇"};return m[name]||"•"}
function applyTheme(){document.documentElement.dataset.theme=theme;document.documentElement.style.colorScheme=theme==="light"?"light":"dark"}
function toggleTheme(){theme=theme==="dark"?"light":"dark";localStorage.setItem("ash-theme",theme);applyTheme();render()}
function nav(){
  const items=[["home","Overview"],["builder","Builder"],["automation","Automations"],["activity","Activity"],["connections","Connections"],["team","Organization"],["settings","Preferences"]];
  return `<aside class="rail"><div class="wordmark"><span class="mark">A</span><b>${esc(profile.assistant_name)}</b></div><div class="navgroup">${items.map(([k,l])=>`<button class="navitem ${view===k?"selected":""}" data-view="${k}"><span>${icon(k)}</span><em>${l}</em></button>`).join("")}</div><div class="railfoot"><span class="presence"></span><div><b>Cloud connected</b><small>${devices.length?devices.length+" device"+(devices.length>1?"s":""):"No desktop linked"}</small></div></div></aside>`;
}
function topbar(title,sub=""){return `<header class="topbar"><div><p class="kicker">${esc(sub)}</p><h1>${esc(title)}</h1></div><div class="topactions"><div class="modeSwitch">${["instant","medium","high"].map(x=>`<button data-mode="${x}" class="${mode===x?"active":""}">${x}</button>`).join("")}</div><button id="themeToggle" class="themeToggle" aria-label="Switch color theme"><span>${theme==="dark"?"☀":"☾"}</span><em>${theme==="dark"?"Light":"Dark"}</em></button><span class="live"><i></i>Online</span></div></header>`}
function googleMark(){return '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.24-.2-1.8H12v3.27h5.52c-.11.81-.71 2.03-2.05 2.85l-.02.11 2.98 2.31.21.02c1.95-1.8 3.07-4.45 3.07-7.76Z"/><path fill="#34A853" d="M12 22c2.78 0 5.11-.92 6.81-2.5l-3.24-2.51c-.87.59-2.02 1-3.57 1-2.73 0-5.05-1.8-5.88-4.29l-.1.01-3.1 2.4-.04.1C4.57 19.57 8.03 22 12 22Z"/><path fill="#FBBC05" d="M6.12 13.7A6.02 6.02 0 0 1 5.8 12c0-.59.11-1.16.3-1.7l-.01-.12-3.14-2.44-.1.05A10 10 0 0 0 2 12c0 1.6.38 3.12 1.05 4.46l3.07-2.76Z"/><path fill="#EA4335" d="M12 6.01c1.94 0 3.25.84 4 1.53l2.88-2.81C17.11 3.08 14.78 2 12 2 8.03 2 4.57 4.43 2.88 7.79l3.22 2.51C6.95 7.81 9.27 6.01 12 6.01Z"/></svg>'}
function shell(content){return session?`<div class="shell">${nav()}<main class="workspace">${content}</main><nav class="mobileNav">${[["home","Home"],["builder","Build"],["automation","Automate"],["connections","Connect"],["settings","You"]].map(([k,l])=>`<button data-view="${k}" class="${view===k?"selected":""}"><span>${icon(k)}</span><small>${l}</small></button>`).join("")}</nav></div>`:`<main class="authShell">${content}</main>`}
function authView(){
  const signupMode=authMode==="signup";
  return `<section class="cinematicAuth" id="cinematicAuth">
    <div class="authBackdrop"></div>
    <div class="authTop">
      <div class="cinematicLogo"><span class="ashGlyph">A</span><strong>Ash<span>.</span></strong></div>
      <nav class="authNav"><span>Product</span><span>Capabilities</span><span>Safety</span><span>Company</span></nav>
      <button id="themeToggle" class="themeToggle authTheme" aria-label="Switch color theme"><span>${theme==="dark"?"☀":"☾"}</span><em>${theme==="dark"?"Light":"Dark"}</em></button>
    </div>

    <div class="authHero" id="authHero">
      <div class="heroCopy">
        <p class="heroEyebrow">${theme==="dark"?"A HIGHER INTELLIGENCE FOR A BRIGHTER YOU":"YOUR AI OPERATING SYSTEM"}</p>
        <h1>${theme==="dark"?'Think Deeper.<br>Move Faster.<br><em>With Ash.</em>':'A more<br><em>capable</em> you.'}</h1>
        <p class="heroLead">Ash thinks, creates, reasons and acts with you — turning ideas into progress across your work, knowledge and life.</p>

        <div class="heroCapabilities">
          <span><b>✦</b>Think<br>Deeper</span>
          <span><b>◇</b>Create<br>Faster</span>
          <span><b>↗</b>Take<br>Action</span>
          <span><b>⌘</b>Built<br>For You</span>
        </div>

        <div class="heroActions">
          <button id="meetAsh" class="heroPrimary">Meet Ash <span>→</span></button>
          <button id="watchVoice" class="heroSecondary"><span class="playDot">▶</span><b>Hear Ash</b></button>
        </div>

        <div class="heroStats">
          <span><strong>10×</strong><small>Productivity mindset</small></span>
          <span><strong>24/7</strong><small>Available workspace</small></span>
          <span><strong>1</strong><small>Assistant, many specialists</small></span>
        </div>
      </div>

      <div class="heroVisual" aria-hidden="true">
        <div class="heroHalo"></div>
        <img class="heroPortrait heroPortraitDark" src="/images/ash-hero-dark.webp" alt="">
        <img class="heroPortrait heroPortraitLight" src="/images/ash-hero-light.webp" alt="">
        <div class="heroArc arcOne"></div>
        <div class="heroArc arcTwo"></div>
      </div>

      <div class="authPanel" id="authPanel">
        <div class="panelGlow"></div>
        <div class="authPanelBrand"><span class="ashGlyph small">A</span><strong>Ash<span>.</span></strong></div>
        <p class="welcomeLabel">${signupMode?"Create your account":"Welcome back."}</p>
        <p class="welcomeSub">${signupMode?"Build your private Ash workspace.":"Same you. A more capable you."}</p>

        <div class="authTabs">
          <button data-auth-mode="signin" class="${!signupMode?"active":""}">Sign in</button>
          <button data-auth-mode="signup" class="${signupMode?"active":""}">Create account</button>
        </div>

        ${signupMode?'<label class="authField"><span>Name</span><input id="name" autocomplete="name" placeholder="Your name"></label>':""}
        <label class="authField"><span>Email</span><div class="inputShell"><span>✉</span><input id="email" type="email" autocomplete="email" placeholder="you@domain.com"></div></label>
        <label class="authField"><span>Password</span><div class="inputShell"><span>▣</span><input id="password" type="password" autocomplete="${signupMode?"new-password":"current-password"}" placeholder="••••••••"></div></label>

        <div class="authMeta"><label><input id="rememberMe" type="checkbox" checked> Remember me</label><button type="button" id="forgotPassword" class="linkButton">Forgot password?</button></div>
        <button id="authSubmit" class="authSubmit">${signupMode?"Create account":"Sign in"} <span>→</span></button>
        <p id="authMsg" class="formMsg"></p>
        <p class="authFine">Private by design. Sensitive actions stay confirmation-based.</p>
      </div>
    </div>
  </section>`;
}
function stat(label,value,meta){return `<div class="stat card"><span>${label}</span><strong>${value}</strong><small>${meta}</small></div>`}
function voiceCore(){
  const bars=Array.from({length:36},(_,i)=>`<i style="--i:${i}"></i>`).join("");
  return `<section class="voiceCore card" id="voiceCore">
    <div class="reactor">
      <div class="reactorRing ring1"></div><div class="reactorRing ring2"></div><div class="reactorRing ring3"></div>
      <div class="reactorCore"><span>A</span></div>
    </div>
    <div class="voiceCoreCopy"><p class="kicker">ASH VOICE CORE</p><h2>${speaking?"Ash is speaking":"Ready when you are"}</h2><p>${speaking?"Voice activity is visualized live from the audio signal.":"Speak or type a command. Ash can reason, research, build and act through one interface."}</p><div class="voiceWave" id="voiceWave">${bars}</div></div>
    <div class="voiceState ${speaking?"speaking":""}"><span></span>${speaking?"Speaking":"Listening ready"}</div>
  </section>`;
}
function actionCard(m,i){if(!m.action)return"";const a=m.action;const summary=a.tool==="gmail.send"?`Send email to ${esc(a.args?.to||"recipient")} · ${esc(a.args?.subject||"No subject")}`:a.tool==="calendar.create"?`Create event · ${esc(a.args?.event?.summary||a.args?.summary||"Calendar event")}`:"Confirm action";return `<div class="confirmCard"><div><small>CONFIRM ACTION</small><b>${summary}</b></div><button data-confirm-index="${i}" class="primary">Confirm</button></div>`}
function home(){
  const liveDevices=devices.filter(d=>d.last_seen_at&&Date.now()-new Date(d.last_seen_at).getTime()<120000).length;
  const activeAuto=automations.filter(a=>a.enabled).length;
  const activeJobs=jobs.filter(j=>["queued","claimed","running"].includes(j.status)).length;
  return `${topbar("Good to have you back","ASH / COMMAND CENTER")}
  ${voiceCore()}
  <section class="stats">${stat("Automations",activeAuto,activeAuto?"active schedules":"none running")}${stat("Work queue",activeJobs,activeJobs?"in progress":"clear")}${stat("Desktop",liveDevices?"Online":"Offline",devices.length?devices.length+" linked":"not linked")}</section>
  <section class="commandPanel card">
    <div class="commandHead"><div><p class="kicker">COMMAND</p><h2>What should Ash handle?</h2></div><span class="modeLabel">${mode}</span></div>
    <div class="feed">${messages.length?messages.slice(-8).map((m,i)=>`<article class="${m.role==="user"?"mine":"ash"}"><small>${m.role==="user"?"YOU":esc(profile.assistant_name).toUpperCase()}</small><p>${esc(m.content)}</p>${actionCard(m,Math.max(0,messages.length-8)+i)}</article>`).join(""):`<div class="emptyPrompt"><p>Ask a question, plan work, build software, or automate a workflow.</p><div class="suggestions"><button data-suggest="Summarize what I need to focus on today">Plan my day</button><button data-view="builder">Build a project</button><button data-view="automation">Create automation</button></div></div>`}</div>
    <div class="composer"><button id="mic" aria-label="Voice input">◉</button><textarea id="prompt" placeholder="Ask Ash anything…" rows="1"></textarea><button id="send" class="send" aria-label="Send">${sending?"…":"↗"}</button></div>
  </section>
  <section class="split"><div class="card panel"><div class="panelTitle"><div><p class="kicker">UP NEXT</p><h3>Automations</h3></div><button data-view="automation" class="textBtn">Manage</button></div>${automations.length?automations.slice(0,3).map(a=>automationRow(a)).join(""):`<p class="quiet">No automations yet. Create one when you want Ash to work on a schedule.</p>`}</div><div class="card panel"><div class="panelTitle"><div><p class="kicker">RECENT</p><h3>Activity</h3></div><button data-view="activity" class="textBtn">View all</button></div>${jobs.length?jobs.slice(0,4).map(jobRow).join(""):`<p class="quiet">Nothing queued yet.</p>`}</div></section>`;
}
function automationRow(a){return `<div class="lineItem"><span class="statusDot ${a.enabled?"on":""}"></span><div><b>${esc(a.name)}</b><small>${esc(a.trigger_type)} · next ${fmt(a.next_run_at)}</small></div><span class="badge">${a.enabled?"Active":"Paused"}</span></div>`}
function jobRow(j){return `<div class="lineItem"><span class="jobIcon">${j.status==="completed"?"✓":j.status==="failed"?"!":"→"}</span><div><b>${esc(j.payload?.automation_name||j.payload?.prompt||j.kind)}</b><small>${esc(j.status)} · ${relative(j.created_at)}</small></div><span class="badge ${j.status}">${esc(j.mode)}</span></div>`}
function builderView(){
  const builderJobs=jobs.filter(j=>j.kind==="builder"||j.payload?.builder===true);
  const liveDevices=devices.filter(d=>d.last_seen_at&&Date.now()-new Date(d.last_seen_at).getTime()<120000);
  return `${topbar("Builder","ASH / SOFTWARE STUDIO")}<section class="automationGrid"><div class="card createAuto"><p class="kicker">BUILD WITH ASH</p><h2>Describe it. Ash builds and verifies it.</h2><p class="quiet">Ash plans the product, writes the project files, installs dependencies, runs the production build, repairs build failures and reports the real evidence from the linked desktop.</p><label>What should Ash build?<textarea id="buildPrompt" rows="8" placeholder="Build a premium responsive website for a Johannesburg coffee shop with menu, booking form, admin-ready structure, SEO and dark/light mode."></textarea></label><div class="formGrid"><label>Mode<select id="buildMode"><option value="high" selected>High · multi-step build</option><option value="medium">Medium · faster</option></select></label><label>Desktop<select id="buildDevice"><option value="">Any linked desktop</option>${devices.map(d=>`<option value="${d.id}">${esc(d.nickname||d.device_name)}${d.last_seen_at&&Date.now()-new Date(d.last_seen_at).getTime()<120000?" · online":""}</option>`).join("")}</select></label></div><button id="createBuild" class="primary wide">Build project</button><p class="quiet builderHint">${liveDevices.length?"Desktop builder online. Ash can execute builds now.":"No active desktop builder detected. You can queue the build; it will start when the Ash desktop worker connects."}</p></div><div class="card autoList"><div class="panelTitle"><div><p class="kicker">BUILD QUEUE</p><h3>Software projects</h3></div><span class="count">${builderJobs.length}</span></div>${builderJobs.length?builderJobs.map(j=>`<div class="autoItem"><div><span class="statusDot ${j.status==="completed"?"on":""}"></span><b>${esc((j.payload?.prompt||"Software build").slice(0,90))}</b><p>${esc(j.error||j.result?.summary||"Waiting for the desktop builder.")}</p><small>${esc(j.status)} · ${fmt(j.created_at)}${j.result?.workspace?" · workspace ready":""}</small></div><span class="badge ${j.status}">${esc(j.mode||"high")}</span></div>`).join(""):`<div class="emptyState"><p>No builds yet.</p><small>Describe a website or app and Ash will create the first one here.</small></div>`}</div></section>`;
}
async function createBuildJob(){
  const prompt=document.querySelector("#buildPrompt")?.value.trim();
  if(!prompt)return toast("Describe the website or app you want Ash to build.");
  const target=document.querySelector("#buildDevice")?.value||null;
  const buildMode=document.querySelector("#buildMode")?.value||"high";
  await supa("/rest/v1/jarvis_remote_jobs",{
    method:"POST",
    headers:{Prefer:"return=representation"},
    body:JSON.stringify({
      user_id:session.user.id,
      target_device_id:target,
      kind:"builder",
      mode:buildMode,
      payload:{prompt,builder:true,source:"user",executor:"desktop"},
      status:"queued",
      requires_confirmation:false
    })
  });
  await loadOps();
  render();
  toast(devices.length?"Build queued for Ash desktop.":"Build queued. Link the Ash desktop worker to start it.");
}
function automationView(){
  return `${topbar("Automations","ASH / WORKFLOWS")}<section class="automationGrid"><div class="card createAuto"><p class="kicker">NEW AUTOMATION</p><h2>Put recurring work on autopilot.</h2><p class="quiet">Ash schedules the job in the cloud and dispatches it to your linked desktop when it is time.</p><label>Name<input id="autoName" placeholder="Morning project brief"></label><label>What should Ash do?<textarea id="autoPrompt" rows="4" placeholder="Review my active project and prepare the next actions."></textarea></label><div class="formGrid"><label>Schedule<select id="autoType"><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="interval">Every N minutes</option><option value="once">Once</option></select></label><label id="whenLabel">First run<input id="autoWhen" type="datetime-local"></label></div><label id="intervalWrap" class="hidden">Repeat every<input id="autoInterval" type="number" min="1" value="60"> minutes</label><div class="formGrid"><label>Mode<select id="autoMode"><option>instant</option><option selected>medium</option><option>high</option></select></label><label>Desktop<select id="autoDevice"><option value="">Any linked desktop</option>${devices.map(d=>`<option value="${d.id}">${esc(d.nickname||d.device_name)}</option>`).join("")}</select></label></div><label class="check"><input id="autoConfirm" type="checkbox"> Ask before consequential actions</label><button id="createAuto" class="primary wide">Create automation</button></div><div class="card autoList"><div class="panelTitle"><div><p class="kicker">SCHEDULED</p><h3>Your automations</h3></div><span class="count">${automations.length}</span></div>${automations.length?automations.map(a=>`<div class="autoItem"><div><span class="statusDot ${a.enabled?"on":""}"></span><b>${esc(a.name)}</b><p>${esc(a.description||a.action_config?.prompt||"")}</p><small>${esc(a.trigger_type)} · next ${fmt(a.next_run_at)}</small></div><button data-toggle-auto="${a.id}" data-enabled="${a.enabled}">${a.enabled?"Pause":"Resume"}</button></div>`).join(""):`<div class="emptyState"><p>No automations yet.</p><small>Create one on the left.</small></div>`}</div></section>`;
}
function activityView(){return `${topbar("Activity","ASH / OPERATIONS")}<section class="card activityPanel"><div class="activityHeader"><div><p class="kicker">EXECUTION LOG</p><h2>What Ash has been doing</h2></div><button id="refreshOps" class="secondary">Refresh</button></div>${jobs.length?jobs.map(j=>`<div class="activityRow"><div class="activityMark ${j.status}">${j.status==="completed"?"✓":j.status==="failed"?"!":"→"}</div><div><b>${esc(j.payload?.automation_name||j.payload?.prompt||j.kind)}</b><p>${esc(j.error||j.result?.summary||"")}</p><small>${fmt(j.created_at)} · ${esc(j.status)}</small></div><span class="badge">${esc(j.mode)}</span></div>`).join(""):`<div class="emptyState"><p>No activity yet.</p><small>Scheduled and remote tasks will appear here.</small></div>`}</section>`}
function integrationFor(key){return integrations.find(i=>i.integration_key===key)||null}
function connectorStatus(c){if(c.builtIn&&c.native)return nativeState.available?"Available on Android":"Web fallback";const row=integrationFor(c.key);return row?.status||"Not connected"}
function connectionsView(){
  return `${topbar("Connections","ASH / PLUGINS")}<section class="connectionsIntro"><div><h2>Connect the tools you already use.</h2><p>Ash uses permissioned connectors instead of embedding third-party credentials in the app. Native Android capabilities work locally; cloud services use authenticated integrations.</p></div><span class="platformPill">${nativeState.available?"Android app":"Web / PWA"}</span></section><section class="connectorGrid">${CONNECTOR_CATALOG.map(c=>{const status=connectorStatus(c);return `<article class="card connector"><div class="connectorTop"><span class="connectorGlyph">${c.category==="device"?"A":c.category==="developer"?"<>":"○"}</span><div><b>${esc(c.name)}</b><small>${esc(c.category)}</small></div><span class="badge ${status.toLowerCase().replace(/\s+/g,"-")}">${esc(status)}</span></div><p>${esc(c.description)}</p><div class="scopeList">${c.permissions.map(p=>`<span>${esc(p)}</span>`).join("")}</div><div class="connectorActions">${c.builtIn&&c.native?`<button data-native-test="${c.key}" class="secondary">Test</button>`:`<button data-connect="${c.key}" class="primary">${integrationFor(c.key)?.status==="connected"?"Manage":"Connect"}</button>`}</div></article>`}).join("")}</section><section class="card connectorNote"><p class="kicker">PLUGIN MODEL</p><h3>Install capability, not hidden access.</h3><p>Every connector declares what it can read or change. Ash should request only the scopes needed for the task, and consequential actions still require confirmation when your preferences say so.</p></section>`;
}
async function testNativeConnector(key){
  try{
    if(key==="android_share"){await shareText("Ash","Shared from Ash");toast("Share sheet opened")}
    else if(key==="android_notifications"){await notify("Ash","Android connector is working.");toast("Notification sent")}
    else if(key==="android_clipboard"){await copyText("Ash connector test");toast("Copied to clipboard")}
    else if(key==="android_browser"){await openUrl("https://github.com/jakeharvey162-source/Ash");toast("Browser opened")}
    await haptic();
  }catch(e){toast(e.message||"Connector test failed")}
}
async function connectCloudConnector(key){
  const item=CONNECTOR_CATALOG.find(x=>x.key===key);if(!item)return;
  const existing=integrationFor(key);
  if(existing?.status==="connected"){toast(item.name+" is already connected");return}
  if(["gmail","google_calendar","google_drive"].includes(key)){
    try{
      const returnUrl=location.origin+location.pathname;
      const r=await fetch(INTEGRATIONS+"?action=start&integration="+encodeURIComponent(key)+"&return_url="+encodeURIComponent(returnUrl),{headers:{Authorization:"Bearer "+session.access_token,apikey:KEY}});
      const d=await r.json();
      if(!r.ok)throw new Error(d.error||"Connection setup failed");
      await openUrl(d.authorization_url);
      toast("Continue in Google to connect "+item.name);
    }catch(e){toast(e.message||"Connection setup failed")}
    return;
  }
  const body={user_id:session.user.id,integration_key:key,display_name:item.name,status:"disconnected",config:{requested_scopes:item.permissions,platform:nativeState.available?"android":"web",oauth_required:true}};
  await supa("/rest/v1/jarvis_integrations",{method:"POST",headers:{Prefer:"resolution=merge-duplicates,return=representation"},body:JSON.stringify(body)}).catch(()=>{});
  await loadOps();render();
  toast(item.name+" connector is ready for provider-specific OAuth.");
}
function teamView(){const names=[["Chief Orchestrator","Turns goals into coordinated work."],["Project Manager","Sequences tasks and tracks delivery."],["Business Analyst","Clarifies requirements and constraints."],["Research Analyst","Finds and verifies information."],["Software Architect","Shapes systems and technical decisions."],["Frontend Engineer","Builds product interfaces."],["Backend Engineer","Builds APIs, data and services."],["Desktop Engineer","Handles local computer workflows."],["Mobile Engineer","Builds mobile experiences."],["AI Engineer","Handles models, routing and prompts."],["Security Engineer","Reviews risk and permissions."],["QA Engineer","Tests behavior and catches regressions."]];return `${topbar("Organization","ASH / SPECIALISTS")}<section class="orgIntro"><h2>One assistant in front.<br>Specialists behind it.</h2><p>Ash chooses internal roles based on the task. You never have to manage the organization manually.</p></section><section class="orgGrid">${names.map(([n,d],i)=>`<div class="card specialist"><span>${String(i+1).padStart(2,"0")}</span><div><b>${n}</b><p>${d}</p></div></div>`).join("")}</section>`}
function settingsView(){return `${topbar("Preferences","ASH / YOU")}<section class="settingsGrid"><div class="card settings"><p class="kicker">IDENTITY</p><label>Assistant name<input id="assistantName" value="${esc(profile.assistant_name)}"></label><label>Wake word<input id="wakeWord" value="${esc(profile.wake_word)}"></label><div class="formGrid"><label>Personality<select id="personality">${["adaptive","executive","companion","builder","analyst","coach"].map(x=>`<option ${profile.personality_preset===x?"selected":""}>${x}</option>`).join("")}</select></label><label>Verbosity<select id="verbosity">${["concise","balanced","detailed"].map(x=>`<option ${profile.behavior_config?.verbosity===x?"selected":""}>${x}</option>`).join("")}</select></label></div><div class="formGrid"><label>Proactivity<select id="proactivity">${["quiet","balanced","proactive"].map(x=>`<option ${profile.behavior_config?.proactivity===x?"selected":""}>${x}</option>`).join("")}</select></label><label>Humor<input id="humor" type="range" min="0" max="100" value="${Number(profile.behavior_config?.humor??20)}"></label></div><label>Voice<select id="voice"><option value="cjVigY5qzO86Huf0OWal">Eric · smooth</option><option value="EXAVITQu4vr4xnSDxMaL">Sarah · confident</option></select></label><label class="check"><input id="speak" type="checkbox" ${profile.voice_config?.auto_speak!==false?"checked":""}> Speak responses automatically</label><label>Custom instructions<textarea id="instructions" rows="5">${esc(profile.custom_instructions||"")}</textarea></label><button id="save" class="primary wide">Save preferences</button></div><div class="sideStack"><div class="card about"><p class="kicker">ABOUT</p><h3>Ash</h3><p>Developed by Jake Harvey.</p><p class="quiet">Ash is designed around user control, explicit permissions and verifiable action status.</p></div><div class="card devicePanel"><p class="kicker">DEVICES</p><h3>Linked computers</h3>${devices.length?devices.map(d=>`<div class="device"><span class="statusDot ${d.last_seen_at&&Date.now()-new Date(d.last_seen_at).getTime()<120000?"on":""}"></span><div><b>${esc(d.nickname||d.device_name)}</b><small>${esc(d.platform)} · ${relative(d.last_seen_at)}</small></div></div>`).join(""):`<p class="quiet">No desktop has checked in yet.</p>`}</div><button id="signout" class="danger">Sign out</button></div></section>`}
function initCinematicMotion(){
  const root=document.querySelector("#cinematicAuth"),hero=document.querySelector("#authHero"),panel=document.querySelector("#authPanel");
  if(!root||!hero||!panel||window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches)return;
  root.onpointermove=e=>{
    const r=root.getBoundingClientRect(),x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;
    root.style.setProperty("--mx",(x*16).toFixed(2)+"px");root.style.setProperty("--my",(y*12).toFixed(2)+"px");
    panel.style.transform=`perspective(1400px) rotateX(${(-y*2.7).toFixed(2)}deg) rotateY(${(x*3.4).toFixed(2)}deg) translate3d(0,-2px,0)`;
  };
  root.onpointerleave=()=>{root.style.setProperty("--mx","0px");root.style.setProperty("--my","0px");panel.style.transform=""};
}
function setVoiceState(active){
  speaking=active;
  const core=document.querySelector("#voiceCore"),state=core?.querySelector(".voiceState"),title=core?.querySelector(".voiceCoreCopy h2");
  if(core)core.classList.toggle("isSpeaking",active);
  if(state){state.classList.toggle("speaking",active);state.lastChild.textContent=active?"Speaking":"Listening ready"}
  if(title)title.textContent=active?"Ash is speaking":"Ready when you are";
}
function animateWaveFromAnalyser(analyser,audio){
  const bars=[...document.querySelectorAll("#voiceWave i")];
  if(!bars.length)return;
  const data=new Uint8Array(analyser.frequencyBinCount);
  const tick=()=>{
    analyser.getByteFrequencyData(data);
    bars.forEach((b,i)=>{
      const idx=Math.floor(i/data.length*analyser.frequencyBinCount);
      const v=Math.max(8,Math.min(100,(data[idx]||0)/255*100));
      b.style.height=v+"%";
    });
    if(!audio.paused&&!audio.ended)requestAnimationFrame(tick);
  };
  tick();
}
async function playVoiceBlob(blob){
  const audio=new Audio(URL.createObjectURL(blob));setVoiceState(true);
  try{
    const AC=window.AudioContext||window.webkitAudioContext;
    if(AC){
      const ctx=new AC(),src=ctx.createMediaElementSource(audio),an=ctx.createAnalyser();
      an.fftSize=128;an.smoothingTimeConstant=.78;src.connect(an);an.connect(ctx.destination);
      audio.addEventListener("play",()=>animateWaveFromAnalyser(an,audio),{once:true});
      audio.addEventListener("ended",()=>{setVoiceState(false);ctx.close().catch(()=>{});URL.revokeObjectURL(audio.src)},{once:true});
    }else audio.addEventListener("ended",()=>setVoiceState(false),{once:true});
    await audio.play();
  }catch{setVoiceState(false)}
}
function render(){applyTheme();document.querySelector("#app").innerHTML=session?shell(view==="home"?home():view==="builder"?builderView():view==="automation"?automationView():view==="activity"?activityView():view==="connections"?connectionsView():view==="team"?teamView():settingsView()):authView();bind();if(!session)initCinematicMotion()}
function bind(){
  document.querySelector("#themeToggle")?.addEventListener("click",toggleTheme);
  document.querySelector("#meetAsh")?.addEventListener("click",()=>document.querySelector("#email")?.focus());
  document.querySelector("#watchVoice")?.addEventListener("click",()=>{toast("Sign in and ask Ash anything to hear the live voice visualization.")});
  document.querySelector("#forgotPassword")?.addEventListener("click",async()=>{
    const email=document.querySelector("#email")?.value.trim();
    const m=document.querySelector("#authMsg");
    if(!email){m.textContent="Enter your email first.";document.querySelector("#email")?.focus();return}
    try{await recoverPassword(email);m.textContent="Password reset email sent.";toast("Check your inbox for the reset link.")}
    catch(e){m.textContent=e.message||"Could not send reset email."}
  });
  document.querySelectorAll("[data-auth-mode]").forEach(b=>b.onclick=()=>{authMode=b.dataset.authMode;render()});
  document.querySelector("#authSubmit")?.addEventListener("click",async()=>{
    const m=document.querySelector("#authMsg"),email=document.querySelector("#email")?.value.trim(),password=document.querySelector("#password")?.value||"";
    if(!email||!password){m.textContent="Enter your email and password.";return}
    m.textContent=authMode==="signup"?"Creating your account…":"Signing you in…";
    try{
      if(authMode==="signup"){
        const name=document.querySelector("#name")?.value.trim()||"";
        const d=await signup(email,password,name);
        if(!session){m.textContent=d?.user?"Account created. Check your email if confirmation is enabled.":"Account created.";return}
      }else{
        await login(email,password);
      }
      await Promise.all([loadProfile(),loadOps()]);
      render();
    }catch(e){m.textContent=e.message||"Authentication failed."}
  });
  document.querySelectorAll("[data-view]").forEach(b=>b.onclick=async()=>{view=b.dataset.view;if(["builder","automation","activity","connections","settings","home"].includes(view))await loadOps();render()});
  document.querySelectorAll("[data-mode]").forEach(b=>b.onclick=()=>{mode=b.dataset.mode;localStorage.setItem("ash-mode",mode);render()});
  document.querySelectorAll("[data-suggest]").forEach(b=>b.onclick=()=>{document.querySelector("#prompt").value=b.dataset.suggest;document.querySelector("#prompt").focus()});  document.querySelector("#send")?.addEventListener("click",send);
  document.querySelector("#prompt")?.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}});
  document.querySelector("#mic")?.addEventListener("click",listen);
  document.querySelector("#save")?.addEventListener("click",saveProfile);
  document.querySelector("#signout")?.addEventListener("click",()=>{session=null;localStorage.removeItem("ash-session");render()});
  document.querySelector("#refreshOps")?.addEventListener("click",async()=>{await loadOps();render();toast("Activity refreshed")});
  document.querySelector("#autoType")?.addEventListener("change",e=>document.querySelector("#intervalWrap").classList.toggle("hidden",e.target.value!=="interval"));
  document.querySelector("#createAuto")?.addEventListener("click",createAutomation);
  document.querySelector("#createBuild")?.addEventListener("click",createBuildJob);
  document.querySelectorAll("[data-toggle-auto]").forEach(b=>b.onclick=()=>toggleAutomation(b.dataset.toggleAuto,b.dataset.enabled==="true"));
  document.querySelectorAll("[data-native-test]").forEach(b=>b.onclick=()=>testNativeConnector(b.dataset.nativeTest));
  document.querySelectorAll("[data-confirm-index]").forEach(b=>b.onclick=()=>confirmPendingAction(Number(b.dataset.confirmIndex)));
  document.querySelectorAll("[data-connect]").forEach(b=>b.onclick=()=>connectCloudConnector(b.dataset.connect));
}
async function createAutomation(){
  const name=document.querySelector("#autoName").value.trim(),prompt=document.querySelector("#autoPrompt").value.trim(),type=document.querySelector("#autoType").value,when=document.querySelector("#autoWhen").value;
  if(!name||!prompt||!when)return toast("Add a name, instruction and first run time.");
  const config=type==="interval"?{repeat_minutes:Number(document.querySelector("#autoInterval").value||60)}:{};
  const action={prompt,mode:document.querySelector("#autoMode").value,target_device_id:document.querySelector("#autoDevice").value||null,kind:"mission",requires_confirmation:document.querySelector("#autoConfirm").checked};
  await supa("/rest/v1/jarvis_automations",{method:"POST",headers:{Prefer:"return=representation"},body:JSON.stringify({user_id:session.user.id,name,description:prompt,trigger_type:type,trigger_config:config,action_config:action,enabled:true,next_run_at:new Date(when).toISOString()})});
  await loadOps();render();toast("Automation created");
}
async function toggleAutomation(id,enabled){await supa("/rest/v1/jarvis_automations?id=eq."+encodeURIComponent(id),{method:"PATCH",body:JSON.stringify({enabled:!enabled,updated_at:new Date().toISOString()})});await loadOps();render()}
async function confirmPendingAction(index){
  const m=messages[index]; if(!m?.action)return;
  const tool=m.action.tool,args=m.action.args||{};
  try{
    const r=await fetch(INTEGRATIONS+"?action="+encodeURIComponent(tool),{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+session.access_token,apikey:KEY},body:JSON.stringify(tool==="gmail.send"?{...args,confirmed:true}:{event:args.event||args,confirmed:true})});
    const d=await r.json(); if(!r.ok)throw new Error(d.error||"Action failed");
    m.content=tool==="gmail.send"?"Email sent successfully.":"Calendar event created successfully.";
    m.action=null; render(); toast("Action completed");
  }catch(e){toast(e.message||"Action failed")}
}
async function send(){if(sending)return;const box=document.querySelector("#prompt"),message=box?.value.trim();if(!message)return;box.value="";messages.push({role:"user",content:message});sending=true;render();try{const r=await fetch(GATEWAY,{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+session.access_token,apikey:KEY},body:JSON.stringify({action:"chat",message,mode,history:messages.slice(-10,-1)})});const d=await r.json();if(!r.ok)throw new Error(d.error||"Ash is unavailable.");messages.push({role:"assistant",content:d.answer||"Done.",action:d.pending_action||null});speak(d.answer)}catch(e){messages.push({role:"assistant",content:e.message})}finally{sending=false;render()}}
function listen(){const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){toast("Voice input needs a supported browser.");return}const r=new SR();r.lang=navigator.language||"en-US";r.onresult=e=>{document.querySelector("#prompt").value=e.results[0][0].transcript;send()};r.onerror=()=>toast("I couldn't hear that clearly.");r.start()}
async function speak(text){
  if(!text||profile.voice_config?.auto_speak===false)return;
  try{
    const r=await fetch(GATEWAY,{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+session.access_token,apikey:KEY},body:JSON.stringify({action:"speech",text:text.slice(0,5000),voice_id:profile.voice_config?.voice_id})});
    if(r.ok&&r.headers.get("content-type")?.includes("audio")){await playVoiceBlob(await r.blob());return}
  }catch{}
  if("speechSynthesis"in window){
    speechSynthesis.cancel();
    const u=new SpeechSynthesisUtterance(text.slice(0,1600));
    u.onstart=()=>setVoiceState(true);
    u.onend=()=>setVoiceState(false);
    u.onerror=()=>setVoiceState(false);
    speechSynthesis.speak(u);
  }
}
if("serviceWorker"in navigator)window.addEventListener("load",()=>navigator.serviceWorker.register("/sw.js").catch(()=>{}));
applyTheme();
render();

(async function hydrateAsh(){
  try{
    nativeState.available=await nativeAvailable();
    nativeState.device=await getDeviceInfo();
  }catch{
    nativeState={available:false,device:{platform:"web"}};
  }

  if(session){
    try{await Promise.all([loadProfile(),loadOps()])}catch{}
  }

  render();
})();