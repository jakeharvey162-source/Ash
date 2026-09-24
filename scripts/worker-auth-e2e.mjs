import { chromium } from "playwright";
import fs from "node:fs";

const url = process.env.ASH_LIVE_URL || "https://meet-ash.jakeharvey162.workers.dev/";
// Gateway v19 research route is verified below with a real grounded query.
const stamp = Date.now();
const email = "ash-e2e-worker-" + stamp + "@example.com";
const password = "AshE2E!" + stamp + "#x9";
const name = "Ash E2E User";

const report = { url, startedAt:new Date().toISOString(), email, checks:{}, errors:[] };
const browser = await chromium.launch({headless:true});
const page = await browser.newPage({viewportSize:{width:1366,height:850}});
page.on("console", msg => { if(msg.type()==="error") report.errors.push({type:"console",text:msg.text()}); });
page.on("pageerror", err => report.errors.push({type:"page",text:String(err)}));
page.on("requestfailed", req => report.errors.push({type:"request",url:req.url(),text:req.failure()?.errorText||"failed"}));
async function shot(name){ await page.screenshot({path:"worker-auth-"+name+".png",fullPage:true}); }
async function mustVisible(selector,label,timeout=12000){ await page.locator(selector).waitFor({state:"visible",timeout}).catch(()=>{throw new Error(label+" not visible");}); }
async function authMessage(){ return ((await page.locator("#authMsg").textContent().catch(()=>""))||"").trim(); }

