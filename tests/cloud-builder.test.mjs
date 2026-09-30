import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeArtifact, generationPrompt, previewDocument, safePreviewData, restoreProject, saveProject, addRevision, activeRevision, generateArtifact} from '../src/cloud-builder.js';
const html='<!doctype html><html><head><title>Budget</title><style>body{margin:0}</style></head><body><h1>Budget</h1><script>document.body.dataset.ready="yes";</script></body></html>';
const storage=()=>{const map=new Map();return {getItem:k=>map.get(k),setItem:(k,v)=>map.set(k,v)}};
test('complete HTML and exact fences accepted; incomplete output is rejected',()=>{
  assert.equal(normalizeArtifact(html),html);
  assert.equal(normalizeArtifact('```html\n'+html+'\n```'),html);
  assert.throws(()=>normalizeArtifact(html.replace('</html>','')),/incomplete/);
  assert.throws(()=>normalizeArtifact(html.replace('<head>','')),/incomplete/);
});
test('external executable dependencies and credentials are rejected',()=>{
  assert.throws(()=>normalizeArtifact(html.replace('<script>','<script src="https://cdn.test/lib.js">')),/external code/);
  assert.throws(()=>normalizeArtifact(html.replace('<style>','<link rel="stylesheet" href="x.css"><style>')),/external code/);
  assert.throws(()=>normalizeArtifact(html.replace('Budget','gsk_'+ 'a'.repeat(30))),/Credential/);
});
test('edits retain full prior source and reject oversized context',()=>{
  const prompt=generationPrompt('Add a budget',html);
  assert.ok(prompt.includes(html));assert.match(prompt,/saved-data compatibility/);
  assert.throws(()=>generationPrompt(''),/Describe/);
  assert.throws(()=>generationPrompt('Edit','x'.repeat(14501)),/too large/);
  assert.ok(generationPrompt('x'.repeat(3000),'x'.repeat(14500)).length<20000);
});
test('preview installs CSP before generated scripts and escapes script breakout in stored data',()=>{
  const source=previewDocument(html,'channel',{'unsafe':'</script><script>alert(1)</script>'});
  assert.ok(source.indexOf('Content-Security-Policy')<source.indexOf('document.body.dataset'));
  assert.match(source,/connect-src 'none'/);
  assert.ok(!source.includes("'unsafe':'</script>"));
  assert.match(source,/\\u003c\/script>/);
});
test('preview data is bounded and ignores invalid/prototype-like objects',()=>{
  const input=JSON.parse('{"__proto__":"safe value","a":123,"b":"ok"}');
  const result=safePreviewData(input);
  assert.equal(Object.getPrototypeOf(result),null);assert.equal(result.b,'ok');assert.ok(!('a' in result));
  assert.equal(Object.keys(safePreviewData(Object.fromEntries(Array.from({length:80},(_,i)=>[i,'x'])))).length,40);
});
test('projects are scoped to user and retain six restorable revisions',()=>{
  let project=null;
  for(let i=0;i<8;i++)project=addRevision(project,'Change '+i,html);
  assert.equal(project.revisions.length,6);
  const store=storage();saveProject(store,'alice',project);
  assert.equal(restoreProject(store,'bob'),null);
  const restored=restoreProject(store,'alice');assert.equal(activeRevision(restored).request,'Change 7');
  restored.activeId=restored.revisions[0].id;saveProject(store,'alice',restored);
  assert.equal(activeRevision(restoreProject(store,'alice')).request,'Change 2');
});
test('corrupt stored state is handled; quota failure is surfaced',()=>{
  assert.equal(restoreProject({getItem:()=>'{broken'},'alice'),null);
  assert.throws(()=>saveProject({setItem(){throw Error('QuotaExceeded')}},'alice',{}),/Quota/);
});
test('generation uses live API output, not a silent scaffold',async()=>{
  let bodySeen;
  const result=await generateArtifact({request:'Build a budget app',fetcher:async body=>{bodySeen=body;return {ok:true,json:async()=>({answer:html})}}});
  assert.equal(result,html);assert.equal(bodySeen.action,'generate');
  await assert.rejects(generateArtifact({request:'Build app',fetcher:async()=>({ok:false,status:503,json:async()=>({error:'Unavailable'})})}),/Unavailable/);
  await assert.rejects(generateArtifact({request:'Build app',fetcher:async()=>({ok:true,json:async()=>({answer:'Sorry, cannot generate'})})}),/incomplete/);
});

