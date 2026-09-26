import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";

const cwd="builder-acceptance-output";
const reportPath="builder-visual-acceptance.json";
const report={checks:{},errors:[]};

const child=spawn("npm",["run","preview","--","--host","127.0.0.1","--port","5179"],{cwd,shell:false,stdio:["ignore","pipe","pipe"]});
let logs="";
child.stdout.on("data",d=>logs+=d.toString());
child.stderr.on("data",d=>logs+=d.toString());

async function waitServer(){
  for(let i=0;i<40;i++){
    try{const r=await fetch("http://127.0.0.1:5179/");if(r.ok)return;}catch{}
    await new Promise(r=>setTimeout(r,500));
  }
  throw new Error("Preview server did not start. Logs: "+logs.slice(-3000));
}

let browser;
try{
  await waitServer();
  browser=await chromium.launch({headless:true});
  for(const [name,width,height] of [["desktop",1440,960],["mobile",390,844]]){
    const page=await browser.newPage({viewport:{width,height}});
    page.on("console",m=>{if(m.type()==="error")report.errors.push({view:name,type:"console",text:m.text()})});
    page.on("pageerror",e=>report.errors.push({view:name,type:"page",text:String(e)}));
    const r=await page.goto("http://127.0.0.1:5179/",{waitUntil:"networkidle",timeout:30000});
    if(!r||r.status()>=400)throw new Error(name+" preview HTTP "+(r?.status()||"none"));
    const metrics=await page.evaluate(()=>({
      text:(document.body.innerText||"").replace(/\s+/g," ").trim(),
      overflow:document.documentElement.scrollWidth>window.innerWidth+2,
      buttons:document.querySelectorAll("button,a").length,
      headings:document.querySelectorAll("h1,h2,h3").length,
      sections:document.querySelectorAll("section,main,header,footer").length,
      bodyBg:getComputedStyle(document.body).background,
      bodyFont:getComputedStyle(document.body).fontFamily
    }));
    report[name]=metrics;
    if(metrics.overflow)throw new Error(name+" has horizontal overflow");
    if(metrics.text.length<500)throw new Error(name+" rendered too little meaningful content");
    if(metrics.headings<4||metrics.sections<4||metrics.buttons<3)throw new Error(name+" lacks expected visual/semantic structure");
    if(/lorem ipsum|john doe|acme corp/i.test(metrics.text))throw new Error(name+" contains placeholder content");
    await page.screenshot({path:`builder-${name}.png`,fullPage:true});
    await page.close();
  }
  if(report.errors.length)throw new Error("Browser errors detected: "+JSON.stringify(report.errors.slice(0,8)));
  report.checks.desktop=true;
  report.checks.mobile=true;
  report.checks.noBrowserErrors=true;
  report.ok=true;
}catch(e){
  report.ok=false;report.failure=String(e?.stack||e);
}finally{
  if(browser)await browser.close();
  child.kill("SIGTERM");
  fs.writeFileSync(reportPath,JSON.stringify(report,null,2));
  console.log("=== ASH BUILDER VISUAL ACCEPTANCE ===");
  console.log(JSON.stringify(report,null,2));
}
if(!report.ok)process.exit(1);
