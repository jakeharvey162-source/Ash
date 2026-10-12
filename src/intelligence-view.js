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
   '<section class="card" style="margin-top:20px;padding:20px"><h3>Live public earth events</h3>'+
   '<p>Read the US Geological Survey’s public earthquake feed on demand. Data can be delayed or incomplete and is not an emergency alert service.</p>'+
   '<button type="button" id="loadPublicQuakes" class="secondary">Load recent earthquakes</button>'+
   '<p id="publicQuakeStatus" role="status" class="quiet">No network request yet.</p>'+ 
   '<div id="publicQuakeMap" aria-live="polite"><p class="quiet">Load recent earthquakes to see their positions on a world coordinate map.</p></div>'+
   '<div id="publicQuakeResults" class="scopeList" aria-live="polite"></div></section>'+
   '<section class="card" style="margin-top:20px;padding:20px"><h3>Desktop integration</h3>'+
   '<p>On your paired Windows machine run <code>python -m desktop_worker.intelligence_hub catalog</code>. Configure Wazuh locally, or import an existing authorized SpiderFoot/Strix JSON report. Then ask the local Ash agent to list the intelligence catalog, view Wazuh agents, or summarize a report inside its workspace.</p>'+
   '<p class="quiet">Only Wazuh inventory and bounded JSON report summaries have local adapters. A visual 3D world view, a ShadowBroker installation, live event correlation and user-specific connectors still require separate integration and testing.</p></section>';
}

export async function fetchPublicEarthquakes(fetcher=fetch){
  const url="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson";
  const res=await fetcher(url,{method:"GET",cache:"no-store",credentials:"omit"});
  if(!res.ok)throw new Error("USGS source returned HTTP "+res.status);
  const json=await res.json();
  if(!Array.isArray(json?.features))throw new Error("Unexpected USGS source format");
  return json.features.slice(0,12).filter(e=>
    Number.isFinite(Number(e?.properties?.mag))&&
    Number.isFinite(Number(e?.geometry?.coordinates?.[0]))&&
    Number.isFinite(Number(e?.geometry?.coordinates?.[1]))&&
    Number(e.geometry.coordinates[0])>=-180&&Number(e.geometry.coordinates[0])<=180&&
    Number(e.geometry.coordinates[1])>=-90&&Number(e.geometry.coordinates[1])<=90
  ).map(e=>({
    label:String(e.properties.place||"Unknown region").slice(0,140),
    magnitude:Number(e.properties.mag),
    timestamp:Number(e.properties.time),
    longitude:Number(e.geometry.coordinates[0]),
    latitude:Number(e.geometry.coordinates[1])
  }));
}
/** A bounded, decorative coordinate plot of public events; not a live satellite view. */
export function renderEarthEventMap(events){
  if(!events.length)return '<p class="quiet">No mappable events returned by the public source.</p>';
  const lines=[90,180,270,360,450,540,630].map(x=>'<line x1="'+x+'" y1="0" x2="'+x+'" y2="360"/>').join("")+
    [90,180,270].map(y=>'<line x1="0" y1="'+y+'" x2="720" y2="'+y+'"/>').join("");
  const markers=events.filter(e=>Number.isFinite(e.longitude)&&Number.isFinite(e.latitude)&&e.longitude>=-180&&e.longitude<=180&&e.latitude>=-90&&e.latitude<=90).map(e=>{
    const x=((e.longitude+180)/360*720).toFixed(2),y=((90-e.latitude)/180*360).toFixed(2);
    return '<circle cx="'+x+'" cy="'+y+'" r="'+Math.max(3,Math.min(9,Number(e.magnitude)||3))+'" fill="#42e8c6" fill-opacity="0.88" stroke="#111827" stroke-width="1.5"><title>'+escapeHtml('M'+e.magnitude.toFixed(1)+' · '+e.label)+'</title></circle>';
  }).join("");
  return '<figure style="margin:12px 0"><svg role="img" aria-label="World coordinates showing '+events.length+' recently reported public earthquakes. Positions are approximate; not a detailed geographic map." viewBox="0 0 720 360" style="display:block;width:100%;max-height:360px;border:1px solid #26394d;border-radius:12px;background:#101b2e"><g stroke="#43627b" stroke-opacity=".45" stroke-width="1">'+lines+'</g><path d="M360 0V360M0 180H720" stroke="#87a4c0" stroke-opacity=".5" stroke-width="1.5"/>'+markers+'</svg><figcaption class="quiet">Longitude / latitude plot · dots show reported positions, not exact impact areas. USGS data may be delayed.</figcaption></figure>';
}

export async function loadPublicEarthquakesView(fetcher=fetch){
  const status=document.getElementById("publicQuakeStatus");
  const results=document.getElementById("publicQuakeResults");
  const map=document.getElementById("publicQuakeMap");
  if(!status||!results||!map)return;
  status.textContent="Contacting USGS public feed...";
  results.replaceChildren();
  map.replaceChildren();
  try{
    const events=await fetchPublicEarthquakes(fetcher);
    if(!status.isConnected||!results.isConnected)return;
    status.textContent="USGS public records · "+events.length+" shown · informational only; feeds can be delayed.";
    if(map.isConnected)map.innerHTML=renderEarthEventMap(events);
    for(const quake of events){
      const p=document.createElement("p");
      const when=Number.isFinite(quake.timestamp)?new Date(quake.timestamp).toISOString():"time unavailable";
      p.textContent="M"+quake.magnitude.toFixed(1)+" · "+quake.label+" · "+when;
      results.appendChild(p);
    }
  }catch(e){
    if(status.isConnected)status.textContent="Public feed unavailable: "+(e?.message||"network error")+". No live information verified.";
    if(map.isConnected)map.textContent="World event map unavailable.";
  }
}
