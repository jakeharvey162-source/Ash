import { chromium } from "playwright";

const appUrl=process.env.ASH_LIVE_URL||"https://meet-ash.jakeharvey162.workers.dev/";
const cfgText=await (await fetch(new URL("/config.js",appUrl))).text();
const pick=name=>{const m=cfgText.match(new RegExp(name+"\\s*:\\s*[\"']([^\"']+)[\"']"));return m?m[1]:""};
const base=pick("SUPABASE_URL").replace(/\/$/,""),key=pick("SUPABASE_PUBLISHABLE_KEY");
if(!base||!key)throw new Error("Live config missing Supabase public settings.");
const stamp=Date.now(),email="ash-wake-ui-"+stamp+"@example.com",password="WakeUi!"+stamp+"#9";

async function jfetch(url,opt={}){const r=await fetch(url,opt);let d={};try{d=await r.json()}catch{};return{r,d}}
const signup=await jfetch(base+"/auth/v1/signup",{method:"POST",headers:{apikey:key,"Content-Type":"application/json"},body:JSON.stringify({email,password,data:{full_name:"Wake UI Test"}})});
if(!signup.r.ok||!signup.d.access_token)throw new Error("Signup failed "+signup.r.status);
const s={access_token:signup.d.access_token,refresh_token:signup.d.refresh_token,user:signup.d.user};
const auth={apikey:key,Authorization:"Bearer "+s.access_token,"Content-Type":"application/json"};
const patch=await fetch(base+"/rest/v1/jarvis_profiles?user_id=eq."+s.user.id,{method:"PATCH",headers:{...auth,Prefer:"return=representation"},body:JSON.stringify({
  assistant_name:"Nova",
  wake_word:"Computer",
  preferred_mode:"instant",
  voice_config:{auto_speak:false,hands_free:false,voice_id:"browser:default",wake_aliases:["hey nova","sentinel","computer"]}
})});
if(!patch.ok)throw new Error("Profile patch failed "+patch.status+" "+await patch.text());

const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1366,height:900}});
const errs=[];
page.on("pageerror",e=>errs.push(String(e)));
page.on("console",m=>{if(m.type()==="error"&&!/400|401|503/.test(m.text()))errs.push(m.text())});

await page.addInitScript(session=>{
  class FakeSpeechRecognition{
    static instances=[];
    constructor(){this.continuous=false;this.interimResults=false;this.maxAlternatives=1;this.lang="en-US";FakeSpeechRecognition.instances.push(this)}
    start(){this.onstart?.()}
    stop(){this.onend?.()}
    emit(text,isFinal=true){
      const result={0:{transcript:text},length:1,isFinal};
      this.onresult?.({resultIndex:0,results:[result]});
    }
  }
  window.SpeechRecognition=FakeSpeechRecognition;
  window.webkitSpeechRecognition=FakeSpeechRecognition;
  window.__fakeSpeechInstances=FakeSpeechRecognition.instances;
  if(!navigator.mediaDevices)Object.defineProperty(navigator,"mediaDevices",{value:{},configurable:true});
  navigator.mediaDevices.getUserMedia=async()=>({getTracks:()=>[{stop(){}}]});
  localStorage.setItem("ash-session",JSON.stringify(session));
  localStorage.setItem("ash-voice-enabled","0");
  localStorage.setItem("ash-hands-free-enabled","0");
},s);

await page.goto(appUrl,{waitUntil:"networkidle",timeout:45000});
await page.locator(".shell").waitFor({state:"visible",timeout:20000});
if(!(await page.getByText("Nova",{exact:true}).first().isVisible()))throw new Error("Renamed assistant is not visible in UI");

await page.locator("[data-view='settings']").first().click();
await page.waitForTimeout(100);
if(await page.locator("#assistantName").inputValue()!=="Nova")throw new Error("Assistant name did not persist to settings");
if(await page.locator("#wakeWord").inputValue()!=="Computer")throw new Error("Wake word did not persist to settings");
const aliases=await page.locator("#wakeAliases").inputValue();
if(!/hey nova/i.test(aliases)||!/sentinel/i.test(aliases))throw new Error("Wake aliases did not persist");

await page.locator("#assistantName").fill("Orbit");
await page.locator("#wakeWord").fill("Sentinel");
await page.locator("#wakeAliases").fill("hey orbit, computer, sentinel");
await page.locator("#saveSettings").click();
await page.waitForTimeout(450);
if(!(await page.getByText("Orbit",{exact:true}).first().isVisible()))throw new Error("UI did not update after rename");

await page.locator("[data-view='home']").first().click();
await page.waitForTimeout(150);
const bodyText=(await page.locator("body").innerText()).toLowerCase();
for(const brand of ["groq","openrouter","anthropic","gemini","elevenlabs","bytez","nvidia","supabase"]){
  if(bodyText.includes(brand))throw new Error("Third-party provider leaked in signed-in UI: "+brand);
}
const hf=page.locator("[data-handsfree-toggle]").first();
await hf.click();
await page.waitForTimeout(150);
if(await hf.getAttribute("aria-pressed")!=="true")throw new Error("Hands-free did not enable");

async function emit(text){
  await page.evaluate(t=>window.__fakeSpeechInstances.at(-1)?.emit(t,true),text);
}
async function waitAnswer(match){
  await page.locator("article.ash p").filter({hasText:match}).last().waitFor({state:"visible",timeout:25000});
}
await emit("Sentinel what is your name? Answer only with your name.");
await waitAnswer("Orbit");
const last1=(await page.locator("article.ash p").last().innerText()).trim();
if(!/Orbit/i.test(last1)||/\bAsh\b/i.test(last1))throw new Error("Wake command did not use renamed identity: "+last1);

await page.waitForTimeout(500);
await emit("What is two plus three? Answer only with the number.");
await waitAnswer("5");
const userTexts=await page.locator("article.mine p").allInnerTexts();
if(!userTexts.some(x=>/two plus three/i.test(x)))throw new Error("Follow-up without wake word was not accepted");
const last2=(await page.locator("article.ash p").last().innerText()).trim();
if(!/5/.test(last2))throw new Error("Follow-up answer incorrect: "+last2);

await page.waitForTimeout(500);
await emit("Hey Orbit what is three plus four? Answer only with the number.");
await waitAnswer("7");
const last3=(await page.locator("article.ash p").last().innerText()).trim();
if(!/7/.test(last3))throw new Error("Wake alias did not work: "+last3);

await emit("stop listening");
await page.waitForTimeout(250);
if(await page.locator("[data-handsfree-toggle]").first().getAttribute("aria-pressed")!=="false")throw new Error("Voice stop command did not disable hands-free");

if(errs.length)throw new Error("Browser errors: "+errs.join(" | "));
await page.screenshot({path:"wake-name-acceptance.png",fullPage:true});
console.log(JSON.stringify({ok:true,assistant:"Orbit",wake_word:"Sentinel",followUp:true,alias:true,stopListening:true,thirdPartyUiHidden:true},null,2));
await browser.close();