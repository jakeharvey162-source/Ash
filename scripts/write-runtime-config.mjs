import fs from "node:fs";

const publicBase=String(process.env.ASH_PUBLIC_API_BASE||"").replace(/\/$/,"");
if(!publicBase){
  console.log("Ash runtime config: direct API mode (existing config preserved).");
  process.exit(0);
}
const config=`window.JARVIS_CONFIG = {
  SUPABASE_URL: ${JSON.stringify(publicBase)},
  SUPABASE_PUBLISHABLE_KEY: "",
  ASH_GATEWAY_URL: ${JSON.stringify(publicBase+"/functions/v1/jarvis-ai-gateway")}
};
`;
fs.writeFileSync("public/config.js",config);
console.log("Ash runtime config: same-origin shield enabled.");