const {BrowserStudio}=await import('../src/browser-studio.js');
function makeStudio(fetcher){
  globalThis.localStorage=storage();
  const studio=new BrowserStudio({fetcher,onChange:()=>{},notify:()=>{}});
  studio.syncUser('alice');return studio;
}
test('failed follow-up preserves the original artifact and draft',async()=>{
  const studio=makeStudio(async()=>({ok:false,status:503,json:async()=>({error:'Provider unavailable'})}));
  studio.project=addRevision(null,'Initial app',html);const original=studio.project;
  studio.draft='Add a budget';await studio.generate();
  assert.equal(studio.project,original);assert.equal(studio.draft,'Add a budget');assert.equal(studio.busy,false);assert.match(studio.error,/Provider unavailable/);
});
test('repair sends captured errors even when re-render resets preview diagnostics',async()=>{
  let body;
  const studio=makeStudio(async input=>{body=input;return {ok:true,json:async()=>({answer:html})}});
  studio.project=addRevision(null,'Initial app',html);studio.errors=['ReferenceError: missingTotal'];
  studio.onChange=()=>{studio.errors=[]};await studio.generate({repair:true});
  assert.match(body.message,/ReferenceError: missingTotal/);assert.equal(studio.project.revisions.length,2);
});
test('cancelled generation never replaces a working revision',async()=>{
  let resolve;
  const studio=makeStudio(()=>new Promise(r=>{resolve=r}));
  studio.project=addRevision(null,'Initial app',html);const original=studio.project;
  studio.draft='Change color';const pending=studio.generate();studio.controller.abort('cancelled');
  resolve({ok:true,json:async()=>({answer:html})});await pending;
  assert.equal(studio.project,original);assert.equal(studio.busy,false);
});
test('account change ignores late results and clears the prior account project',async()=>{
  let resolve;
  const studio=makeStudio(()=>new Promise(r=>{resolve=r}));
  studio.draft='Build app';const pending=studio.generate();studio.syncUser('bob');
  resolve({ok:true,json:async()=>({answer:html})});await pending;
  assert.equal(studio.project,null);assert.equal(studio.userId,'bob');assert.equal(studio.busy,false);
});
test('preview iframe never grants generated code same-origin access',()=>{
  const studio=makeStudio(()=>{});studio.project=addRevision(null,'App',html);
  assert.match(studio.view(),/sandbox="allow-scripts allow-downloads"/);
  assert.ok(!studio.view().includes('allow-same-origin'));
});

const {completeHTMLArtifact}=await import('../supabase/functions/jarvis-ai-gateway/artifact-validation.js');
test('backend rejects truncated code and preserves complete code verbatim',()=>{
  assert.equal(completeHTMLArtifact(html),html);
  assert.equal(completeHTMLArtifact('<think>reasoning</think>\n```html\n'+html+'\n```'),html);
  assert.throws(()=>completeHTMLArtifact(html.slice(0,-20)),/incomplete_html_artifact/);
  assert.throws(()=>completeHTMLArtifact('Here is your website:\n'+html),/incomplete_html_artifact/);
});

const {restoreWorkspace,saveWorkspace,projectBackup,importProjectBackup}=await import('../src/cloud-builder.js');
test('workspace migrates a legacy project without losing data or revisions',()=>{
  const store=storage(),project=addRevision(null,'Old project',html);project.data={expenses:'[1,2]'};saveProject(store,'alice',project);
  const workspace=restoreWorkspace(store,'alice');assert.equal(workspace.activeId,project.id);assert.deepEqual({...workspace.projects[0].data},project.data);
  saveWorkspace(store,'alice',workspace.projects,workspace.activeId);assert.equal(restoreWorkspace(store,'alice').projects.length,1);
});
test('new builds preserve separate projects and isolated data',async()=>{
  const studio=makeStudio(async()=>({ok:true,json:async()=>({answer:html})}));
  studio.draft='Expense app';await studio.generate();const original=studio.project;original.data={entries:'saved'};studio.persist();
  studio.draft='Coffee site';await studio.generate({fresh:true});assert.equal(studio.projects.length,2);assert.notEqual(studio.project.id,original.id);
  assert.deepEqual(studio.project.data,{});assert.equal(studio.projects[0].data.entries,'saved');
  const workspace=restoreWorkspace(localStorage,'alice');assert.equal(workspace.projects.length,2);assert.equal(workspace.activeId,studio.project.id);
  assert.equal(restoreWorkspace(localStorage,'bob').projects.length,0);
});
test('backup round trip keeps revisions and data while import creates a distinct project',()=>{
  const original=addRevision(addRevision(null,'First',html),'Second',html);original.title='Budget';original.data={entries:'saved'};
  const imported=importProjectBackup(projectBackup(original));assert.notEqual(imported.id,original.id);assert.equal(imported.revisions.length,2);
  assert.equal(activeRevision(imported).request,'Second');assert.equal(imported.data.entries,'saved');
});
test('hostile or invalid backups are rejected before preview',()=>{
  assert.throws(()=>importProjectBackup('not json'),/valid/);
  assert.throws(()=>importProjectBackup(JSON.stringify({format:'ash-project',version:1,project:{revisions:[{html:'<script>alert(1)</script>'}]}})),/incomplete/);
  assert.throws(()=>importProjectBackup('x'.repeat(1000001)),/1 MB/);
});
test('workspace handles corrupt entries without breaking valid projects',()=>{
  const store=storage(),project=addRevision(null,'Valid',html);
  store.setItem('ash-browser-workspace:alice',JSON.stringify({version:1,projects:[{},project],activeId:null}));
  assert.equal(restoreWorkspace(store,'alice').projects.length,1);assert.equal(restoreWorkspace(store,'alice').activeId,null);
});

const {sourceArtifact}=await import('../supabase/functions/jarvis-ai-gateway/artifact-validation.js');
test('source route rejects assistant fallback prose and preserves complete code',()=>{
  assert.equal(sourceArtifact('```jsx\nexport default function App(){return <h1>Hi</h1>}\n```'),'export default function App(){return <h1>Hi</h1>}');
  assert.throws(()=>sourceArtifact('Sorry, I cannot build that.'),/invalid_source/);
  assert.throws(()=>sourceArtifact('Offline Python core is active'),/invalid_source/);
});
