import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const url = Deno.env.get("SUPABASE_URL")!;
const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const admin = createClient(url, serviceKey, { auth: { autoRefreshToken: false, persistSession: false } });

const allowedOrigins = new Set([
  "https://meet-ash.jakeharvey162.workers.dev",
  "https://ash-f4.vercel.app",
  "https://ash.vercel.app",
  "http://127.0.0.1:4173",
  "http://localhost:4173",
  "http://localhost:3000",
  "capacitor://localhost"
]);

function cors(req: Request) {
  const origin = req.headers.get("origin") || "";
  return {
    "Access-Control-Allow-Origin": allowedOrigins.has(origin) ? origin : "https://meet-ash.jakeharvey162.workers.dev",
    "Access-Control-Allow-Headers": "authorization, content-type, apikey, x-ash-device-id, x-ash-device-secret",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Vary": "Origin",
    "Content-Type": "application/json"
  };
}
const json = (req: Request, body: unknown, status=200) => new Response(JSON.stringify(body), { status, headers: cors(req) });
const normalizeCode=(v:string)=>v.toUpperCase().replace(/[^A-Z0-9]/g,"");
async function sha256(v:string){
  const data=new TextEncoder().encode(v);
  const digest=await crypto.subtle.digest("SHA-256",data);
  return [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,"0")).join("");
}
function randomCode(){
  const alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const a=new Uint8Array(8);crypto.getRandomValues(a);
  const s=[...a].map(x=>alphabet[x%alphabet.length]).join("");
  return s.slice(0,4)+"-"+s.slice(4);
}
function randomSecret(){
  const a=new Uint8Array(32);crypto.getRandomValues(a);
  let raw="";for(const b of a)raw+=String.fromCharCode(b);
  return btoa(raw).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
}
async function requireUser(req:Request){
  const auth=req.headers.get("authorization")||"";
  const token=auth.replace(/^Bearer\s+/i,"").trim();
  if(!token)return null;
  const {data,error}=await admin.auth.getUser(token);
  if(error||!data.user)return null;
  return data.user;
}
async function requireDevice(req:Request){
  const deviceId=req.headers.get("x-ash-device-id")||"";
  const secret=req.headers.get("x-ash-device-secret")||"";
  if(!deviceId||!secret)return null;
  const {data:cred}=await admin.from("jarvis_device_credentials").select("device_id,secret_hash").eq("device_id",deviceId).maybeSingle();
  if(!cred)return null;
  const incoming=await sha256(secret);
  if(incoming!==cred.secret_hash)return null;
  const {data:device}=await admin.from("jarvis_devices").select("*").eq("id",deviceId).maybeSingle();
  return device||null;
}
async function parse(req:Request){try{return await req.json()}catch{return {}}}

