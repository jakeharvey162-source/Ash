import { CONNECTOR_CATALOG } from './connectors.js';
import { nativeAvailable, getDeviceInfo, openUrl, shareText, copyText, notify, haptic } from './native.js';
const C=window.JARVIS_CONFIG||{};
const BASE=(C.SUPABASE_URL||"").replace(/\/$/,""),KEY=C.SUPABASE_PUBLISHABLE_KEY||"",GATEWAY=C.ASH_GATEWAY_URL||"",INTEGRATIONS=BASE+"/functions/v1/ash-integrations";
let session=JSON.parse(localStorage.getItem("ash-session")||"null");
let profile={assistant_name:"Ash",personality_preset:"adaptive",preferred_mode:"medium",wake_word:"Ash",custom_instructions:"",behavior_config:{verbosity:"balanced",proactivity:"balanced",humor:20},voice_config:{auto_speak:true,voice_id:"cjVigY5qzO86Huf0OWal"}};
let mode=localStorage.getItem("ash-mode")||"medium",view="home",authMode="signin",theme=localStorage.getItem("ash-theme")||"dark",messages=[],automations=[],jobs=[],devices=[],integrations=[],nativeState={available:false,device:null},sending=false,speaking=false,coreState="idle",coreDetail="Systems ready",opsLoadedAt=0,refreshPromise=null,healthState={gateway:"unknown",session:"unknown",desktop:"offline",local:"unavailable",pwa:"unknown",voice:"unknown",checkedAt:null};
let heroVisualCleanup=null;

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const headers=()=>({apikey:KEY,"Content-Type":"application/json",...(session?.access_token?{Authorization:"Bearer "+session.access_token}:{})});
function saveSession(s){session={access_token:s.access_token,refresh_token:s.refresh_token||session?.refresh_token,user:s.user||session?.user};localStorage.setItem("ash-session",JSON.stringify(session))}
function clearSession(){session=null;localStorage.removeItem("ash-session");opsLoadedAt=0}
function tokenExpiresSoon(token,skew=60){
  try{
    const part=token.split(".")[1];if(!part)return false;
    const json=JSON.parse(atob(part.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(part.length/4)*4,"=")));
    return Number(json.exp||0)*1000-Date.now()<skew*1000;
  }catch{return false}
}
async function refreshSession(){
  if(refreshPromise)return refreshPromise;
  if(!session?.refresh_token)throw new Error("Your Ash session has expired. Please sign in again.");
  refreshPromise=(async()=>{
    const r=await fetch(BASE+"/auth/v1/token?grant_type=refresh_token",{
      method:"POST",
      headers:{apikey:KEY,"Content-Type":"application/json"},
      body:JSON.stringify({refresh_token:session.refresh_token})
    });
    let d={};try{d=await r.json()}catch{}
    if(!r.ok||!d?.access_token){clearSession();throw new Error("Your Ash session has expired. Please sign in again.");}
    saveSession(d);return session;
  })().finally(()=>{refreshPromise=null});
  return refreshPromise;
}
async function ensureFreshSession(){
  if(session?.access_token&&session?.refresh_token&&tokenExpiresSoon(session.access_token))await refreshSession();
  return session;
}
async function authedFetch(url,opt={},retry=true){
  await ensureFreshSession();
  const run=()=>fetch(url,{...opt,headers:{apikey:KEY,...(opt.headers||{}),...(session?.access_token?{Authorization:"Bearer "+session.access_token}:{})}});
  let r=await run();
  if(r.status===401&&retry&&session?.refresh_token){await refreshSession();r=await run();}
  return r;
}
async function supa(path,opt={},retry=true){
  await ensureFreshSession();
  let r=await fetch(BASE+path,{...opt,headers:{...headers(),...(opt.headers||{})}});
  if(r.status===401&&retry&&session?.refresh_token&&!path.startsWith("/auth/v1/")){await refreshSession();return supa(path,opt,false)}
  let d={};try{d=await r.json()}catch{}
  if(!r.ok)throw new Error(d?.msg||d?.message||d?.error_description||d?.error||("HTTP "+r.status));
  return d
}
async function login(email,password){
  try{
    saveSession(await supa("/auth/v1/token?grant_type=password",{method:"POST",body:JSON.stringify({email,password})}));
  }catch(e){
    const raw=String(e?.message||"");
    if(/invalid login credentials/i.test(raw))throw new Error("Email or password is incorrect. If you just created your account, try signing in again or use Forgot password.");
    if(/email not confirmed/i.test(raw))throw new Error("Your account exists, but sign-in is waiting on the current authentication settings.");
    throw e;
  }
}
async function signup(email,password,name){
  const d=await supa("/auth/v1/signup",{method:"POST",body:JSON.stringify({email,password,data:{full_name:name}})});
  if(d.access_token)saveSession(d);
  const identities=Array.isArray(d?.user?.identities)?d.user.identities:null;
  return {
    ...d,
    signup_state:d.access_token?"signed_in":identities&&identities.length===0?"existing_or_obfuscated":"confirmation_required"
  };
}
async function recoverPassword(email){return supa("/auth/v1/recover",{method:"POST",body:JSON.stringify({email})})}
async function loadProfile(){if(!session)return;const r=await supa("/rest/v1/jarvis_profiles?user_id=eq."+encodeURIComponent(session.user.id)+"&select=*");if(r?.[0])profile={...profile,...r[0],behavior_config:{...profile.behavior_config,...(r[0].behavior_config||{})},voice_config:{...profile.voice_config,...(r[0].voice_config||{})}};mode=profile.preferred_mode||mode}
async function loadOps(force=false){
  if(!session)return;
  if(!force&&Date.now()-opsLoadedAt<15000)return;
  const q="?user_id=eq."+encodeURIComponent(session.user.id)+"&order=created_at.desc&limit=20";
  const [a,j,d,i]=await Promise.all([
    supa("/rest/v1/jarvis_automations"+q).catch(()=>[]),
    supa("/rest/v1/jarvis_remote_jobs"+q).catch(()=>[]),
    supa("/rest/v1/jarvis_devices"+q).catch(()=>[]),
    supa("/rest/v1/jarvis_integrations"+q).catch(()=>[])
  ]);
  automations=a||[];jobs=j||[];devices=d||[];integrations=i||[];opsLoadedAt=Date.now();
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
      <nav class="authNav"><button type="button" data-public-section="product">Product</button><button type="button" data-public-section="capabilities">Capabilities</button><button type="button" data-public-section="safety">Safety</button><button type="button" data-public-section="company">Company</button></nav>
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

      <div class="heroRobot" id="heroRobot" aria-hidden="true">
        <div class="heroRobotDepth">
          <img id="ashHeroRobot" src="/images/ash-home-robot.webp" width="148" height="148" alt="" decoding="async" fetchpriority="high">
        </div>
        <div class="heroRobotStatus"><i></i><span>ASH</span></div>
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

    <section class="publicInfo" id="publicInfo">
      <article class="publicSection" id="product">
        <p class="kicker">PRODUCT</p>
        <h2>Ash is an AI command center, not a single model.</h2>
        <p>Ash combines conversational AI, software building, automation, connected tools, voice interaction and optional local AI in one interface. Cloud features use configured providers and Supabase services; local features require the Ash desktop worker and a supported local model.</p>
      </article>
      <article class="publicSection" id="capabilities">
        <p class="kicker">CAPABILITIES</p>
        <h2>What Ash can actually do today.</h2>
        <div class="publicGrid">
          <span><b>Reason & chat</b><small>Adaptive and multi-agent cloud reasoning when providers are available.</small></span>
          <span><b>Build software</b><small>Generate projects, install dependencies, run builds, repair failures and report evidence through a linked desktop.</small></span>
          <span><b>Automate work</b><small>Schedule supported jobs and dispatch them through Ash's cloud/desktop workflow.</small></span>
          <span><b>Work locally</b><small>Use Ollama or Ash's direct offline Python/GGUF fallback when configured on your computer.</small></span>
          <span><b>Voice</b><small>Speech input and spoken responses where the browser/device and configured voice service support them.</small></span>
          <span><b>Connected tools</b><small>Permission-based integrations such as Google services where the connector is configured and authorized.</small></span>
        </div>
      </article>
      <article class="publicSection" id="safety">
        <p class="kicker">SAFETY & CONTROL</p>
        <h2>You stay in control of consequential actions.</h2>
        <p>Ash is designed to distinguish suggestions from actions that actually happened. Sensitive external actions can require confirmation, connected services use their own authorization scopes, and system diagnostics expose degraded services instead of pretending everything worked.</p>
        <p class="publicFine">Ash can make mistakes. Verify important outputs before relying on them, especially for financial, legal, medical, security or irreversible decisions.</p>
      </article>
      <article class="publicSection" id="company">
        <p class="kicker">COMPANY / PROJECT</p>
        <h2>Independent software project.</h2>
        <p>Ash is an independent project developed by Jake Harvey. This page does not claim that Ash is a registered company unless and until a legal entity is formally established.</p>
        <p class="publicFine">Ash is not affiliated with or endorsed by OpenAI, Anthropic, Google, Microsoft, Meta, Marvel, or other third-party model, platform or media brands unless an official partnership is explicitly announced. Third-party names are used only to identify compatible services or integrations.</p>
      </article>
      <footer class="publicFooter">
        <span>© 2026 Ash project.</span>
        <button type="button" data-public-section="safety">Safety</button>
        <button type="button" data-public-section="company">About</button>
      </footer>
    </section>
  </section>`;
}
function stat(label,value,meta){return `<div class="stat card"><span>${label}</span><strong>${value}</strong><small>${meta}</small></div>`}
function voiceCore(){
  const labels={idle:["Ready","Waiting for your command"],listening:["Listening","Voice channel open"],thinking:["Thinking","Specialists are reasoning"],building:["Building","Generating and verifying software"],acting:["Acting","Executing a verified tool"],speaking:["Speaking","Voice synthesis active"],offline:["Local brain","No cloud required"]};
  const [title,sub]=labels[coreState]||labels.idle;
  const localReady=devices.some(d=>d.capabilities?.local_ai||d.capabilities?.builder);
  return `<section class="voiceCore card core-${coreState}" id="voiceCore" data-state="${coreState}">
    <div class="reactor ashSphere" id="ashSphere">
      <canvas id="ashCoreCanvas" width="420" height="420" aria-hidden="true"></canvas>
      <div class="reactorRing ring1"></div><div class="reactorRing ring2"></div><div class="reactorRing ring3"></div>
      <div class="reactorCore"><span>A</span></div>
      <span class="coreOrbit orbitA"></span><span class="coreOrbit orbitB"></span><span class="coreOrbit orbitC"></span>
    </div>
    <div class="voiceCoreCopy"><p class="kicker">ASH CORE / ${esc(coreState.toUpperCase())}</p><h2>${esc(title)}</h2><p>${esc(coreDetail||sub)}</p><div class="coreTelemetry"><span><i></i>${mode==="high"?"Multi-agent":"Adaptive"} intelligence</span><span><i></i>${localReady?"Local execution ready":"Cloud workspace"}</span><span><i></i>Confirmation guard active</span></div></div>
    <div class="voiceState ${coreState}"><span></span>${esc(title)}</div>
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
function scrollFeed(smooth=true){const feed=document.querySelector(".feed");if(feed)requestAnimationFrame(()=>feed.scrollTo({top:feed.scrollHeight,behavior:smooth?"smooth":"auto"}))}
function chatArticle(m,i){return `<article class="${m.role==="user"?"mine":"ash"}"><small>${m.role==="user"?"YOU":esc(profile.assistant_name).toUpperCase()}</small><p>${esc(m.content)}</p>${actionCard(m,i)}</article>`}
function appendChatMessage(m,i){const feed=document.querySelector(".feed");if(!feed)return false;const empty=feed.querySelector(".emptyPrompt");if(empty)empty.remove();feed.insertAdjacentHTML("beforeend",chatArticle(m,i));while(feed.children.length>12)feed.firstElementChild?.remove();scrollFeed(true);return true}
function setSendBusy(active){const b=document.querySelector("#send");if(b){b.disabled=active;b.textContent=active?"…":"↗"}}
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
  setCoreState("building","Project queued for the Ash Builder. Waiting for desktop execution.");
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
  await loadOps(true);
  render();
  toast(devices.length?"Build queued for Ash desktop.":"Build queued. Link the Ash desktop worker to start it.");
}
function automationView(){
  return `${topbar("Automations","ASH / WORKFLOWS")}<section class="automationGrid"><div class="card createAuto"><p class="kicker">NEW AUTOMATION</p><h2>Put recurring work on autopilot.</h2><p class="quiet">Ash schedules the job in the cloud and dispatches it to your linked desktop when it is time.</p><label>Name<input id="autoName" placeholder="Morning project brief"></label><label>What should Ash do?<textarea id="autoPrompt" rows="4" placeholder="Review my active project and prepare the next actions."></textarea></label><div class="formGrid"><label>Schedule<select id="autoType"><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="interval">Every N minutes</option><option value="once">Once</option></select></label><label id="whenLabel">First run<input id="autoWhen" type="datetime-local"></label></div><label id="intervalWrap" class="hidden">Repeat every<input id="autoInterval" type="number" min="1" value="60"> minutes</label><div class="formGrid"><label>Mode<select id="autoMode"><option>instant</option><option selected>medium</option><option>high</option></select></label><label>Desktop<select id="autoDevice"><option value="">Any linked desktop</option>${devices.map(d=>`<option value="${d.id}">${esc(d.nickname||d.device_name)}</option>`).join("")}</select></label></div><label class="check"><input id="autoConfirm" type="checkbox"> Ask before consequential actions</label><button id="createAuto" class="primary wide">Create automation</button></div><div class="card autoList"><div class="panelTitle"><div><p class="kicker">SCHEDULED</p><h3>Your automations</h3></div><span class="count">${automations.length}</span></div>${automations.length?automations.map(a=>`<div class="autoItem"><div><span class="statusDot ${a.enabled?"on":""}"></span><b>${esc(a.name)}</b><p>${esc(a.description||a.action_config?.prompt||"")}</p><small>${esc(a.trigger_type)} · next ${fmt(a.next_run_at)}</small></div><button data-toggle-auto="${a.id}" data-enabled="${a.enabled}">${a.enabled?"Pause":"Resume"}</button></div>`).join(""):`<div class="emptyState"><p>No automations yet.</p><small>Create one on the left.</small></div>`}</div></section>`;
}

