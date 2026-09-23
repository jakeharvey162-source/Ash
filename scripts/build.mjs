import { cpSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const dist = resolve(root, "dist");
mkdirSync(dist, { recursive: true });

for (const file of ["index.html", "manifest.webmanifest", "sw.js"]) cpSync(resolve(root, file), resolve(dist, file));
cpSync(resolve(root, "src"), resolve(dist, "src"), { recursive: true });
cpSync(resolve(root, "icons"), resolve(dist, "icons"), { recursive: true });

const cfg = {
  SUPABASE_URL: process.env.ASH_SUPABASE_URL || "https://ftsomveafuskrutqzsvs.supabase.co",
  SUPABASE_PUBLISHABLE_KEY: process.env.ASH_SUPABASE_PUBLISHABLE_KEY || "sb_publishable_x3SYM26ShPtf_JIYdvOkEg_kLXb2kIz",
  ASH_GATEWAY_URL: process.env.ASH_GATEWAY_URL || "https://ftsomveafuskrutqzsvs.supabase.co/functions/v1/jarvis-ai-gateway"
};
writeFileSync(resolve(dist, "config.js"), `window.JARVIS_CONFIG = ${JSON.stringify(cfg, null, 2)};\n`);
