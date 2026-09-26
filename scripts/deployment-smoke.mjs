import { chromium } from "playwright";

const url = process.env.ASH_DEPLOY_URL;
if (!url) throw new Error("ASH_DEPLOY_URL is required");

const forbiddenProviderNames = [
  "openrouter",
  "groq",
  "anthropic",
  "elevenlabs",
  "bytez",
  "nvidia",
  "gemini"
];

const response = await fetch(url, { redirect: "follow" });
if (!response.ok) throw new Error(`Deployment returned HTTP ${response.status}`);
const html = await response.text();

const scriptSrcs = [...html.matchAll(/<script[^>]+src=["']([^"']+)["']/gi)].map(m => m[1]);
let bundleText = "";
for (const src of scriptSrcs) {
  const assetUrl = new URL(src, response.url).toString();
  const asset = await fetch(assetUrl);
  if (asset.ok) bundleText += "\n" + await asset.text();
}

const exposed = forbiddenProviderNames.filter(name => new RegExp("\\b" + name + "\\b", "i").test(bundleText));
if (exposed.length) throw new Error("Public frontend bundle exposes backend provider names: " + exposed.join(", "));

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewportSize: { width: 1366, height: 850 } });
const consoleErrors = [];
const failedRequests = [];
page.on("console", msg => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
page.on("requestfailed", req => failedRequests.push(req.url()));

try {
  const nav = await page.goto(url, { waitUntil: "networkidle", timeout: 45000 });
  if (!nav || nav.status() !== 200) throw new Error("Browser navigation did not return HTTP 200");

  for (const [selector, label] of [
    ["#email", "email field"],
    ["#password", "password field"],
    ["#authSubmit", "sign in button"],
    ["[data-auth-mode='signup']", "create account control"],
    ["#themeToggle", "theme toggle"],
    ["#ashHeroRobot", "hero visual"]
  ]) {
    if (!(await page.locator(selector).isVisible().catch(() => false))) {
      throw new Error(label + " is not visible");
    }
  }

  if (await page.locator("#googleSignin").count()) {
    throw new Error("Google sign-in is still present");
  }

  const cfg = await page.evaluate(() => window.JARVIS_CONFIG || {});
  if (!cfg.SUPABASE_URL || !cfg.SUPABASE_PUBLISHABLE_KEY || !cfg.ASH_GATEWAY_URL) {
    throw new Error("Ash public runtime config is incomplete");
  }

  const visibleText = (await page.locator("body").innerText()).toLowerCase();
  const visibleExposure = forbiddenProviderNames.filter(name => visibleText.includes(name));
  if (visibleExposure.length) {
    throw new Error("Visible UI exposes backend provider names: " + visibleExposure.join(", "));
  }

  const before = await page.evaluate(() => document.documentElement.dataset.theme || "");
  await page.locator("#themeToggle").click();
  await page.waitForTimeout(250);
  const after = await page.evaluate(() => document.documentElement.dataset.theme || "");
  if (before === after) throw new Error("Theme toggle did not change theme");

  if (consoleErrors.length) throw new Error("Console errors: " + consoleErrors.slice(0, 3).join(" | "));
  if (failedRequests.length) throw new Error("Failed requests: " + failedRequests.slice(0, 3).join(" | "));

  console.log(JSON.stringify({
    ok: true,
    url: page.url(),
    httpStatus: nav.status(),
    title: await page.title(),
    providerNamesHidden: true,
    authUi: true,
    themeToggle: true,
    runtimeConfig: true
  }, null, 2));
} finally {
  await browser.close();
}
