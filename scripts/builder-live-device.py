from __future__ import annotations
import json, os, pathlib, re, shutil, sys, time
import httpx

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"desktop_worker"))
from ash_agent import AshPythonAgent

APP=os.environ.get("ASH_LIVE_URL","https://meet-ash.jakeharvey162.workers.dev/").rstrip("/")
cfg=httpx.get(APP+"/config.js",timeout=15).text
def pick(name:str)->str:
    m=re.search(rf'{name}\s*:\s*["\']([^"\']+)["\']',cfg)
    return m.group(1) if m else ""

base=pick("SUPABASE_URL").rstrip("/")
key=pick("SUPABASE_PUBLISHABLE_KEY")
gateway=pick("ASH_GATEWAY_URL")
if not (base and key and gateway):
    raise SystemExit("Live Ash config missing required public endpoints.")

stamp=int(time.time()*1000)
email=f"ash-live-builder-{stamp}@example.com"
password=f"LiveBuilder-{stamp}-A9!"
signup=httpx.post(
    base+"/auth/v1/signup",
    headers={"apikey":key,"Content-Type":"application/json"},
    json={"email":email,"password":password,"data":{"full_name":"Ash Builder Acceptance"}},
    timeout=20,
)
signup.raise_for_status()
session=signup.json()
token=session.get("access_token")
if not token:
    raise SystemExit("Test account returned no session.")
headers={"apikey":key,"Authorization":"Bearer "+token,"Content-Type":"application/json"}

pair=httpx.post(base+"/functions/v1/ash-device-link",headers=headers,json={"action":"create_pairing"},timeout=20)
pair.raise_for_status()
code=pair.json().get("code")
claim=httpx.post(
    base+"/functions/v1/ash-device-link",
    headers={"Content-Type":"application/json"},
    json={"action":"claim_pairing","code":code,"device_name":"Live Builder CI","platform":"linux-ci","app_version":"builder-live","capabilities":{"builder":True,"verified_builds":True}},
    timeout=20,
)
claim.raise_for_status()
device=claim.json()
device_id=device.get("device_id")
device_secret=device.get("device_secret")
if not device_id or not device_secret:
    raise SystemExit("Paired device credentials missing.")

os.environ["ASH_GATEWAY_URL"]=gateway
os.environ["ASH_SUPABASE_PUBLISHABLE_KEY"]=key
agent=AshPythonAgent()
agent.set_device_credentials(device_id,device_secret)

root=ROOT/"builder-live-acceptance"
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)
cases=[
    ("coffee","Build a premium warm editorial website for a Johannesburg specialty coffee shop named Ember & Oak. Use cream, espresso and terracotta tones, refined typography, real menu sections, responsive layout, dark/light mode, and no fake testimonials, awards or metrics."),
    ("saas","Build a premium calm productivity SaaS called LumaFlow. Use cool neutral tones, crisp hierarchy, pricing, feature comparison, FAQ, responsive mobile/desktop behavior, dark/light mode, and no fake testimonials, awards or fabricated metrics.")
]
report={"cases":[]}
for slug,prompt in cases:
    result=agent.build_fullstack(prompt,str(root/slug))
    warning=str(result.details.get("planner_warning") or "")
    if not result.ok:
        raise SystemExit(f"{slug}: builder failed: {result.output}")
    if "verified premium fallback used" in warning.lower():
        print("BUILDER WARNING",slug,warning,flush=True)
        raise SystemExit(f"{slug}: cloud generation fell back instead of using live model")
    report["cases"].append({
        "slug":slug,
        "ok":True,
        "generated_files":result.details.get("generated_files",[]),
        "repaired_files":result.details.get("repaired_files",[]),
        "evidence":result.details.get("evidence",[]),
        "planner_warning":warning,
        "summary":result.output[:1200],
    })

(root/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print("ASH LIVE DEVICE BUILDER: PASS")
print(json.dumps(report,indent=2))