Deno.serve(async (req:Request)=>{
  if(req.method==="OPTIONS")return new Response("ok",{headers:cors(req)});
  if(req.method!=="POST")return json(req,{error:"Method not allowed"},405);
  const body=await parse(req);
  const action=String(body.action||"");

  if(action==="create_pairing"){
    const user=await requireUser(req);
    if(!user)return json(req,{error:"Unauthorized"},401);
    await admin.from("jarvis_device_pairings").delete().eq("user_id",user.id).is("consumed_at",null).lt("expires_at",new Date().toISOString());
    const code=randomCode();
    const expiresAt=new Date(Date.now()+10*60*1000).toISOString();
    const {error}=await admin.from("jarvis_device_pairings").insert({user_id:user.id,code_hash:await sha256(normalizeCode(code)),expires_at:expiresAt});
    if(error)return json(req,{error:"Could not create pairing code."},500);
    return json(req,{code,expires_at:expiresAt});
  }

  if(action==="claim_pairing"){
    const code=normalizeCode(String(body.code||""));
    if(code.length!==8)return json(req,{error:"Invalid pairing code."},400);
    const hash=await sha256(code);
    const now=new Date().toISOString();
    const {data:pair}=await admin.from("jarvis_device_pairings").select("*").eq("code_hash",hash).is("consumed_at",null).gt("expires_at",now).maybeSingle();
    if(!pair)return json(req,{error:"Pairing code expired or invalid."},400);
    const deviceName=String(body.device_name||"Ash Desktop").trim().slice(0,120)||"Ash Desktop";
    const platform=String(body.platform||"desktop").trim().slice(0,60)||"desktop";
    const capabilities=typeof body.capabilities==="object"&&body.capabilities?body.capabilities:{};
    const {data:existing}=await admin.from("jarvis_devices").select("*").eq("user_id",pair.user_id).eq("device_name",deviceName).maybeSingle();
    let deviceId=existing?.id;
    const devicePayload={
      user_id:pair.user_id,device_name:deviceName,nickname:deviceName,platform,
      app_version:String(body.app_version||"ash-desktop-worker-3"),
      is_trusted:true,last_seen_at:now,capabilities,paired_at:now,connection_mode:"pairing"
    };
    if(deviceId){
      const {error}=await admin.from("jarvis_devices").update(devicePayload).eq("id",deviceId);
      if(error)return json(req,{error:"Could not update device."},500);
    }else{
      const {data,error}=await admin.from("jarvis_devices").insert(devicePayload).select("id").single();
      if(error||!data)return json(req,{error:"Could not register device."},500);
      deviceId=data.id;
    }
    const secret=randomSecret();
    const {error:credErr}=await admin.from("jarvis_device_credentials").upsert({device_id:deviceId,secret_hash:await sha256(secret),last_rotated_at:now},{onConflict:"device_id"});
    if(credErr)return json(req,{error:"Could not issue device credential."},500);
    await admin.from("jarvis_device_pairings").update({consumed_at:now,device_id:deviceId}).eq("id",pair.id);
    return json(req,{device_id:deviceId,device_secret:secret,device_name:deviceName,user_id:pair.user_id});
  }

  if(action==="disconnect_device"){
    const user=await requireUser(req);
    if(!user)return json(req,{error:"Unauthorized"},401);
    const deviceId=String(body.device_id||"");
    const {data:device}=await admin.from("jarvis_devices").select("id,user_id").eq("id",deviceId).maybeSingle();
    if(!device||device.user_id!==user.id)return json(req,{error:"Device not found."},404);
    await admin.from("jarvis_device_credentials").delete().eq("device_id",deviceId);
    await admin.from("jarvis_devices").delete().eq("id",deviceId);
    return json(req,{ok:true});
  }

  const device=await requireDevice(req);
  if(!device)return json(req,{error:"Device authentication failed."},401);
  const deviceId=device.id, userId=device.user_id;
  const now=new Date().toISOString();

  if(action==="heartbeat"){
    await admin.from("jarvis_devices").update({last_seen_at:now}).eq("id",deviceId);
    return json(req,{ok:true,last_seen_at:now});
  }

  if(action==="preferences"){
    const {data:profile,error}=await admin.from("jarvis_profiles")
      .select("assistant_name,wake_word,voice_config,updated_at")
      .eq("user_id",userId)
      .maybeSingle();
    if(error)return json(req,{error:"Could not load preferences."},500);
    const voiceConfig=(profile?.voice_config&&typeof profile.voice_config==="object")?profile.voice_config:{};
    return json(req,{
      assistant_name:String(profile?.assistant_name||"Ash"),
      wake_word:String(profile?.wake_word||profile?.assistant_name||"Ash"),
      wake_aliases:Array.isArray(voiceConfig.wake_aliases)?voiceConfig.wake_aliases:[],
      updated_at:profile?.updated_at||null
    });
  }

  if(action==="jobs"){
    const {data,error}=await admin.from("jarvis_remote_jobs").select("*").eq("user_id",userId).eq("status","queued").or("target_device_id.is.null,target_device_id.eq."+deviceId).order("created_at",{ascending:true}).limit(4);
    if(error)return json(req,{error:"Could not load jobs."},500);
    return json(req,{jobs:data||[]});
  }

  if(action==="claim_job"){
    const jobId=String(body.job_id||"");
    const {data:pending,error:readError}=await admin.from("jarvis_remote_jobs").select("*")
      .eq("id",jobId).eq("user_id",userId).eq("status","queued")
      .or("target_device_id.is.null,target_device_id.eq."+deviceId).maybeSingle();
    if(readError)return json(req,{error:"Could not inspect job."},500);
    if(!pending)return json(req,{job:null});
    if(pending.requires_confirmation===true){
      const {error:holdError}=await admin.from("jarvis_remote_jobs").update({
        status:"waiting_for_confirmation",updated_at:now
      }).eq("id",jobId).eq("user_id",userId).eq("status","queued");
      if(holdError)return json(req,{error:"Could not hold job for approval."},500);
      return json(req,{job:null,waiting_for_confirmation:true});
    }
    const {data,error}=await admin.from("jarvis_remote_jobs").update({status:"running",claimed_at:now,updated_at:now})
      .eq("id",jobId).eq("user_id",userId).eq("status","queued")
      .or("target_device_id.is.null,target_device_id.eq."+deviceId).select("*").maybeSingle();
    if(error)return json(req,{error:"Could not claim job."},500);
    return json(req,{job:data||null});
  }

  if(action==="finish_job"){
    const jobId=String(body.job_id||"");
    const ok=body.ok===true;
    const patch={status:ok?"completed":"failed",result:body.result||{},error:String(body.error||"").slice(0,1200),completed_at:now,updated_at:now};
    const {data,error}=await admin.from("jarvis_remote_jobs").update(patch).eq("id",jobId).eq("user_id",userId).select("id,status").maybeSingle();
    if(error)return json(req,{error:"Could not finish job."},500);
    return json(req,{job:data||null});
  }

  return json(req,{error:"Unknown action."},400);
});