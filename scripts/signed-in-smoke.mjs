import { chromium } from "playwright";

const url = process.env.ASH_LOCAL_URL || "http://127.0.0.1:4173/";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

let refresh_token_hits = 0;
const json = (route, body, status=200) => route.fulfill({
  status,
  contentType: "application/json",
  body: JSON.stringify(body)
});

await page.addInitScript(() => {
  localStorage.setItem("ash-session", JSON.stringify({
    access_token: "test-access-token",
    refresh_token: "test-refresh-token",
    user: { id: "00000000-0000-0000-0000-000000000001", email: "ash-test@example.invalid" }
  }));
  localStorage.setItem("ash-mode", "high");
  localStorage.setItem("ash-theme", "dark");
});

await page.route("**/auth/v1/token?grant_type=refresh_token", route => { refresh_token_hits++; return json(route, { access_token: "refreshed-token", refresh_token: "test-refresh-token", user: { id: "00000000-0000-0000-0000-000000000001", email: "ash-test@example.invalid" } }); });

await page.route("**/rest/v1/jarvis_profiles**", route => json(route, [{
  user_id: "00000000-0000-0000-0000-000000000001",
  assistant_name: "Ash",
  personality_preset: "builder",
  preferred_mode: "high",
  wake_word: "Ash",
  custom_instructions: "",
  behavior_config: { verbosity: "balanced", proactivity: "balanced", humor: 20, learn_style: true },
  voice_config: { auto_speak: false, voice_id: "test" }
}]));

await page.route("**/rest/v1/jarvis_automations**", route => json(route, []));
await page.route("**/rest/v1/jarvis_integrations**", route => json(route, []));
let gateway_hits = 0;
await page.route("**/functions/v1/jarvis-ai-gateway**", route => {
  const reqUrl = new URL(route.request().url());
  if (reqUrl.searchParams.get("action") === "health") {
    return json(route, { ok: true, service: "jarvis-ai-gateway", cloud_ready: true, voice_ready: true });
  }
  gateway_hits++;
  const auth = route.request().headers()["authorization"] || "";
  if (gateway_hits === 1 && !auth.includes("refreshed-token")) return json(route, { error: "unauthorized" }, 401);
  return json(route, { answer: "Chat render test passed.", mode: "high", assistant_name: "Ash" });
});

await page.route("**/rest/v1/jarvis_devices**", route => json(route, [{
  id: "10000000-0000-0000-0000-000000000001",
  user_id: "00000000-0000-0000-0000-000000000001",
  device_name: "Ash Test Desktop",
  nickname: "Ash Test Desktop",
  platform: "windows",
  last_seen_at: new Date().toISOString(),
  capabilities: { builder: true, verified_builds: true, local_ai: true, offline_brain: true }
}]));

let queued = false;
await page.route("**/rest/v1/jarvis_remote_jobs**", async route => {
  if (route.request().method() === "POST") {
    const body = JSON.parse(route.request().postData() || "{}");
    if (body.kind !== "builder" || body.payload?.builder !== true || !body.payload?.prompt) {
      return json(route, { error: "bad_builder_payload" }, 400);
    }
    queued = true;
    return json(route, [{ id: "20000000-0000-0000-0000-000000000001", ...body }], 201);
  }
  return json(route, []);
});


async function assertNoHorizontalOverflow(label){
  const dims=await page.evaluate(()=>({
    doc:document.documentElement.scrollWidth,
    body:document.body.scrollWidth,
    viewport:window.innerWidth
  }));
  if(Math.max(dims.doc,dims.body)>dims.viewport+2)throw new Error(label+" has horizontal overflow: "+JSON.stringify(dims));
}
async function assertSignedInViewport(width,height,label){
  await page.setViewportSize({width,height});
  await page.reload({waitUntil:"networkidle"});
  await assertNoHorizontalOverflow(label);
  if(width<=900 || (width<=1024&&height<=600)){
    if(!(await page.locator(".mobileNav").isVisible()))throw new Error(label+" mobile navigation missing.");
  }else{
    if(!(await page.locator(".rail").isVisible()))throw new Error(label+" desktop rail missing.");
  }
  if(!(await page.locator("#prompt").isVisible()))throw new Error(label+" chat composer missing.");
}

const errors = [];
page.on("pageerror", err => errors.push(String(err)));
page.on("console", msg => { if (msg.type() === "error" && !msg.text().includes("401 (Unauthorized)")) errors.push(msg.text()); });

await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });

if (!(await page.locator(".shell").isVisible())) throw new Error("Signed-in shell did not render.");
if (!(await page.getByText("Overview", { exact: true }).isVisible())) throw new Error("Desktop navigation missing.");
if (!(await page.getByText("Builder", { exact: true }).first().isVisible())) throw new Error("Builder navigation missing.");

await page.getByRole("button", { name: /Activity$/ }).click();
await page.locator("#runHealth").click();
await page.getByText("online", { exact: true }).first().waitFor({ state: "visible", timeout: 3000 });
if (!(await page.getByText("Local AI", { exact: true }).isVisible())) throw new Error("Health panel missing local AI status.");
await page.getByRole("button", { name: /Overview$/ }).click();

await page.locator("#ashCoreCanvas").evaluate(el => el.dataset.persistToken = "keep");
await page.locator("#prompt").fill("Test chat rendering");
await page.locator("#send").click();
await page.getByText("Chat render test passed.", { exact: true }).waitFor({ state: "visible", timeout: 5000 });
const persisted = await page.locator("#ashCoreCanvas").evaluate(el => el.dataset.persistToken || "");
if (persisted !== "keep") throw new Error("Chat send rebuilt the Ash Core instead of updating in place.");
if (refresh_token_hits < 1) throw new Error("Expired gateway session did not auto-refresh.");

await page.getByText("Builder", { exact: true }).first().click();
await page.waitForTimeout(150);

if (!(await page.locator("#buildPrompt").isVisible())) throw new Error("Builder prompt is not visible.");
if (!(await page.locator("#createBuild").isVisible())) throw new Error("Builder action is not visible.");
if (!(await page.getByText("Desktop builder online.", { exact: false }).isVisible())) throw new Error("Builder did not detect linked desktop.");

await page.locator("#buildPrompt").fill("Build a responsive portfolio website with a contact form and dark mode.");
await page.locator("#createBuild").click();
await page.waitForTimeout(150);

if (!queued) throw new Error("Builder request was not queued.");
if (errors.length) throw new Error("Browser errors: " + errors.join(" | "));

for (const [w,h,label] of [
  [360,800,"Android narrow portrait"],
  [390,844,"Android portrait"],
  [844,390,"Android landscape"],
  [768,1024,"Tablet portrait"],
  [1366,768,"Laptop"],
  [1920,1080,"Desktop"]
]){
  await assertSignedInViewport(w,h,label);
}
const mobileButtons = await page.locator(".mobileNav button").count();
await page.setViewportSize({width:390,height:844});
await page.reload({waitUntil:"networkidle"});
if (mobileButtons !== 5) throw new Error("Expected 5 mobile navigation actions, got " + mobileButtons);
await page.screenshot({ path: "signed-in-smoke.png", fullPage: true });
console.log("ASH SIGNED-IN UI SMOKE: PASS");
await browser.close();
