/** Real Chromium user journey: authenticated client intake -> actual job POST -> visible queue.
 * All remote services are mocked; this is not a claim of a live customer delivery.
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { chromium } from "playwright";

const host="http://127.0.0.1:4173";
const server=spawn(process.execPath,["node_modules/vite/bin/vite.js","preview","--host","127.0.0.1","--port","4173","--strictPort"],{stdio:"ignore"});
let browser;
try {
  let ready=false;
  for(let i=0;i<80;i++){
    try{const r=await fetch(host);if(r.ok){ready=true;break}}catch{}
    await new Promise(resolve=>setTimeout(resolve,150));
  }
  assert.ok(ready,"Ash preview server did not start.");
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage({viewport:{width:390,height:844},serviceWorkers:"block"});
  const tokenPart=Buffer.from(JSON.stringify({sub:"11111111-1111-4111-8111-111111111111",exp:Math.floor(Date.now()/1000)+3600})).toString("base64url");
  const jwt="head."+tokenPart+".mock";
  await page.addInitScript(t=>{
    localStorage.setItem("ash-session",JSON.stringify({
      access_token:t,refresh_token:"fixture-refresh",
      user:{id:"11111111-1111-4111-8111-111111111111",email:"owner@example.com"},
    }));
    localStorage.setItem("ash-voice-enabled","false");
  },jwt);
  const saved=[];
  await page.route("**/rest/v1/**",async route=>{
    const request=route.request();
    const url=new URL(request.url());
    if(request.method()==="POST" && url.pathname.endsWith("jarvis_remote_jobs")){
      const data=request.postDataJSON();
      saved.push(data);
      return route.fulfill({status:201,contentType:"application/json",body:JSON.stringify([{id:"job-new",created_at:new Date().toISOString(),...data}])});
    }
    const data=url.pathname.endsWith("jarvis_remote_jobs")?
      saved.map((job,i)=>({id:"job-"+i,created_at:new Date().toISOString(),...job})):[];
    return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(data)});
  });
  await page.route("**/auth/v1/**",route=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({id:"11111111-1111-4111-8111-111111111111"})}));
  await page.route("**/functions/v1/**",route=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({ok:false})}));
  await page.goto(host,{waitUntil:"domcontentloaded"});
  await page.locator('[data-view="business"]').first().click();
  await page.locator("#businessClient").fill("<img src=x onerror=alert(1)>");
  await page.locator("#businessEmail").fill("client@example.com");
  await page.locator("#businessProject").fill("Coffee Shop Website");
  await page.locator("#businessRequest").fill("Build a beautiful responsive website with menu, booking form, and clear enquiry details.");
  await page.locator("#businessCreate").click();
  await page.waitForFunction(()=>document.querySelector(".autoList")?.textContent?.includes("Coffee Shop Website"));
  assert.equal(saved.length,1,"Submitting the form should create exactly one backend job.");
  assert.equal(saved[0].kind,"builder");
  assert.equal(saved[0].requires_confirmation,false);
  assert.equal(saved[0].payload.external_delivery_authorized,false);
  assert.equal(saved[0].payload.business_client.email,"client@example.com");
  assert.ok(!await page.locator(".autoList img").count(),"Client text must be escaped on the page.");
  assert.match(await page.locator(".autoList").innerText(),/review|waiting|queued/i);
  console.log("ASH BUSINESS DESK CHROMIUM: PASS mobile client intake, authenticated queue, output rendering, and owner guard.");
} finally {
  await browser?.close().catch(()=>{});
  server.kill("SIGTERM");
}
