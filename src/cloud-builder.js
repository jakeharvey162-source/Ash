// Standalone artifacts never run in Ash's origin. Desktop builds remain separate.
export const MAX_SOURCE = 120000;
export const MAX_REVISIONS = 6;
export const MAX_REQUEST = 3000;

export function normalizeArtifact(answer) {
  let html = String(answer || '').trim();
  const fence = html.match(/^```(?:html)?\s*\n([\s\S]*?)\n```$/i);
  if (fence) html = fence[1].trim();
  if (html.length > MAX_SOURCE) throw new Error('The project is too large for browser builds. Use Desktop build for this project.');
  if (!/^<!doctype html>/i.test(html) || !/<html\b/i.test(html) || !/<\/html>\s*$/i.test(html) || !/<head\b/i.test(html) || !/<body\b/i.test(html) || !/<\/body>/i.test(html)) {
    throw new Error('Ash returned an incomplete HTML project. Your previous revision is safe. Try a smaller request.');
  }
  if (/<script\b[^>]*\bsrc\s*=/i.test(html) || /<link\b[^>]*\brel\s*=\s*["']?stylesheet/i.test(html)) {
    throw new Error('This project depends on external code. Browser builds need embedded CSS and JavaScript.');
  }
  if (/\b(?:gsk_|nvapi-|sk-)[A-Za-z0-9_-]{20,}/.test(html)) throw new Error('Credential-like content was detected. The project was not saved or previewed.');
  return html;
}

export function generationPrompt(request, previous = '', repair = '') {
  const brief = String(request || '').trim();
  if (!brief || brief.length > MAX_REQUEST) throw new Error(`Describe the project in 1–${MAX_REQUEST} characters.`);
  if (previous.length > 14500) throw new Error('This revision is too large for a safe full-source edit. Download it and use Desktop build to continue.');
  return `You are Ash's implementation engineer. Return ONLY a complete <!doctype html> document ending with </html>, no Markdown or commentary. Keep the ENTIRE document under 14000 characters so it can be edited later.
Build a finished standalone website or small application using embedded CSS and vanilla JavaScript. No external libraries, scripts, fonts, images, network calls, imports or dependencies. Use inline SVG and CSS artwork. Use semantic HTML, visible focus states, accessible labels, deliberate typography, responsive layouts at 360px and 1440px, and no horizontal overflow.
Implement the requested interactions fully. Use integer cents for currency arithmetic. Validate form inputs. Render user data with textContent, never innerHTML. Use localStorage for local persistence and never claim it is cloud sync. Mock bookings must clearly say they are saved locally and not sent. Do not invent testimonials, awards, proof, backend functionality or test results. Do not include credentials. Escape user data in CSV exports. Keep all links local section anchors unless the brief explicitly gives a destination.
${previous ? 'EDIT the existing project below. Preserve working functionality, localStorage keys and saved-data compatibility. Make the smallest requested change, then return the entire updated document.' : 'Build the requested project from scratch.'}
USER REQUEST:\n${brief}
${repair ? `REPAIR THESE OBSERVED ERRORS:\n${repair.slice(0,1000)}\n` : ''}${previous ? `EXISTING PROJECT:\n${previous}` : ''}`;
}

function inlineJSON(value) {
  return JSON.stringify(value).replace(/</g, '\\u003c').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
}

export function previewDocument(html, channel, savedData = {}) {
  // CSP is installed before any generated content; later policies cannot relax it.
  // No allow-same-origin, forms, popups or top-navigation capability is granted.
  const bridge = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"><script>(function(){
    const channel=${inlineJSON(channel)},data=Object.assign(Object.create(null),${inlineJSON(savedData)});
    const emit=(type,payload)=>parent.postMessage({ashPreview:channel,type,payload},'*');
    const persist=()=>emit('storage',data);
    const storage={getItem(k){return Object.hasOwn(data,String(k))?data[String(k)]:null},setItem(k,v){const key=String(k),value=String(v);if(value.length>30000||(!Object.hasOwn(data,key)&&Object.keys(data).length>=40))throw new Error('Preview storage limit reached');data[key]=value;persist()},removeItem(k){delete data[String(k)];persist()},clear(){for(const k of Object.keys(data))delete data[k];persist()},key(i){return Object.keys(data)[i]??null},get length(){return Object.keys(data).length}};
    try{Object.defineProperty(window,'localStorage',{value:storage})}catch(e){emit('error','Preview persistence could not initialize: '+e.message)}
    addEventListener('error',e=>emit('error',String(e.message||'Script or resource error').slice(0,500)),true);
    addEventListener('unhandledrejection',e=>emit('error',String(e.reason?.message||e.reason||'Unhandled promise rejection').slice(0,500)));
    const check=()=>emit('metrics',{width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth+2,title:document.title,textLength:(document.body?.innerText||'').trim().length});
    addEventListener('DOMContentLoaded',()=>{emit('ready',{});setTimeout(check,250)});
    addEventListener('resize',check);
  })();<\/script>`;
  return html.replace(/<head\b[^>]*>/i, tag => tag + bridge);
}

export function safePreviewData(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const out = Object.create(null);
  let size = 0;
  for (const [key, val] of Object.entries(value).slice(0,40)) {
    if (typeof val !== 'string' || val.length > 30000 || key.length > 200) continue;
    size += key.length + val.length;
    if (size > 60000) break;
    out[key] = val;
  }
  return out;
}

export function restoreProject(storage, userId) {
  try {
    const data = JSON.parse(storage.getItem('ash-browser-project:' + userId) || 'null');
    if (!data || !Array.isArray(data.revisions)) return null;
    const revisions = data.revisions.slice(-MAX_REVISIONS).filter(r => r && typeof r.id === 'string' && typeof r.request === 'string' && typeof r.html === 'string' && r.html.length <= MAX_SOURCE);
    if (!revisions.length) return null;
    return { id: String(data.id || ''), revisions, activeId: revisions.some(r=>r.id===data.activeId)?data.activeId:revisions.at(-1).id, data: safePreviewData(data.data) };
  } catch { return null; }
}

export function saveProject(storage, userId, project) {
  // Report quota/private-browsing failures instead of silently claiming persistence.
  storage.setItem('ash-browser-project:' + userId, JSON.stringify(project));
}

export function addRevision(project, request, html) {
  const revision = { id: crypto.randomUUID(), request, html: normalizeArtifact(html), createdAt: new Date().toISOString() };
  return { id: project?.id || crypto.randomUUID(), revisions: [...(project?.revisions || []), revision].slice(-MAX_REVISIONS), activeId: revision.id, data: project?.data || {} };
}

export function activeRevision(project) {
  return project?.revisions.find(r=>r.id===project.activeId) || project?.revisions.at(-1) || null;
}

export async function generateArtifact({ request, previous = '', repair = '', fetcher, signal }) {
  const message = generationPrompt(request, previous, repair);
  const response = await fetcher({ action: 'generate', output_format: 'html', message, mode: 'high', history: [] }, signal);
  const data = await response.json();
  if (!response.ok) throw new Error(response.status===401 ? 'Your session expired. Sign in again.' : data.error || `Generation failed (${response.status}). Your previous revision is safe.`);
  return normalizeArtifact(data.answer);
}
