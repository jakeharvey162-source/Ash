/** Ash Business Desk: a client handoff on top of the existing authorized desktop builder.
 * No money movement, outbound customer contact, or synthetic payment verification.
 */
export const BUSINESS_LIMITS = Object.freeze({
  client: 100,
  email: 254,
  request: 3500,
  title: 100,
});

export function prepareClientBuild(input) {
  const client = String(input?.client || "").trim();
  const email = String(input?.email || "").trim();
  const request = String(input?.request || "").trim();
  const project = String(input?.project || "").trim() || "Customer website";
  const preset = String(input?.design_preset || "midnight-studio");
  if (!client || client.length > BUSINESS_LIMITS.client) throw Error("Enter the customer's name (up to 100 characters).");
  if (!/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(email) || email.length > BUSINESS_LIMITS.email)
    throw Error("Enter a valid customer email.");
  if (request.length < 15 || request.length > BUSINESS_LIMITS.request) throw Error("Describe what the customer needs (15–3,500 characters).");
  if (project.length > BUSINESS_LIMITS.title) throw Error("Project name is too long.");
  const presets = ["editorial-luxe","midnight-studio","warm-commerce","clean-enterprise"];
  if (!presets.includes(preset)) throw Error("Choose a supported design style.");
  const brief = "Build an original, usable, accessible and responsive client website.\n"+
    "Project: "+project+"\nClient: "+client+"\nRequirements:\n"+request+
    "\nDeliver a local preview and evidence of a real build. Do not email, publish, purchase anything or claim customer acceptance or payment. Ask the owner to review the result before any handoff.";
  return {
    kind: "builder",
    mode: "high",
    status: "queued",
    requires_confirmation: false,
    payload: {
      prompt: brief,
      builder: true,
      executor: "desktop",
      source: "business_desk",
      create_admin: false,
      design_preset: preset,
      business_client: { name: client, email, project },
      requires_owner_review: true,
      external_delivery_authorized: false,
    },
  };
}

export function businessBuildState(job) {
  const status = String(job?.status || "unknown");
  const passed = job?.result?.verification?.build_passed === true &&
    job?.result?.quality_report?.verified_build === true;
  if (status === "failed") return {label:"Needs attention",ready:false};
  if (status === "cancelled") return {label:"Cancelled",ready:false};
  if (status === "completed" && passed) return {label:"Built · owner review needed",ready:true};
  if (status === "completed") return {label:"Build finished · not verified",ready:false};
  if (status === "waiting_for_confirmation") return {label:"Owner approval needed",ready:false};
  return {label:status==="queued"?"Waiting for your desktop":status==="running"||status==="claimed"?"Ash is building":"Check activity",ready:false};
}

export function renderBusinessDesk({jobs=[],devices=[],draft={}}, escapeText) {
  const safe=(s)=>escapeText(String(s??""));
  const entries=jobs.filter(j=>j?.kind==="builder" && j?.payload?.source==="business_desk");
  const live=devices.some(d=>d?.last_seen_at && Date.now()-new Date(d.last_seen_at).getTime()<120000);
  const projects=entries.length?entries.map(j=>{
    const client=j.payload?.business_client||{}, state=businessBuildState(j);
    const summary=String(j.result?.summary||j.error||"").slice(0,180);
    const safeUrl=String(j.result?.preview_url||"");
    const localPreview=/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(safeUrl);
    return '<div class="autoItem"><div><b>'+safe(client.project||"Client website")+'</b>'+
      '<p>'+safe(client.name)+' · '+safe(client.email)+'</p>'+
      '<small>'+safe(state.label)+'</small>'+
      (summary?'<p class="quiet">'+safe(summary)+'</p>':"")+
      (state.ready?'<p class="quiet">Review the actual result. Client delivery needs your approval. Payment has not been verified.</p>':"")+
      (localPreview?'<p class="quiet">A preview is running only on the paired computer, not publicly hosted.</p>':"")+
      '</div></div>';
  }).join(""):'<div class="emptyState"><p>No customer websites queued yet.</p><small>Start with a brief on the left.</small></div>';
  return '<section class="automationGrid">'+
    '<div class="card createAuto"><p class="kicker">ASH / BUSINESS DESK</p><h2>Give Ash a customer project.</h2>'+
    '<p class="quiet">Ash will send your brief to the linked desktop builder. You review the result before it reaches anyone else.</p>'+
    '<label>Customer name<input id="businessClient" data-business-field="client" maxlength="100" autocomplete="off" placeholder="e.g. Artisan Brew Hub" value="'+safe(draft.client)+'" required></label>'+
    '<label>Customer email<input id="businessEmail" data-business-field="email" type="email" maxlength="254" autocomplete="off" placeholder="client@example.com" value="'+safe(draft.email)+'" required></label>'+
    '<label>Project name<input id="businessProject" data-business-field="project" maxlength="100" value="'+safe(draft.project??"Customer website")+'" required></label>'+
    '<label>What should Ash build?<textarea id="businessRequest" data-business-field="request" rows="6" maxlength="3500" placeholder="Describe the pages, colours, forms and features the customer wants." required>'+safe(draft.request)+'</textarea></label>'+
    '<label>Design style<select id="businessPreset" data-business-field="design_preset">'+[["midnight-studio","Midnight Studio"],["editorial-luxe","Editorial Luxe"],["warm-commerce","Warm Commerce"],["clean-enterprise","Clean Enterprise"]].map(([value,label])=>'<option value="'+value+'"'+((draft.design_preset||"midnight-studio")===value?' selected':'')+'>'+label+'</option>').join('')+'</select></label>'+
    '<button type="button" id="businessCreate" class="primary wide">Create client website</button>'+
    '<p class="quiet">'+(live?"Desktop online · ready to accept build jobs.":"Desktop offline · the job will remain queued until your linked worker is online.")+'</p></div>'+
    '<div class="card autoList"><div class="panelTitle"><div><p class="kicker">CUSTOMER PROJECTS</p><h3>Builds and handoffs</h3></div><span class="count">'+entries.length+'</span></div>'+
    projects+
    '<div class="card" style="padding:16px;margin-top:14px"><h3>Before sending a website</h3>'+
    '<p class="quiet">Review its real preview, obtain customer sign-off, confirm funds directly with the payment provider, and approve delivery. Ash will not mark money as received from a screenshot or a message.</p>'+
    '<button type="button" id="businessActivity" class="secondary">View build and approval activity</button></div></div></section>'+
    '<section class="card" style="padding:20px;margin-top:18px"><p class="kicker">OWNER CONTACT</p><h3>Free alerts when Ash needs you</h3>'+
    '<p class="quiet">Get free alerts on your phone when a website build needs review or an action needs approval. Install the ntfy app on your phone, choose a private subscription topic and connect it on your paired Ash desktop. Your phone opens Ash to approve decisions. Free push alerts are not normal cellular calls, and alerts never authorize payments or trades.</p><p class="quiet">Alerts stay off until you turn them on. Do not share your private notification topic.</p><button type="button" id="businessTeam" class="secondary">Open Organization workspace</button></section>';
}
