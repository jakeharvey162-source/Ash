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

await page.route("**/auth/v1/token?grant_type=password", route => json(route, {
  access_token: "login-token",
  refresh_token: "login-refresh",
  user: { id: "00000000-0000-0000-0000-000000000001", email: "test@example.invalid" }
}));
await page.route("**/auth/v1/signup", route => json(route, {
  user: {
    id: "00000000-0000-0000-0000-000000000002",
    email: "new@example.invalid",
    identities: []
  }
}));
await page.route("**/auth/v1/recover", route => json(route, {}));
await page.route("**/rest/v1/jarvis_profiles**", route => json(route, []));
await page.route("**/rest/v1/jarvis_automations**", route => json(route, []));
await page.route("**/rest/v1/jarvis_remote_jobs**", route => json(route, []));
await page.route("**/rest/v1/jarvis_devices**", route => json(route, []));
await page.route("**/rest/v1/jarvis_integrations**", route => json(route, []));

const errors=[];
page.on("pageerror", e=>errors.push(String(e)));

await page.goto(url,{waitUntil:"networkidle",timeout:30000});
if (!(await page.locator("#authSubmit").isVisible())) throw new Error("Sign in button missing.");
if (!(await page.getByRole("button",{name:"Create account"}).isVisible())) throw new Error("Create account tab missing.");

for (const label of ["Product","Capabilities","Safety","Company"]) {
  const nav = page.getByRole("button",{name:label,exact:true});
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
await page.getByText("If this email already has an account", { exact: false }).waitFor({ state:"visible", timeout:3000 });
if ((await page.locator("#authMsg").textContent()||"").toLowerCase().includes("account created")) throw new Error("Obfuscated signup falsely reported account creation.");

await page.getByRole("button",{name:"Sign in"}).click();
if (await page.locator("#name").count()) throw new Error("Sign-in mode still shows name field.");

await page.locator("#email").fill("test@example.invalid");
await page.getByRole("button",{name:"Forgot password?"}).click();
await page.getByText("Password reset email sent.",{exact:true}).waitFor({state:"visible",timeout:3000});

await page.locator("#password").fill("Password123!");
await page.locator("#authSubmit").click();
await page.locator(".shell").waitFor({state:"visible",timeout:5000});
if (!(await page.getByText("Overview",{exact:true}).isVisible())) throw new Error("Successful sign-in did not open Ash.");

if(errors.length) throw new Error("Browser errors: "+errors.join(" | "));
console.log("ASH AUTH UI SMOKE: PASS");
await browser.close();