function liveDesktop(){
  return devices.find(d=>d.last_seen_at&&Date.now()-new Date(d.last_seen_at).getTime()<120000)||null;
}
function healthBadge(label,value){
  const ok=["online","ready","healthy","active"].includes(value),warn=["degraded","unknown"].includes(value);
  return `<div class="healthItem"><span class="healthDot ${ok?"ok":warn?"warn":"bad"}"></span><div><b>${esc(label)}</b><small>${esc(value)}</small></div></div>`;
}
function healthPanel(){
  return `<section class="card healthPanel"><div class="activityHeader"><div><p class="kicker">SELF DIAGNOSTICS</p><h2>Ash system health</h2></div><button id="runHealth" class="secondary">Run diagnostics</button></div><div class="healthGrid">${healthBadge("AI gateway",healthState.gateway)}${healthBadge("Session",healthState.session)}${healthBadge("Desktop",healthState.desktop)}${healthBadge("Local AI",healthState.local)}${healthBadge("Voice",healthState.voice)}${healthBadge("PWA",healthState.pwa)}</div><p class="quiet healthNote">${healthState.checkedAt?"Last checked "+relative(healthState.checkedAt):"Run diagnostics to verify every execution path."}</p></section>`;
}
async function probeHealth(showToast=false){
  const next={...healthState,checkedAt:new Date().toISOString()};
  try{
    await ensureFreshSession();
    const auth=await authedFetch(BASE+"/auth/v1/user",{method:"GET"});
    next.session=auth.ok?"healthy":"degraded";
  }catch{next.session="offline"}
  try{
    const g=await authedFetch(GATEWAY+"?action=health",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});
    const d=await g.json().catch(()=>({}));
    next.gateway=g.ok&&d.ok?(d.cloud_ready?"online":"degraded"):"offline";
    next.voice=g.ok&&d.voice_ready?"ready":"degraded";
  }catch{next.gateway="offline";next.voice="unknown"}
  const desk=liveDesktop();
  next.desktop=desk?"online":"offline";
  next.local=desk&&(desk.capabilities?.offline_brain||desk.capabilities?.local_ai)?"ready":"unavailable";
  try{
    const reg=await navigator.serviceWorker?.getRegistration?.();
    next.pwa=reg?"active":"degraded";
  }catch{next.pwa="unknown"}
  healthState=next;
  if(document.querySelector(".healthPanel"))render();
  if(showToast)toast(next.gateway==="online"?"Diagnostics complete":"Diagnostics found a degraded path");
  return next;
}
async function rescueThroughDesktop(message){
  const desk=liveDesktop();
  if(!desk||!(desk.capabilities?.offline_brain||desk.capabilities?.local_ai))throw new Error("No local Ash desktop is online.");
  setCoreState("offline","Cloud unavailable. Rescue Mode handed this request to your local Ash brain.");
  const created=await supa("/rest/v1/jarvis_remote_jobs",{
    method:"POST",
    headers:{Prefer:"return=representation"},
    body:JSON.stringify({
      user_id:session.user.id,
      target_device_id:desk.id,
      kind:"chat_fallback",
      mode,
      payload:{prompt:message,rescue:true,source:"chat"},
      status:"queued",
      requires_confirmation:false
    })
  });
  const id=created?.[0]?.id;
  if(!id)throw new Error("Could not queue Rescue Mode.");
  for(let attempt=0;attempt<30;attempt++){
    await new Promise(r=>setTimeout(r,1200));
    const rows=await supa("/rest/v1/jarvis_remote_jobs?id=eq."+encodeURIComponent(id)+"&select=id,status,result,error");
    const job=rows?.[0];
    if(job?.status==="completed")return job.result?.summary||"Local Ash completed the request.";
    if(job?.status==="failed")throw new Error(job.error||"Local Ash could not complete the request.");
  }
  throw new Error("Rescue Mode is still running on your desktop. Check Activity for the result.");
}