try{
  const response = await page.goto(url,{waitUntil:"networkidle",timeout:45000});
  report.status = response?.status() || null;
  report.finalUrl = page.url();
  if(report.status!==200) throw new Error("Homepage returned HTTP "+report.status);
  await mustVisible("#authSubmit","Sign in button");
  await mustVisible("[data-auth-mode='signup']","Create account tab");
  report.checks.homepage=true;

  await page.locator("[data-auth-mode='signup']").click();
  await mustVisible("#name","Create account name field");
  await page.locator("#name").fill(name);
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.locator("#authSubmit").click();
  await page.waitForFunction(()=>{
    if(document.querySelector(".shell")) return true;
    const msg=(document.querySelector("#authMsg")?.textContent||"").trim();
    return Boolean(msg && !/creating your account/i.test(msg));
  },{timeout:20000}).catch(()=>{});
  const signupOk=await page.locator(".shell").isVisible().catch(()=>false);
  if(!signupOk) throw new Error("Create account did not enter Ash: "+(await authMessage()));
  report.checks.createAccount=true;

  const stored = await page.evaluate(()=>JSON.parse(localStorage.getItem("ash-session")||"null"));
  if(!stored?.access_token||!stored?.user?.id) throw new Error("Signup entered Ash without a valid persisted session.");
  report.userId=stored.user.id;
  report.checks.signupSession=true;
  await shot("after-signup");

  await page.locator("[data-view='settings']").first().click();
  await mustVisible("#signout","Sign out button");
  await page.locator("#signout").click();
  await mustVisible("#authSubmit","Sign in form after sign out");
  if(await page.locator("#name").count()) throw new Error("Sign out returned to Create account instead of Sign in.");
  report.checks.signOut=true;

  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password);
  await page.locator("#authSubmit").click();
  await mustVisible(".shell","Dashboard after sign in",15000);
  report.checks.signIn=true;
  await shot("after-signin");

  const pairContext=await page.evaluate(()=>({
    base:(window.JARVIS_CONFIG?.SUPABASE_URL||"").replace(/\/$/,""),
    key:window.JARVIS_CONFIG?.SUPABASE_PUBLISHABLE_KEY||"",
    session:JSON.parse(localStorage.getItem("ash-session")||"null")
  }));
  const deviceLink=pairContext.base+"/functions/v1/ash-device-link";
  const createPair=await page.request.post(deviceLink,{
    headers:{Authorization:"Bearer "+pairContext.session.access_token,apikey:pairContext.key},
    data:{action:"create_pairing"}
  });
  if(!createPair.ok())throw new Error("Could not create desktop pairing code: "+await createPair.text());
  const pair=await createPair.json();
  if(!pair.code)throw new Error("Pairing endpoint returned no code.");

  const claimPair=await page.request.post(deviceLink,{data:{
    action:"claim_pairing",code:pair.code,device_name:"Ash CI Desktop",platform:"test",
    app_version:"ash-e2e",capabilities:{builder:true,local_ai:true,voice_runtime:true}
  }});
  if(!claimPair.ok())throw new Error("Could not claim desktop pairing code: "+await claimPair.text());
  const device=await claimPair.json();
  if(!device.device_id||!device.device_secret)throw new Error("Pairing did not issue a device credential.");

  const deviceHeaders={"X-Ash-Device-ID":device.device_id,"X-Ash-Device-Secret":device.device_secret};
  const heartbeat=await page.request.post(deviceLink,{headers:deviceHeaders,data:{action:"heartbeat"}});
  if(!heartbeat.ok())throw new Error("Desktop heartbeat failed: "+await heartbeat.text());

  const job=await page.evaluate(async ({base,key,deviceId})=>{
    const s=JSON.parse(localStorage.getItem("ash-session")||"null");
    const r=await fetch(base+"/rest/v1/jarvis_remote_jobs",{
      method:"POST",
      headers:{apikey:key,Authorization:"Bearer "+s.access_token,"Content-Type":"application/json",Prefer:"return=representation"},
      body:JSON.stringify({user_id:s.user.id,target_device_id:deviceId,kind:"mission",mode:"instant",payload:{prompt:"pairing channel test"},status:"queued",requires_confirmation:false})
    });
    const d=await r.json();return {ok:r.ok,data:d};
  },{base:pairContext.base,key:pairContext.key,deviceId:device.device_id});
  if(!job.ok||!job.data?.[0]?.id)throw new Error("Could not queue desktop test job: "+JSON.stringify(job.data));
  const jobId=job.data[0].id;

  const jobsResp=await page.request.post(deviceLink,{headers:deviceHeaders,data:{action:"jobs"}});
  const queued=await jobsResp.json();
  if(!jobsResp.ok()||!queued.jobs?.some(j=>j.id===jobId))throw new Error("Paired desktop could not receive queued job.");

  const claimJob=await page.request.post(deviceLink,{headers:deviceHeaders,data:{action:"claim_job",job_id:jobId}});
  if(!claimJob.ok()||!(await claimJob.json()).job)throw new Error("Paired desktop could not claim job.");

  const finishJob=await page.request.post(deviceLink,{headers:deviceHeaders,data:{action:"finish_job",job_id:jobId,ok:true,result:{summary:"pairing channel verified"}}});
  if(!finishJob.ok())throw new Error("Paired desktop could not finish job.");

  const disconnect=await page.request.post(deviceLink,{
    headers:{Authorization:"Bearer "+pairContext.session.access_token,apikey:pairContext.key},
    data:{action:"disconnect_device",device_id:device.device_id}
  });
  if(!disconnect.ok())throw new Error("Could not disconnect paired test device.");
  report.checks.desktopPairing=true;
  report.checks.desktopJobChannel=true;
  const research=await page.evaluate(async ()=>{
    const cfg=window.JARVIS_CONFIG||{};
    const s=JSON.parse(localStorage.getItem("ash-session")||"null");
    const r=await fetch(cfg.ASH_GATEWAY_URL,{
      method:"POST",
      headers:{apikey:cfg.SUPABASE_PUBLISHABLE_KEY,Authorization:"Bearer "+s.access_token,"Content-Type":"application/json"},
      body:JSON.stringify({action:"research",message:"Research the latest official OpenAI product update and give me the source.",mode:"instant",history:[]})
    });
    let d={};try{d=await r.json()}catch{}
    return {ok:r.ok,status:r.status,data:d};
  });
  report.liveResearch={status:research.status,grounded:research.data?.grounded,sources:Array.isArray(research.data?.sources)?research.data.sources.length:0,researched_at:research.data?.researched_at||null,error:research.data?.error||null,research_status:research.data?.research_status||null};
  if(!research.ok||research.data?.grounded!==true||!Array.isArray(research.data?.sources)||research.data.sources.length<1)throw new Error("Live research did not return grounded current sources: "+JSON.stringify(report.liveResearch));
  report.checks.liveResearchGrounded=true;
  const yearCheck=await page.evaluate(async ()=>{
    const cfg=window.JARVIS_CONFIG||{};
    const s=JSON.parse(localStorage.getItem("ash-session")||"null");
    const r=await fetch(cfg.ASH_GATEWAY_URL,{
      method:"POST",
      headers:{apikey:cfg.SUPABASE_PUBLISHABLE_KEY,Authorization:"Bearer "+s.access_token,"Content-Type":"application/json"},
      body:JSON.stringify({action:"chat",message:"What year is it right now? Answer with the current year.",mode:"instant",history:[]})
    });
    let d={};try{d=await r.json()}catch{}
    return {ok:r.ok,status:r.status,answer:String(d.answer||"")};
  });
  report.currentYearCheck=yearCheck;
  if(!yearCheck.ok||!/\b2026\b/.test(yearCheck.answer)||/\b2023\b/.test(yearCheck.answer))throw new Error("Ash returned a stale current year: "+JSON.stringify(yearCheck));
  report.checks.currentYear2026=true;

  await page.locator("[data-view='settings']").first().click();
  await page.locator("#signout").click();
  await mustVisible("#authSubmit","Sign in form before wrong-password test");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password+"WRONG");
  await page.locator("#authSubmit").click();
  await page.waitForFunction(()=>{const msg=(document.querySelector("#authMsg")?.textContent||"").trim();return Boolean(msg&&!/signing you in/i.test(msg));},{timeout:20000});
  const wrong=await authMessage();
  report.wrongPasswordMessage=wrong;
  if(/confirm your email/i.test(wrong)) throw new Error("Wrong-password message incorrectly asks the user to confirm email.");
  if(!/password|incorrect|credentials/i.test(wrong)) throw new Error("Wrong-password message is not useful: "+wrong);
  report.checks.wrongPassword=true;

  if(!(await page.locator("#forgotPassword").isVisible())) throw new Error("Forgot password control is missing.");
  report.checks.forgotPasswordControl=true;
  await shot("final");
  report.ok=true;
}catch(e){
  report.ok=false;
  report.failure=String(e?.stack||e);
  await shot("failure").catch(()=>{});
}finally{
  report.finishedAt=new Date().toISOString();
  fs.writeFileSync("worker-auth-e2e.json",JSON.stringify(report,null,2));
  console.log("=== ASH WORKER AUTH E2E ===");
  console.log(JSON.stringify(report,null,2));
  await browser.close();
}
if(!report.ok) process.exit(1);
