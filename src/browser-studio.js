import { activeRevision, addRevision, generateArtifact, previewDocument, restoreProject, safePreviewData, saveProject } from './cloud-builder.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export class BrowserStudio {
  constructor({ fetcher, onChange, notify }) {
    this.fetcher=fetcher;this.onChange=onChange;this.notify=notify;
    this.userId=null;this.project=null;this.draft='';this.status='';this.error='';this.busy=false;
    this.viewport='desktop';this.showSource=false;this.errors=[];this.metrics=null;this.controller=null;this.detach=null;
  }
  syncUser(userId) {
    if (this.userId===userId) return;
    this.controller?.abort();this.detach?.();
    this.userId=userId;this.project=userId?restoreProject(localStorage,userId):null;
    this.draft='';this.busy=false;this.status='';this.error='';this.metrics=null;this.errors=[];
  }
  view() {
    const revision=activeRevision(this.project);
    return `<section class="card browserStudio" aria-label="Browser builder">
      <div class="studioHeading"><div><p class="kicker">BUILD NOW · NO DESKTOP REQUIRED</p><h2>Idea to working preview.</h2><p class="quiet">Create standalone websites and small apps, then refine and download them. Projects and demo data stay in this browser. Backend services need a desktop project.</p></div><span class="badge">Browser build</span></div>
      <label for="studioBrief">${revision?'Describe your next change, or start a new project':'What would you like to build?'}<textarea id="studioBrief" rows="3" maxlength="3000" placeholder="Build a student expense tracker with totals in rand, category filters, saved expenses and CSV export.">${esc(this.draft)}</textarea></label>
      <div class="studioActions"><button id="studioGenerate" class="primary" ${this.busy?'disabled':''}>${this.busy?'Working…':revision?'Apply change':'Build in browser'}</button>${revision?`<button id="studioNew" ${this.busy?'disabled':''}>Build as new project</button><button id="studioDownload">Download HTML</button>`:''}${this.busy?'<button id="studioCancel">Stop generation</button>':''}</div>
      <p id="studioStatus" class="quiet" role="status" aria-live="polite">${esc(this.status||'No desktop, install or paid asset is required. Generation uses your configured Ash AI service.')}</p>
      ${this.error?`<p class="studioError" role="alert">${esc(this.error)}</p>`:''}
      ${revision?`<div class="studioToolbar"><div class="studioActions"><button id="studioDesktop" aria-pressed="${this.viewport==='desktop'}">Desktop preview</button><button id="studioMobile" aria-pressed="${this.viewport==='mobile'}">360px preview</button><button id="studioSource" aria-expanded="${this.showSource}">${this.showSource?'Hide source':'View source'}</button><button id="studioReload">Reload preview</button></div><label>Revision<select id="studioRevision" ${this.busy?'disabled':''}>${this.project.revisions.map((r,i)=>`<option value="${esc(r.id)}" ${r.id===this.project.activeId?'selected':''}>${i+1} · ${esc(r.request.slice(0,60))}</option>`).join('')}</select></label></div>
      <div class="studioPreview ${this.viewport==='mobile'?'mobile':''}"><iframe id="studioFrame" title="Generated project preview" sandbox="allow-scripts allow-downloads" referrerpolicy="no-referrer"></iframe></div>
      <p id="studioEvidence" class="quiet" role="status">Preview starting. Requested functionality still needs interaction testing.</p>
      <button id="studioRepair" hidden>Repair observed preview errors</button>
      ${this.showSource?`<label>index.html<textarea class="studioSource" readonly rows="14" spellcheck="false">${esc(revision.html)}</textarea></label>`:''}
      <p class="quiet">Preview blocks external requests and isolates generated code from your Ash account. Downloads contain the original source. Only preview errors and layout checks are reported; Ash does not claim a full app test passed.</p>`:''}
    </section>`;
  }
  persist() {
    if (!this.project||!this.userId) return;
    try { saveProject(localStorage,this.userId,this.project); }
    catch { this.error='Browser storage is unavailable or full. Keep this tab open and download your project; it is not saved across reloads.'; }
  }
  async generate({ fresh=false, repair=false }={}) {
    if (this.busy) return;
    const previous=activeRevision(this.project);
    const request=repair ? 'Fix the observed preview errors while preserving all existing functionality.' : this.draft.trim();
    if (!request) {this.error='Describe the website, app or change you want.';this.onChange();return;}
    const observedErrors=this.errors.join("\n");
    const owner=this.userId;
    const controller=new AbortController();this.controller=controller;
    const timeout=setTimeout(()=>controller.abort('timeout'),180000);
    this.busy=true;this.error='';this.status=repair?'Repairing observed preview errors…':previous&&!fresh?'Updating your project; the current revision stays safe…':'Generating your website or app…';this.onChange();
    try {
      const html=await generateArtifact({request,previous:fresh?'':previous?.html||'',repair:repair?observedErrors:'',fetcher:this.fetcher,signal:controller.signal});
      if (controller.signal.aborted||owner!==this.userId) return;
      this.project=addRevision(fresh?null:this.project,request,html);
      this.persist();this.draft='';this.errors=[];this.metrics=null;
      this.status=`Revision ready${this.error?' in this tab':' and saved in this browser'}. Test the interactions in the preview.`;
    } catch(e) {
      if (owner!==this.userId) return;
      this.error=controller.signal.aborted ? controller.signal.reason==='timeout'?'Generation timed out. Your previous revision is safe. Try a smaller request.':'Generation stopped. Your previous revision is safe.' : e.message||'Generation failed. Your previous revision is safe.';
      this.status='';
    } finally {
      clearTimeout(timeout);
      if (owner===this.userId) {this.busy=false;this.controller=null;this.onChange();}
    }
  }
  mount() {
    this.detach?.();this.detach=null;
    const byId=id=>document.getElementById(id);
    byId('studioBrief')?.addEventListener('input',e=>{this.draft=e.target.value});
    byId('studioGenerate')?.addEventListener('click',()=>this.generate());
    byId('studioNew')?.addEventListener('click',()=>this.generate({fresh:true}));
    byId('studioCancel')?.addEventListener('click',()=>this.controller?.abort('cancelled'));
    byId('studioDownload')?.addEventListener('click',()=>this.download());
    for (const [id,viewport] of [['studioDesktop','desktop'],['studioMobile','mobile']]) byId(id)?.addEventListener('click',()=>{this.viewport=viewport;this.onChange()});
    byId('studioSource')?.addEventListener('click',()=>{this.showSource=!this.showSource;this.onChange()});
    byId('studioReload')?.addEventListener('click',()=>this.onChange());
    byId('studioRepair')?.addEventListener('click',()=>this.generate({repair:true}));
    byId('studioRevision')?.addEventListener('change',e=>{this.project.activeId=e.target.value;this.persist();this.onChange()});
    const revision=activeRevision(this.project),frame=byId('studioFrame');
    if (!revision||!frame) return;
    const channel=crypto.randomUUID();this.errors=[];this.metrics=null;
    const update=()=>{
      const evidence=byId('studioEvidence');
      if (evidence) evidence.textContent=`${this.metrics?`Preview rendered at ${this.metrics.width}px · ${this.metrics.overflow?'horizontal overflow detected':'no horizontal overflow detected'}`:'Preview starting'} · ${this.errors.length} observed error(s). Requested interactions are not automatically verified.`;
      const repair=byId('studioRepair');if(repair){repair.hidden=!this.errors.length;repair.disabled=this.busy;}
    };
    const listener=event=>{
      if (event.source!==frame.contentWindow||event.data?.ashPreview!==channel) return;
      const {type,payload}=event.data;
      if (type==='error'&&this.errors.length<20) this.errors.push(String(payload).slice(0,500));
      if (type==='metrics'&&payload&&Number.isFinite(payload.width)) {
        this.metrics={width:Math.round(payload.width),overflow:payload.overflow===true};
        if(this.metrics.overflow&&!this.errors.includes('Horizontal overflow in preview.'))this.errors.push('Horizontal overflow in preview.');
      }
      if(type==='download'&&payload&&typeof payload.content==='string'&&payload.content.length<=1000000&&/\.(csv|txt|json)$/i.test(String(payload.name))){
        const name=String(payload.name).replace(/[^a-zA-Z0-9._-]/g,'_').slice(-100);
        const url=URL.createObjectURL(new Blob([payload.content],{type:'text/plain;charset=utf-8'}));
        const link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();
        setTimeout(()=>URL.revokeObjectURL(url),1000);
      }
      if (type==='storage') {this.project.data=safePreviewData(payload);this.persist();}
      update();
    };
    window.addEventListener('message',listener);
    this.detach=()=>window.removeEventListener('message',listener);
    frame.srcdoc=previewDocument(revision.html,channel,this.project.data);update();
  }
  download() {
    const revision=activeRevision(this.project);if(!revision) return;
    const url=URL.createObjectURL(new Blob([revision.html],{type:'text/html;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='ash-project.html';document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);this.notify('Downloaded standalone HTML. Open it in a browser to run it.');
  }
}
