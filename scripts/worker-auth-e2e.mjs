import { chromium } from "playwright";
import fs from "node:fs";

const url = process.env.ASH_LIVE_URL || "https://meet-ash.jakeharvey162.workers.dev/";
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

  await page.locator("[data-view='settings']").first().click();
  await page.locator("#signout").click();
  await mustVisible("#authSubmit","Sign in form before wrong-password test");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(password+"WRONG");
  await page.locator("#authSubmit").click();
  await page.waitForFunction(()=>{const msg=(document.querySelector("#authMsg")?.textContent||"").trim();return Boolean(msg&&!/signing you in/i.test(msg));},{timeout:10000});
  const wrong=await authMessage();
  report.wrongPasswordMessage=wrong;
  if(/confirm your email/i.test(wrong)) throw new Error("Wrong-password message incorrectly asks the user to confirm email.");
  if(!/password|incorrect|credentials/i.test(wrong)) throw new Error("Wrong-password message is not useful: "+wrong);
  report.checks.wrongPassword=true;

  await page.locator("#password").fill("");
  await page.locator("#forgotPassword").click();
  await page.waitForFunction(()=>/reset|inbox/i.test(document.querySelector("#authMsg")?.textContent||""),{timeout:10000});
  const resetMsg=await authMessage();
  report.resetMessage=resetMsg;
  if(!/reset|inbox/i.test(resetMsg)) throw new Error("Forgot password did not report success: "+resetMsg);
  report.checks.forgotPassword=true;
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
