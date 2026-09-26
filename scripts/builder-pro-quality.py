from __future__ import annotations
import json, pathlib, shutil, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "desktop_worker"))
from ash_agent import AshPythonAgent

root = pathlib.Path("builder-acceptance").resolve()
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)

cases = [
    {
        "slug": "coffee",
        "prompt": "Build a premium editorial-style responsive website for a Johannesburg specialty coffee shop named Ember & Oak. Use warm sophisticated typography, strong whitespace, light and dark mode, a realistic menu and booking/contact experience. No neon cyber style, fake awards, fake testimonials, fake customer counts, lorem ipsum, or placeholder proof."
    },
    {
        "slug": "saas",
        "prompt": "Build a polished modern productivity SaaS landing experience named LumaFlow. It should feel calm, expensive and human-designed, with strong hierarchy, subtle motion-ready states, responsive pricing and FAQ sections, dark and light themes, accessible focus states and realistic product copy. Do not use generic AI dashboard visuals, fake metrics, testimonials, awards or lorem ipsum."
    }
]

agent = AshPythonAgent()
report = {"cases": []}
for case in cases:
    workspace = root / case["slug"]
    result = agent.build_fullstack(case["prompt"], str(workspace))
    entry = {
        "slug": case["slug"],
        "prompt": case["prompt"],
        "ok": bool(result.ok),
        "workspace": str(workspace),
        "generated_files": result.details.get("generated_files", []),
        "planner_warning": result.details.get("planner_warning", ""),
        "evidence": result.details.get("evidence", []),
        "summary": result.output[:1800],
    }
    report["cases"].append(entry)
    if not result.ok:
        print(json.dumps(report, indent=2))
        raise SystemExit("Builder failed case: " + case["slug"])

(root / "builder-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("ASH BUILDER GENERATION: PASS")
print(json.dumps(report, indent=2))