function activityView(){return `${topbar("Activity","ASH / OPERATIONS")}${healthPanel()}<section class="card activityPanel"><div class="activityHeader"><div><p class="kicker">EXECUTION LOG</p><h2>What Ash has been doing</h2></div><button id="refreshOps" class="secondary">Refresh</button></div>${jobs.length?jobs.map(j=>`<div class="activityRow"><div class="activityMark ${j.status}">${j.status==="completed"?"✓":j.status==="failed"?"!":"→"}</div><div><b>${esc(j.payload?.automation_name||j.payload?.prompt||j.kind)}</b><p>${esc(j.error||j.result?.summary||"")}</p><small>${fmt(j.created_at)} · ${esc(j.status)}</small></div><span class="badge">${esc(j.mode)}</span></div>`).join(""):`<div class="emptyState"><p>No activity yet.</p><small>Scheduled and remote tasks will appear here.</small></div>`}</section>`}
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
      const r=await authedFetch(INTEGRATIONS+"?action=start&integration="+encodeURIComponent(key)+"&return_url="+encodeURIComponent(returnUrl));
      const d=await r.json();
      if(!r.ok)throw new Error(d.error||"Connection setup failed");
      await openUrl(d.authorization_url);
      toast("Continue in Google to connect "+item.name);
    }catch(e){toast(e.message||"Connection setup failed")}
    return;
  }
  const body={user_id:session.user.id,integration_key:key,display_name:item.name,status:"disconnected",config:{requested_scopes:item.permissions,platform:nativeState.available?"android":"web",oauth_required:true}};
  await supa("/rest/v1/jarvis_integrations",{method:"POST",headers:{Prefer:"resolution=merge-duplicates,return=representation"},body:JSON.stringify(body)}).catch(()=>{});
  await loadOps(true);render();
  toast(item.name+" connector is ready for provider-specific OAuth.");
}
function teamView(){const names=[["Chief Orchestrator","Turns goals into coordinated work."],["Project Manager","Sequences tasks and tracks delivery."],["Business Analyst","Clarifies requirements and constraints."],["Research Analyst","Finds and verifies information."],["Software Architect","Shapes systems and technical decisions."],["Frontend Engineer","Builds product interfaces."],["Backend Engineer","Builds APIs, data and services."],["Desktop Engineer","Handles local computer workflows."],["Mobile Engineer","Builds mobile experiences."],["AI Engineer","Handles models, routing and prompts."],["Security Engineer","Reviews risk and permissions."],["QA Engineer","Tests behavior and catches regressions."]];return `${topbar("Organization","ASH / SPECIALISTS")}<section class="orgIntro"><h2>One assistant in front.<br>Specialists behind it.</h2><p>Ash chooses internal roles based on the task. You never have to manage the organization manually.</p></section><section class="orgGrid">${names.map(([n,d],i)=>`<div class="card specialist"><span>${String(i+1).padStart(2,"0")}</span><div><b>${n}</b><p>${d}</p></div></div>`).join("")}</section>`}
function settingsView(){return `${topbar("Preferences","ASH / YOU")}<section class="settingsGrid"><div class="card settings"><p class="kicker">IDENTITY</p><label>Assistant name<input id="assistantName" value="${esc(profile.assistant_name)}"></label><label>Wake word<input id="wakeWord" value="${esc(profile.wake_word)}"></label><div class="formGrid"><label>Personality<select id="personality">${["adaptive","executive","companion","builder","analyst","coach"].map(x=>`<option ${profile.personality_preset===x?"selected":""}>${x}</option>`).join("")}</select></label><label>Verbosity<select id="verbosity">${["concise","balanced","detailed"].map(x=>`<option ${profile.behavior_config?.verbosity===x?"selected":""}>${x}</option>`).join("")}</select></label></div><div class="formGrid"><label>Proactivity<select id="proactivity">${["quiet","balanced","proactive"].map(x=>`<option ${profile.behavior_config?.proactivity===x?"selected":""}>${x}</option>`).join("")}</select></label><label>Humor<input id="humor" type="range" min="0" max="100" value="${Number(profile.behavior_config?.humor??20)}"></label></div><label>Voice<select id="voice"><option value="cjVigY5qzO86Huf0OWal">Eric · smooth</option><option value="EXAVITQu4vr4xnSDxMaL">Sarah · confident</option></select></label><label class="check"><input id="speak" type="checkbox" ${profile.voice_config?.auto_speak!==false?"checked":""}> Speak responses automatically</label><label>Custom instructions<textarea id="instructions" rows="5">${esc(profile.custom_instructions||"")}</textarea></label><button id="save" class="primary wide">Save preferences</button></div><div class="sideStack"><div class="card about"><p class="kicker">ABOUT</p><h3>Ash</h3><p>Developed by Jake Harvey.</p><p class="quiet">Ash is designed around user control, explicit permissions and verifiable action status.</p></div><div class="card devicePanel"><p class="kicker">DEVICES</p><h3>Linked computers</h3>${devices.length?devices.map(d=>`<div class="device"><span class="statusDot ${d.last_seen_at&&Date.now()-new Date(d.last_seen_at).getTime()<120000?"on":""}"></span><div><b>${esc(d.nickname||d.device_name)}</b><small>${esc(d.platform)} · ${relative(d.last_seen_at)}</small></div></div>`).join(""):`<p class="quiet">No desktop has checked in yet.</p>`}</div><button id="signout" class="danger">Sign out</button></div></section>`}
function initHeroRobot(){
  heroVisualCleanup?.();heroVisualCleanup=null;
  const host=document.querySelector("#heroRobot");
  const card=document.querySelector(".heroRobotDepth");
  const image=document.querySelector("#ashHeroRobot");
  if(!host||!card||!image)return;

  const reduce=matchMedia("(prefers-reduced-motion: reduce)").matches;
  let raf=0,targetX=0,targetY=0,currentX=0,currentY=0;
  const renderDepth=()=>{
    currentX+=(targetX-currentX)*.09;
    currentY+=(targetY-currentY)*.09;
    card.style.transform=reduce
      ?"perspective(900px) rotateX(0deg) rotateY(0deg) translateZ(0)"
      :`perspective(900px) rotateX(${currentY.toFixed(2)}deg) rotateY(${currentX.toFixed(2)}deg) translateZ(22px)`;
    if(!reduce)raf=requestAnimationFrame(renderDepth);
  };
  const move=e=>{
    const r=host.getBoundingClientRect();
    targetX=((e.clientX-r.left)/Math.max(r.width,1)-.5)*7;
    targetY=-((e.clientY-r.top)/Math.max(r.height,1)-.5)*5;
  };
  const reset=()=>{targetX=0;targetY=0};
  host.addEventListener("pointermove",move,{passive:true});
  host.addEventListener("pointerleave",reset,{passive:true});
  image.dataset.asset="user-upload-exact";
  if(!reduce)raf=requestAnimationFrame(renderDepth);
  heroVisualCleanup=()=>{
    cancelAnimationFrame(raf);
    host.removeEventListener("pointermove",move);
    host.removeEventListener("pointerleave",reset);
  };
}
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
function setCoreState(state,detail=""){
  coreState=state||"idle";coreDetail=detail||({
    idle:"Systems ready. Speak or type a command.",
    listening:"I'm listening.",
    thinking:"Reasoning across the best available specialists.",
    building:"Writing files, running builds and repairing failures.",
    acting:"Executing the authorized action and checking the result.",
    speaking:"Voice output synchronized to the Ash Core.",
    offline:"Running from the private on-device Python brain."
  }[coreState]||"Systems ready.");
  const core=document.querySelector("#voiceCore");
  if(core){core.dataset.state=coreState;core.className=`voiceCore card core-${coreState}`;}
  const title=core?.querySelector(".voiceCoreCopy h2"),copy=core?.querySelector(".voiceCoreCopy p:not(.kicker)"),stateEl=core?.querySelector(".voiceState");
  const label={idle:"Ready",listening:"Listening",thinking:"Thinking",building:"Building",acting:"Acting",speaking:"Speaking",offline:"Local brain"}[coreState]||"Ready";
  if(title)title.textContent=label;if(copy)copy.textContent=coreDetail;if(stateEl){stateEl.className=`voiceState ${coreState}`;stateEl.lastChild.textContent=label}
}
function setVoiceState(active){speaking=active;setCoreState(active?"speaking":"idle")}
function initAshCore(){
  const canvas=document.querySelector("#ashCoreCanvas");if(!canvas||canvas.dataset.ready)return;canvas.dataset.ready="1";
  const lowPower=(navigator.deviceMemory&&navigator.deviceMemory<=4)||(navigator.hardwareConcurrency&&navigator.hardwareConcurrency<=4);const mobile=window.innerWidth<650;const size=mobile?280:360;canvas.width=size;canvas.height=size;const ctx=canvas.getContext("2d",{alpha:true}),count=mobile?(lowPower?42:58):(lowPower?72:104);
  const pts=Array.from({length:count},(_,i)=>{const a=Math.random()*Math.PI*2,z=Math.random()*2-1,r=Math.sqrt(1-z*z);return{a,z,r,seed:Math.random()*20,i}});
  let frame=0,last=0;
  const draw=t=>{
    if(!canvas.isConnected)return;
    if(document.hidden){requestAnimationFrame(draw);return}
    const minFrame=mobile||lowPower?33:22;if(t-last<minFrame){requestAnimationFrame(draw);return}last=t;frame++;
    const w=canvas.width,h=canvas.height,cx=w/2,cy=h/2,state=coreState;
    const speed={idle:.0018,listening:.0035,thinking:.0055,building:.0048,acting:.006,speaking:.004,offline:.0024}[state]||.002;
    const pulse=1+Math.sin(t*(state==="speaking"?.008:.003))*({idle:.02,listening:.05,thinking:.08,building:.07,acting:.09,speaking:.12,offline:.035}[state]||.03);
    ctx.clearRect(0,0,w,h);
    const accent=getComputedStyle(document.documentElement).getPropertyValue("--accent").trim()||"#f59e0b";
    pts.forEach(p=>{
      p.a+=speed*(.65+(p.i%7)/10);
      const x3=p.r*Math.cos(p.a),y3=p.z,z3=p.r*Math.sin(p.a);
      const persp=1/(1.55-z3*.5),rad=142*pulse*persp;
      const x=cx+x3*rad,y=cy+y3*rad;
      const alpha=.18+.72*((z3+1)/2);
      const size=.75+2.2*((z3+1)/2);
      ctx.globalAlpha=alpha;ctx.fillStyle=accent;ctx.beginPath();ctx.arc(x,y,size,0,Math.PI*2);ctx.fill();
    });
    ctx.globalAlpha=.22;ctx.strokeStyle=accent;ctx.lineWidth=1.2;
    for(let i=0;i<3;i++){ctx.beginPath();ctx.ellipse(cx,cy,118+i*18,48+i*8,t*.00015+i*.7,0,Math.PI*2);ctx.stroke()}
    ctx.globalAlpha=1;requestAnimationFrame(draw);
  };requestAnimationFrame(draw);
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
function render(){heroVisualCleanup?.();heroVisualCleanup=null;applyTheme();document.querySelector("#app").innerHTML=session?shell(view==="home"?home():view==="builder"?builderView():view==="automation"?automationView():view==="activity"?activityView():view==="connections"?connectionsView():view==="team"?teamView():settingsView()):authView();bind();if(!session){initCinematicMotion();initHeroRobot()}else initAshCore()}
function bind(){
  document.querySelector("#themeToggle")?.addEventListener("click",toggleTheme);
  document.querySelector("#meetAsh")?.addEventListener("click",()=>document.querySelector("#email")?.focus());
  document.querySelector("#watchVoice")?.addEventListener("click",()=>{toast("Sign in and ask Ash anything to hear the live voice visualization.")});
  document.querySelectorAll("[data-public-section]").forEach(b=>b.addEventListener("click",()=>{
    document.querySelector("#"+b.dataset.publicSection)?.scrollIntoView({behavior:"smooth",block:"start"});
  }));
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
        if(!session){
          if(d.signup_state==="existing_or_obfuscated"){
            m.textContent="If this email already has an account, sign in or use Forgot password.";
          }else{
            m.textContent="Account created. You can sign in with the same email and password.";
          }
          return
        }
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
  document.querySelector("#signout")?.addEventListener("click",()=>{clearSession();render()});
  document.querySelector("#refreshOps")?.addEventListener("click",async()=>{await loadOps(true);render();toast("Activity refreshed")});
  document.querySelector("#runHealth")?.addEventListener("click",()=>probeHealth(true));
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
  await loadOps(true);render();toast("Automation created");
}
async function toggleAutomation(id,enabled){await supa("/rest/v1/jarvis_automations?id=eq."+encodeURIComponent(id),{method:"PATCH",body:JSON.stringify({enabled:!enabled,updated_at:new Date().toISOString()})});await loadOps(true);render()}
async function confirmPendingAction(index){
  const m=messages[index]; if(!m?.action)return;
  const tool=m.action.tool,args=m.action.args||{};
  try{
    const r=await authedFetch(INTEGRATIONS+"?action="+encodeURIComponent(tool),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(tool==="gmail.send"?{...args,confirmed:true}:{event:args.event||args,confirmed:true})});
    const d=await r.json(); if(!r.ok)throw new Error(d.error||"Action failed");
    m.content=tool==="gmail.send"?"Email sent successfully.":"Calendar event created successfully.";
    m.action=null; render(); toast("Action completed");
  }catch(e){toast(e.message||"Action failed")}
}
async function send(){if(sending)return;const box=document.querySelector("#prompt"),message=box?.value.trim();if(!message)return;box.value="";const userMsg={role:"user",content:message};messages.push(userMsg);appendChatMessage(userMsg,messages.length-1);sending=true;setSendBusy(true);setCoreState("thinking","Working the request across Ash intelligence.");try{const r=await authedFetch(GATEWAY,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"chat",message,mode,history:messages.slice(-10,-1)})});const d=await r.json();if(!r.ok)throw new Error(r.status===401?"Your Ash session expired. Sign in again.":d.error||"Ash cloud is unavailable.");const reply={role:"assistant",content:d.answer||"Done.",action:d.pending_action||null};messages.push(reply);appendChatMessage(reply,messages.length-1);speak(d.answer)}catch(e){let text=e.message||"Ash cloud is unavailable.";try{const local=await rescueThroughDesktop(message);text="Rescue Mode · "+local}catch(rescueError){if(!/session expired/i.test(text))text+=" Local rescue is unavailable too: "+(rescueError.message||"desktop offline.")}const reply={role:"assistant",content:text};messages.push(reply);appendChatMessage(reply,messages.length-1)}finally{sending=false;setSendBusy(false);if(!speaking)setCoreState("idle")}}
function listen(){const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!SR){toast("Voice input needs a supported browser.");return}setCoreState("listening");const r=new SR();r.lang=navigator.language||"en-US";r.onresult=e=>{document.querySelector("#prompt").value=e.results[0][0].transcript;send()};r.onerror=()=>toast("I couldn't hear that clearly.");r.start()}
async function speak(text){
  if(!text||profile.voice_config?.auto_speak===false)return;
  try{
    const r=await authedFetch(GATEWAY,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"speech",text:text.slice(0,5000),voice_id:profile.voice_config?.voice_id})});
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
    try{await Promise.all([loadProfile(),loadOps()]);await probeHealth(false)}catch{}
  }

  render();
})();