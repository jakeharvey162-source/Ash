import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";

const cases=["coffee","saas"];
const report={cases:[]};
const banned=/\b(lorem ipsum|placeholder|fake testimonial|trusted by 10,000|award[- ]winning|#1 rated)\b/i;

function startPreview(dir,port){
  const cp=spawn(process.execPath,["node_modules/vite/bin/vite.js","preview","--host","127.0.0.1","--port",String(port)],{cwd:dir,stdio:["ignore","pipe","pipe"]});
  return cp;
}
async function waitHttp(url,timeout=20000){
  const end=Date.now()+timeout;
  while(Date.now()<end){
    try{const r=await fetch(url);if(r.ok)return;}catch{}
    await new Promise(r=>setTimeout(r,300));
  }
  throw new Error("Preview did not start: "+url);
}

const browser=await chromium.launch({headless:true});
try{
  for(let i=0;i<cases.length;i++){
    const slug=cases[i],dir="builder-acceptance/"+slug,port=4300+i;
    const cp=startPreview(dir,port);
    const errors=[];
    try{
      await waitHttp("http://127.0.0.1:"+port+"/");
      const page=await browser.newPage({viewport:{width:1440,height:960}});
      page.on("pageerror",e=>errors.push(String(e)));
      page.on("console",m=>{if(m.type()==="error")errors.push(m.text())});
      await page.goto("http://127.0.0.1:"+port+"/",{waitUntil:"networkidle",timeout:30000});
      const desktop=await page.evaluate(()=>({w:document.documentElement.scrollWidth,v:innerWidth,text:document.body.innerText,buttons:document.querySelectorAll("button,a").length,sections:document.querySelectorAll("section").length}));
      if(desktop.w>desktop.v+2)throw new Error(slug+" desktop horizontal overflow");
      if(banned.test(desktop.text))throw new Error(slug+" contains fabricated/placeholder copy");
      if(desktop.text.trim().length<500)throw new Error(slug+" generated experience is too thin");
      if(desktop.buttons<4||desktop.sections<3)throw new Error(slug+" lacks product depth");
      await page.screenshot({path:"builder-acceptance/"+slug+"-desktop.png",fullPage:true});

      const themeBefore=await page.evaluate(()=>document.documentElement.dataset.theme||getComputedStyle(document.documentElement).colorScheme||"");
      const toggle=page.getByRole("button",{name:/theme|color/i}).first();
      if(await toggle.count()){
        await toggle.click();await page.waitForTimeout(120);
        const themeAfter=await page.evaluate(()=>document.documentElement.dataset.theme||getComputedStyle(document.documentElement).colorScheme||"");
        if(themeBefore===themeAfter)throw new Error(slug+" theme toggle did not change theme state");
      }else throw new Error(slug+" has no accessible theme toggle");

      await page.setViewportSize({width:390,height:844});
      await page.reload({waitUntil:"networkidle"});
      const mobile=await page.evaluate(()=>({w:document.documentElement.scrollWidth,v:innerWidth,text:document.body.innerText}));
      if(mobile.w>mobile.v+2)throw new Error(slug+" mobile horizontal overflow");
      if(banned.test(mobile.text))throw new Error(slug+" mobile contains fabricated/placeholder copy");
      await page.screenshot({path:"builder-acceptance/"+slug+"-mobile.png",fullPage:true});
      if(errors.length)throw new Error(slug+" browser errors: "+errors.join(" | "));
      report.cases.push({slug,desktop:true,mobile:true,theme:true,noOverflow:true,noFabrication:true,noConsoleErrors:true});
      await page.close();
    }finally{
      cp.kill("SIGKILL");
      await new Promise(resolve=>cp.once("close",resolve));
    }
  }
}finally{await browser.close()}
fs.writeFileSync("builder-acceptance/visual-report.json",JSON.stringify(report,null,2));
console.log("ASH BUILDER VISUAL QUALITY: PASS");
console.log(JSON.stringify(report,null,2));
