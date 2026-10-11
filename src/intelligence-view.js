/** Honest public intelligence catalog; local connection state is never fabricated. */
export const INTELLIGENCE_MODULES = Object.freeze([
  { id: "gods-eye-view", title: "God's Eye View", type: "3D world visualization", url: "https://github.com/bilawalsidhu/gods-eye-view", status: "External app · not embedded", details: "Aircraft, maritime, satellite and hazard layers. Launch separately; availability depends on public feeds and keys." },
  { id: "shadowbroker", title: "ShadowBroker", type: "Open-source intelligence", url: "https://github.com/BigBodyCobain/Shadowbroker", status: "External app · not connected", details: "Independent OSINT dashboard. Requires its own deployment and license review." },
  { id: "wazuh", title: "Wazuh", type: "Defensive monitoring", url: "https://github.com/wazuh/wazuh", status: "Local read-only adapter · setup required", details: "Ash Desktop can request an authorized Wazuh manager's agent inventory after local credentials are configured." },
  { id: "spiderfoot", title: "SpiderFoot", type: "Authorized OSINT reports", url: "https://github.com/smicallef/spiderfoot", status: "Local report adapter · setup required", details: "Import a previously exported JSON report from an authorized investigation. No scan is started from this page." },
  { id: "strix", title: "Strix", type: "Authorized security testing", url: "https://github.com/usestrix/strix", status: "Local report adapter · setup required", details: "Import approved assessment findings as a local JSON export. No offensive action is started from this page." },
]);
function escapeHtml(v) { return String(v??"").replace(/[&<>"']/g, x => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[x])); }
export function renderIntelligenceCatalog(){
  const cards=INTELLIGENCE_MODULES.map(item=>
    '<article class="card" style="padding:20px;display:flex;flex-direction:column;gap:9px;min-width:0">'+
    '<p class="kicker">'+escapeHtml(item.type)+'</p>'+
    '<h3>'+escapeHtml(item.title)+'</h3>'+
    '<p>'+escapeHtml(item.details)+'</p>'+
    '<p class="quiet">'+escapeHtml(item.status)+'</p>'+
    '<a href="'+escapeHtml(item.url)+'" target="_blank" rel="noopener noreferrer" class="secondary" style="display:inline-block;margin-top:auto;padding:10px 12px;border-radius:10px">Open official project ↗</a>'+
    '</article>'
  ).join("");
  return '<section class="orgIntro"><h2>Explore the world. Verify the evidence.</h2>'+
   '<p>These are distinct third-party tools, not automatically connected live feeds. Ash Desktop provides read-only adapters for approved security telemetry and exported reports. This web page never launches scans or reads private networks.</p></section>'+
   '<section class="orgGrid">'+cards+'</section>'+
   '<section class="card" style="margin-top:20px;padding:20px"><h3>Desktop integration</h3>'+
   '<p>On your paired Windows machine run <code>python -m desktop_worker.intelligence_hub catalog</code>. Configure Wazuh locally, or import an existing authorized SpiderFoot/Strix JSON report. Then ask the local Ash agent to list the intelligence catalog, view Wazuh agents, or summarize a report inside its workspace.</p>'+
   '<p class="quiet">Only Wazuh inventory and bounded JSON report summaries have local adapters. A visual 3D world view, a ShadowBroker installation, live event correlation and user-specific connectors still require separate integration and testing.</p></section>';
}
