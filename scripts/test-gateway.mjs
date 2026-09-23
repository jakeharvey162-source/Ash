import handler from "../api/ash.js";

class Res{
  constructor(){this.statusCode=200;this.headers={};this.parts=[]}
  setHeader(k,v){this.headers[k.toLowerCase()]=v}
  end(v=""){if(v)this.parts.push(Buffer.isBuffer(v)?v:Buffer.from(String(v)))}
  body(){return Buffer.concat(this.parts).toString("utf8")}
  json(){return JSON.parse(this.body()||"{}")}
}

const realFetch=global.fetch;
let providerCalls=0;
global.fetch=async(url)=>{
  const s=String(url);
  if(s.includes("/auth/v1/user")) return new Response(JSON.stringify({id:"u1"}),{status:200});
  if(s.includes("/rest/v1/jarvis_profiles")) return new Response(JSON.stringify([{assistant_name:"Ash",personality_preset:"adaptive"}]),{status:200});
  if(s.includes("api.groq.com/openai/v1/chat/completions")){providerCalls++;return new Response(JSON.stringify({choices:[{message:{content:"mock answer"}}]}),{status:200})}
  if(s.includes("api.anthropic.com/v1/messages")){providerCalls++;return new Response(JSON.stringify({content:[{text:"mock specialist"}]}),{status:200})}
  if(s.includes("api.elevenlabs.io/v1/text-to-speech")) return new Response(new Uint8Array([1,2,3]),{status:200,headers:{"content-type":"audio/mpeg"}});
  throw new Error("Unexpected fetch "+s);
};

function req(method="POST",body={},auth=true){return {method,body,headers:auth?{authorization:"Bearer test"}:{}}}

process.env.GROQ_API_KEY="test";
process.env.ANTHROPIC_API_KEY="test";
process.env.ELEVENLABS_API_KEY="test";

let r=new Res();await handler(req("GET",{},false),r);let d=r.json();
if(r.statusCode!==200||!d.cloud_ready||!d.voice_ready||d.identity!=="Ash")throw new Error("health failed");

r=new Res();await handler(req("POST",{action:"chat",message:"hello",mode:"instant"},false),r);
if(r.statusCode!==401)throw new Error("auth guard failed");

r=new Res();await handler(req("POST",{action:"chat",message:"hello",mode:"instant"}),r);d=r.json();
if(r.statusCode!==200||d.answer!=="mock answer"||d.assistant_name!=="Ash")throw new Error("instant failed");

r=new Res();await handler(req("POST",{action:"chat",message:"plan it",mode:"high"}),r);d=r.json();
if(r.statusCode!==200||!Array.isArray(d.agents)||d.agents.length<4)throw new Error("high mode failed");

r=new Res();await handler(req("POST",{action:"speech",text:"hello"}),r);
if(r.statusCode!==200||r.headers["content-type"]!=="audio/mpeg")throw new Error("speech failed");

if(providerCalls<3)throw new Error("routing not exercised");
global.fetch=realFetch;
console.log("ASH GATEWAY MOCK INTEGRATION: PASS");
