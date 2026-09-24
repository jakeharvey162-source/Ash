import { chromium } from "playwright";
import fs from "node:fs";

const url = process.env.ASH_LIVE_URL || "https://ash-f4.vercel.app/";
const report = {
  url,
  fetchedAt: new Date().toISOString(),
  http: {},
  desktop: {},
  mobile: {},
  consoleErrors: [],
  pageErrors: [],
  failedRequests: [],
  badResponses: []
};

async function inspect(viewport, name) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewportSize: viewport });
  page.on("console", msg => {
    if (msg.type() === "error") report.consoleErrors.push({ view: name, text: msg.text() });
  });
  page.on("pageerror", err => report.pageErrors.push({ view: name, text: String(err) }));
  page.on("requestfailed", req => report.failedRequests.push({
    view: name,
    url: req.url(),
    failure: req.failure()?.errorText || "unknown"
  }));
  page.on("response", res => {
    if (res.status() >= 400) report.badResponses.push({
      view: name,
      status: res.status(),
      url: res.url()
    });
  });

  const start = Date.now();
  let response;
  try {
    response = await page.goto(url, { waitUntil: "networkidle", timeout: 45000 });
  } catch (e) {
    report[name].navigationError = String(e);
  }
  report[name].loadMs = Date.now() - start;
  report[name].status = response?.status() || null;
  report[name].finalUrl = page.url();
  report[name].title = await page.title().catch(() => "");
  report[name].bodyText = (await page.locator("body").innerText().catch(() => "")).slice(0, 2500);
  report[name].appHtmlLength = await page.locator("#app").innerHTML().then(x=>x.length).catch(() => 0);
  await page.locator("#ashHeroRobot").waitFor({state:"visible",timeout:10000}).catch(()=>{});
  await page.waitForFunction(()=>document.querySelector("#ashHeroRobot")?.complete===true,{timeout:10000}).catch(()=>{});
  report[name].visible = {
    email: await page.locator("#email").isVisible().catch(()=>false),
    password: await page.locator("#password").isVisible().catch(()=>false),
    signIn: await page.locator("#authSubmit").isVisible().catch(()=>false),
    createAccount: await page.locator("[data-auth-mode='signup']").isVisible().catch(()=>false),
    google: await page.locator("#googleSignin").isVisible().catch(()=>false),
    exactRobot: await page.locator("#ashHeroRobot").isVisible().catch(()=>false),
    themeToggle: await page.locator("#themeToggle").isVisible().catch(()=>false)
  };
  report[name].heroRobot = await page.locator("#ashHeroRobot").evaluate(img=>({
    src: img.getAttribute("src"),
    asset: img.dataset.asset || null,
    complete: img.complete,
    naturalWidth: img.naturalWidth,
    naturalHeight: img.naturalHeight,
    clientWidth: img.clientWidth,
    clientHeight: img.clientHeight
  })).catch(()=>null);
  report[name].config = await page.evaluate(() => {
    const c = window.JARVIS_CONFIG || null;
    return c ? {
      hasSupabaseUrl: Boolean(c.SUPABASE_URL),
      hasPublishableKey: Boolean(c.SUPABASE_PUBLISHABLE_KEY),
      hasGateway: Boolean(c.ASH_GATEWAY_URL),
      gateway: c.ASH_GATEWAY_URL || null
    } : null;
  }).catch(()=>null);
  report[name].styles = await page.evaluate(() => {
    const b = getComputedStyle(document.body);
    return { background: b.background, color: b.color, fontFamily: b.fontFamily };
  }).catch(()=>null);

  if(name==="desktop"){
    try{
      report[name].googleRemoved=(await page.locator("#googleSignin").count())===0;
      await page.locator("#themeToggle").click();
      await page.waitForTimeout(350);
      report[name].themeAfterToggle=await page.evaluate(()=>document.documentElement.dataset.theme||null);
    }catch(e){
      report[name].interactionAudit={error:String(e)};
    }
  }
  await page.screenshot({ path: `audit-${name}.png`, fullPage: true });
  await browser.close();
}

try {
  const r = await fetch(url, { redirect: "follow" });
  report.http = {
    status: r.status,
    finalUrl: r.url,
    contentType: r.headers.get("content-type"),
    cacheControl: r.headers.get("cache-control"),
    textPreview: (await r.text()).slice(0, 1200)
  };
} catch (e) {
  report.http.error = String(e);
}

await inspect({ width: 1440, height: 1000 }, "desktop");
await inspect({ width: 390, height: 844 }, "mobile");

fs.writeFileSync("live-audit.json", JSON.stringify(report, null, 2));
console.log("=== ASH LIVE AUDIT ===");
console.log(JSON.stringify(report, null, 2));
