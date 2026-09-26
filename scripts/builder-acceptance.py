from __future__ import annotations
import json, os, pathlib, re, shutil, sys
import httpx

BASE="https://ftsomveafuskrutqzsvs.supabase.co"
KEY="sb_publishable_x3SYM26ShPtf_JIYdvOkEg_kLXb2kIz"
GATEWAY=BASE+"/functions/v1/jarvis-ai-gateway"
OUT=pathlib.Path("builder-acceptance-output").resolve()
REPORT=pathlib.Path("builder-acceptance.json").resolve()

def fail(msg, report):
    report["ok"]=False
    report["failure"]=msg
    REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    raise SystemExit(1)

stamp=str(__import__("time").time_ns())
email=f"ash-builder-acceptance-{stamp}@example.com"
password=f"AshBuilder!{stamp}#B9"
report={"email":email,"checks":{}}

with httpx.Client(timeout=30) as client:
    r=client.post(BASE+"/auth/v1/signup",headers={"apikey":KEY,"Content-Type":"application/json"},json={"email":email,"password":password,"data":{"name":"Builder Acceptance"}})
    data=r.json()
    if r.status_code>=400 or not data.get("access_token"):
        fail("Could not create builder acceptance user: "+r.text,report)
    token=data["access_token"]

os.environ["ASH_GATEWAY_URL"]=GATEWAY
os.environ["ASH_ACCESS_TOKEN"]=token
os.environ["ASH_SUPABASE_PUBLISHABLE_KEY"]=KEY
os.environ["ASH_CLAUDE_CLI_ENABLED"]="0"

sys.path.insert(0,str(pathlib.Path("desktop_worker").resolve()))
from ash_agent import AshPythonAgent

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

prompt="""Build a premium responsive launch website for a fictional productivity app named Orbit.
Use React + Vite and include package.json scripts for dev, build, and preview.
The visual direction should feel editorial and expensive rather than generic AI/cyber:
- confident typographic hierarchy
- restrained modern color system
- strong spacing rhythm
- polished cards and interactive states
- responsive navigation and sections
- accessible contrast and focus states
- dark/light support
- meaningful realistic copy, not lorem ipsum
- hero, product value section, workflow section, pricing section, FAQ and CTA
- mobile width must not horizontally overflow
Do not use external paid assets and do not add fake customer logos, fake reviews, fake user counts, fake awards or fake performance claims.
"""
agent=AshPythonAgent()
result=agent.build_fullstack(prompt,str(OUT))
report["result_ok"]=result.ok
report["summary"]=result.output[:3000]
report["details"]=result.details

if not result.ok:
    fail("Ash Builder returned failure: "+result.output,report)

pkg=OUT/"package.json"
if not pkg.exists():
    fail("Builder produced no package.json",report)
try:
    package=json.loads(pkg.read_text(encoding="utf-8"))
except Exception as exc:
    fail("package.json is invalid: "+str(exc),report)

scripts=package.get("scripts") or {}
for required in ("dev","build","preview"):
    if not scripts.get(required):
        fail(f"package.json is missing {required} script",report)
report["checks"]["scripts"]=True

evidence=result.details.get("evidence") or []
builds=[e for e in evidence if str(e.get("command","")).startswith("npm run build")]
if not builds or builds[-1].get("code")!=0:
    fail("No verified successful npm run build evidence",report)
report["checks"]["verified_build"]=True

files=[p for p in OUT.rglob("*") if p.is_file() and "node_modules" not in p.parts and "dist" not in p.parts]
if len(files)<4:
    fail("Builder generated too few project files",report)
report["checks"]["project_files"]=len(files)

for p in files:
    rel=p.relative_to(OUT).as_posix()
    if rel.startswith(".env") or "/.env" in rel:
        fail("Builder wrote an environment secret file: "+rel,report)
report["checks"]["no_env_files"]=True

text_parts=[]
for p in files:
    if p.suffix.lower() in {".js",".jsx",".ts",".tsx",".css",".html",".json",".md"}:
        try:
            text_parts.append(p.read_text(encoding="utf-8",errors="ignore"))
        except Exception:
            pass
blob="\n".join(text_parts)
if re.search(r"\b(lorem ipsum|acme corp|example testimonial|john doe)\b",blob,re.I):
    fail("Builder emitted placeholder/demo copy",report)

secret_patterns=[
    r"sk-[A-Za-z0-9_-]{16,}",
    r"gsk_[A-Za-z0-9_-]{16,}",
    r"AIza[0-9A-Za-z_-]{20,}",
    r"nvapi-[A-Za-z0-9_-]{16,}"
]
if any(re.search(p,blob) for p in secret_patterns):
    fail("Builder emitted credential-like content",report)
report["checks"]["no_secret_patterns"]=True

style_blob="\n".join(p.read_text(encoding="utf-8",errors="ignore") for p in files if p.suffix.lower() in {".css",".scss",".jsx",".tsx",".js",".ts"})
quality_signals={
    "responsive": bool(re.search(r"@media|clamp\(|minmax\(|grid-template|flex-wrap",style_blob,re.I)),
    "interaction": bool(re.search(r":hover|:focus|transition|transform",style_blob,re.I)),
    "spacing": bool(re.search(r"gap\s*:|padding\s*:|--.*space",style_blob,re.I)),
    "typography": bool(re.search(r"font-size|font-weight|letter-spacing|line-height",style_blob,re.I)),
    "surfaces": bool(re.search(r"border-radius|box-shadow|background",style_blob,re.I)),
    "theme": bool(re.search(r"prefers-color-scheme|data-theme|dark|light",style_blob,re.I)),
}
report["design_signals"]=quality_signals
if sum(quality_signals.values())<5:
    fail("Generated UI did not meet minimum design-system quality signals",report)
report["checks"]["design_system_static"]=True

report["ok"]=True
REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8")
print("=== ASH BUILDER ACCEPTANCE ===")
print(json.dumps(report,indent=2))
