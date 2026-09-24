import { chromium } from "playwright";

const url = process.env.ASH_LOCAL_URL || "http://127.0.0.1:4173/";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
const page = await context.newPage();

const json = (route, body, status=200) => route.fulfill({
  status,
  contentType: "application/json",
  body: JSON.stringify(body)
});

await page.route("**/auth/v1/token?grant_type=password", async route => {
  const body = JSON.parse(route.request().postData() || "{}");
  if (body.email === "wrong@example.invalid") {
    return json(route, { error: "invalid_grant", error_description: "Invalid login credentials" }, 400);
  }
  return json(route, {
    access_token: "login-token",
    refresh_token: "login-refresh",
    user: { id: "00000000-0000-0000-0000-000000000001", email: "test@example.invalid" }
  });
});
await page.route("**/auth/v1/signup", route => json(route, {
  access_token: "signup-token",
  refresh_token: "signup-refresh",
  user: {
    id: "00000000-0000-0000-0000-000000000002",
    email: "new@example.invalid",
    identities: [{ id:"identity-new" }]
  }
}));
await page.route("**/auth/v1/recover", route => json(route, {}));
await page.route("**/rest/v1/jarvis_profiles**", route => json(route, []));
await page.route("**/rest/v1/jarvis_automations**", route => json(route, []));
await page.route("**/rest/v1/jarvis_remote_jobs**", route => json(route, []));
await page.route("**/rest/v1/jarvis_devices**", route => json(route, []));
await page.route("**/rest/v1/jarvis_integrations**", route => json(route, []));



async function assertPublicPageScroll(){
  await page.setViewportSize({width:1366,height:768});
  await page.reload({waitUntil:"networkidle"});
  const metrics=await page.evaluate(()=>({
    scrollHeight:document.scrollingElement?.scrollHeight||document.documentElement.scrollHeight,
    clientHeight:document.scrollingElement?.clientHeight||document.documentElement.clientHeight
  }));
  if(metrics.scrollHeight<=metrics.clientHeight+20)throw new Error("Ash public page is not scrollable: "+JSON.stringify(metrics));
  await page.evaluate(()=>window.scrollTo(0,Math.min(700,(document.scrollingElement?.scrollHeight||document.documentElement.scrollHeight)-window.innerHeight)));
  await page.waitForTimeout(80);
  const y=await page.evaluate(()=>window.scrollY);
  if(y<20)throw new Error("Ash public page could not scroll.");
}

async function assertPublicViewport(width,height,label){
  await page.setViewportSize({width,height});
  await page.reload({waitUntil:"networkidle"});
  const dims=await page.evaluate(()=>({doc:document.documentElement.scrollWidth,body:document.body.scrollWidth,viewport:window.innerWidth}));
  if(Math.max(dims.doc,dims.body)>dims.viewport+2)throw new Error(label+" public page overflows horizontally: "+JSON.stringify(dims));
  if(!(await page.locator("#authSubmit").isVisible()))throw new Error(label+" auth form missing.");
  if(width<=650 && !(await page.locator(".authNav").isVisible()))throw new Error(label+" mobile public navigation missing.");
  if(!(await page.locator("#ashHeroRobot").isVisible()))throw new Error(label+" robot image missing.");
}

const errors=[];
page.on("pageerror", e=>errors.push(String(e)));

await page.goto(url,{waitUntil:"networkidle",timeout:30000});
if (!(await page.locator("#authSubmit").isVisible())) throw new Error("Sign in button missing.");
if (!(await page.locator("#ashHeroRobot").isVisible())) throw new Error("Exact Ash homepage robot image missing.");
await page.waitForFunction(()=>document.querySelector("#ashHeroRobot")?.complete===true,{timeout:10000});
const robot=await page.locator("#ashHeroRobot").evaluate(img=>({src:img.getAttribute("src"),w:img.naturalWidth,h:img.naturalHeight,asset:img.dataset.asset}));
if(robot.src!=="/images/ash-home-robot.webp"||robot.w!==148||robot.h!==148||robot.asset!=="user-upload-exact") throw new Error("Homepage is not rendering the exact uploaded Ash robot asset: "+JSON.stringify(robot));
if (!(await page.getByRole("button",{name:"Create account"}).isVisible())) throw new Error("Create account tab missing.");

for (const label of ["Product","Capabilities","Safety","Company"]) {
  const nav = page.locator(".authNav").getByRole("button",{name:label,exact:true});
  if (!(await nav.isVisible())) throw new Error(label+" navigation button missing.");
  await nav.click();
  await page.waitForTimeout(80);
  const id = label.toLowerCase();
  const target = page.locator("#"+id);
  if (!(await target.isVisible())) throw new Error(label+" section did not open/navigate.");
}
await page.getByRole("button",{name:"Create account"}).click();
if (!(await page.locator("#name").isVisible())) throw new Error("Create-account mode did not open.");
if ((await page.locator("#authSubmit").textContent())?.includes("Create account") !== true) throw new Error("Create-account submit label incorrect.");

await page.locator("#name").fill("Test User");
await page.locator("#email").fill("new@example.invalid");
await page.locator("#password").fill("Password123!");
await page.locator("#authSubmit").click();
await page.locator(".shell").waitFor({state:"visible",timeout:5000});
if (!(await page.getByText("Overview",{exact:true}).isVisible())) throw new Error("New signup did not enter Ash immediately.");
await page.getByRole("button",{name:"Preferences",exact:true}).click();
await page.locator("#signout").click();
await page.getByRole("button",{name:"Sign in",exact:true}).waitFor({state:"visible",timeout:3000});
if (await page.locator("#name").count()) throw new Error("Sign-in mode still shows name field.");

await page.locator("#email").fill("wrong@example.invalid");
await page.locator("#password").fill("WrongPassword!");
await page.locator("#authSubmit").click();
await page.getByText("Email or password is incorrect.", { exact:false }).waitFor({state:"visible",timeout:3000});

await page.locator("#email").fill("test@example.invalid");
await page.getByRole("button",{name:"Forgot password?"}).click();
await page.getByText("Password reset email sent.",{exact:true}).waitFor({state:"visible",timeout:3000});

await page.locator("#password").fill("Password123!");
await page.locator("#authSubmit").click();
await page.locator(".shell").waitFor({state:"visible",timeout:5000});
if (!(await page.getByText("Overview",{exact:true}).isVisible())) throw new Error("Successful sign-in did not open Ash.");

for (const [w,h,label] of [
  [360,800,"Android narrow portrait"],
  [390,844,"Android portrait"],
  [844,390,"Android landscape"],
  [768,1024,"Tablet portrait"],
  [1366,768,"Laptop"],
  [1920,1080,"Desktop"]
]) await assertPublicViewport(w,h,label);

await assertPublicPageScroll();

if(errors.length) throw new Error("Browser errors: "+errors.join(" | "));
console.log("ASH AUTH UI SMOKE: PASS");
await browser.close();
