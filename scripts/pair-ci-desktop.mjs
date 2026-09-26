import fs from "node:fs";

const live=process.env.ASH_LIVE_URL||"https://meet-ash.jakeharvey162.workers.dev/";
const cfg=await (await fetch(new URL("/config.js",live))).text();
const pick=name=>cfg.match(new RegExp(name+"\\s*:\\s*[\"']([^\"']+)[\"']"))?.[1]||"";
const base=pick("SUPABASE_URL").replace(/\/$/,"");
const key=pick("SUPABASE_PUBLISHABLE_KEY");
const gateway=pick("ASH_GATEWAY_URL");
if(!base||!key||!gateway)throw new Error("Ash live public config is incomplete.");

const stamp=Date.now();
const email="ash-builder-paired-"+stamp+"@example.com";
const password="BuilderPair-"+stamp+"-A7!";
const signup=await fetch(base+"/auth/v1/signup",{
  method:"POST",headers:{apikey:key,"Content-Type":"application/json"},
  body:JSON.stringify({email,password,data:{full_name:"Ash Paired Builder CI"}})
});
const user=await signup.json().catch(()=>({}));
if(!signup.ok||!user.access_token)throw new Error("CI signup failed: "+signup.status);

const link=base+"/functions/v1/ash-device-link";
const pairRes=await fetch(link,{
  method:"POST",headers:{apikey:key,Authorization:"Bearer "+user.access_token,"Content-Type":"application/json"},
  body:JSON.stringify({action:"create_pairing"})
});
const pair=await pairRes.json().catch(()=>({}));
if(!pairRes.ok||!pair.code)throw new Error("CI pairing code creation failed.");

const claimRes=await fetch(link,{
  method:"POST",headers:{"Content-Type":"application/json"},
  body:JSON.stringify({
    action:"claim_pairing",code:pair.code,device_name:"Ash Paired Builder CI",platform:"linux-ci",
    app_version:"builder-live-acceptance",
    capabilities:{builder:true,verified_builds:true,screen_vision:true,computer_control:false}
  })
});
const claim=await claimRes.json().catch(()=>({}));
if(!claimRes.ok||!claim.device_id||!claim.device_secret)throw new Error("CI desktop pairing failed.");

console.log("::add-mask::"+claim.device_secret);
const envPath=process.env.GITHUB_ENV;
if(!envPath)throw new Error("GITHUB_ENV unavailable.");
fs.appendFileSync(envPath,[
  "ASH_GATEWAY_URL="+gateway,
  "ASH_DEVICE_ID="+claim.device_id,
  "ASH_DEVICE_SECRET="+claim.device_secret,
  "ASH_SUPABASE_PUBLISHABLE_KEY="+key,
  "ASH_REQUIRE_LIVE_BUILDER=1"
].join("\n")+"\n");
console.log("ASH PAIRED BUILDER SESSION: READY");
