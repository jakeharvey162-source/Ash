const base="https://ftsomveafuskrutqzsvs.supabase.co";
const key="sb_publishable_x3SYM26ShPtf_JIYdvOkEg_kLXb2kIz";
const gateway=base+"/functions/v1/jarvis-ai-gateway";
const stamp=Date.now();
const email="ash-voice-smoke-"+stamp+"@example.com";
const password="AshVoice!"+stamp+"#v7";

const signup=await fetch(base+"/auth/v1/signup",{
  method:"POST",
  headers:{apikey:key,"Content-Type":"application/json"},
  body:JSON.stringify({email,password,data:{name:"Ash Voice Smoke"}})
});
const signupData=await signup.json().catch(()=>({}));
if(!signup.ok||!signupData.access_token) throw new Error("Signup failed: "+signup.status+" "+JSON.stringify(signupData));
const headers={apikey:key,Authorization:"Bearer "+signupData.access_token,"Content-Type":"application/json"};

const voices=await fetch(gateway,{method:"POST",headers,body:JSON.stringify({action:"voices"})});
const vd=await voices.json().catch(()=>({}));
console.log("VOICE CATALOG",JSON.stringify({status:voices.status,count:Array.isArray(vd.voices)?vd.voices.length:0}));
if(!voices.ok) throw new Error("Voice catalog failed");

const speech=await fetch(gateway,{method:"POST",headers,body:JSON.stringify({action:"speech",text:"Ash voice smoke test.",voice_speed:1.07})});
const contentType=speech.headers.get("content-type")||"";
const body=await speech.arrayBuffer();
console.log("VOICE SPEECH",JSON.stringify({status:speech.status,contentType,bytes:body.byteLength}));
if(!speech.ok||!/audio/i.test(contentType)||body.byteLength<500) throw new Error("Speech generation failed");
console.log("ASH VOICE LIVE SMOKE: PASS");
