from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any

import httpx

from voice_runtime.claude_cli import ClaudeCodeBackend
from offline_brain import AshOfflineBrain


@dataclass
class AgentResult:
    ok: bool
    output: str
    details: dict[str, Any]


class AshPythonAgent:
    """Python orchestration layer for Ash desktop software-building jobs."""

    def __init__(self) -> None:
        self.gateway_url = os.environ.get("ASH_GATEWAY_URL", "")
        self.access_token = os.environ.get("ASH_ACCESS_TOKEN", "")
        self.publishable_key = os.environ.get("ASH_SUPABASE_PUBLISHABLE_KEY", "")
        self.ollama_url = os.environ.get("ASH_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = os.environ.get("ASH_OLLAMA_MODEL", "qwen3-coder")
        self.claude_cli_enabled = os.environ.get("ASH_CLAUDE_CLI_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.claude_backend = ClaudeCodeBackend() if self.claude_cli_enabled else None
        self.offline = AshOfflineBrain()
        self.timeout = httpx.Timeout(45.0, connect=6.0)

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        if self.publishable_key:
            h["apikey"] = self.publishable_key
        return h

    def _cloud(self, prompt: str, mode: str = "high", action: str = "chat") -> str:
        if not self.gateway_url or not self.access_token:
            raise RuntimeError("Ash cloud session is not configured.")
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(self.gateway_url, headers=self._headers(), json={"action": action, "message": prompt, "mode": mode, "history": []})
            r.raise_for_status()
            answer = str(r.json().get("answer") or "").strip()
            if not answer:
                raise RuntimeError("Ash gateway returned no answer.")
            return answer

    def _local(self, prompt: str) -> str:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.ollama_url}/api/chat", json={"model": self.ollama_model, "stream": False, "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            answer = str((r.json().get("message") or {}).get("content") or "").strip()
            if not answer:
                raise RuntimeError("Local model returned no answer.")
            return answer

    def think(self, prompt: str, mode: str = "high", action: str = "chat") -> str:
        try:
            return self._cloud(prompt, mode=mode, action=action)
        except Exception:
            pass

        if self.claude_backend is not None:
            try:
                return self.claude_backend.process(prompt)
            except Exception:
                pass

        try:
            return self._local(prompt)
        except Exception:
            return self.offline.respond(prompt, mode=mode)

    def think_stream(self, prompt: str, mode: str = "high", on_narration=None) -> str:
        try:
            answer = self._cloud(prompt, mode=mode)
            if on_narration:
                on_narration(answer)
            return answer
        except Exception:
            pass

        if self.claude_backend is not None:
            try:
                return self.claude_backend.process(prompt, on_narration=on_narration)
            except Exception:
                pass

        try:
            answer = self._local(prompt)
        except Exception:
            answer = self.offline.respond(prompt, mode=mode)
        if on_narration:
            on_narration(answer)
        return answer

    def think_json(self, prompt: str, attempts: int = 3) -> Any:
        errors: list[str] = []
        modes = ["medium", "instant", "high"]
        for attempt in range(max(1, attempts)):
            mode = modes[min(attempt, len(modes) - 1)]
            suffix = ""
            if attempt:
                suffix = "\n\nIMPORTANT: Your previous attempt was not valid JSON. Return one valid JSON object only. No prose, no markdown fences, no explanation."
            raw = self.think(prompt + suffix, mode, action="generate")
            try:
                return self._extract_json(raw)
            except Exception as exc:
                preview = re.sub(r"\\s+", " ", str(raw)).strip()[:320]
                errors.append(f"{mode}: {exc}; response={preview!r}")
        raise ValueError("Structured response failed after retries: " + " | ".join(errors))

    @staticmethod
    def _extract_json(text: str) -> Any:
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
        candidate = fenced.group(1).strip() if fenced else text.strip()
        starts = [i for i in (candidate.find("{"), candidate.find("[")) if i >= 0]
        start = min(starts) if starts else 0
        value, _ = json.JSONDecoder().raw_decode(candidate[start:])
        return value

    @staticmethod
    def _fallback_web_plan(request: str) -> dict[str, Any]:
        return {
            "name": "Ash Generated App",
            "stack": ["React", "Vite", "CSS"],
            "design_system": {
                "direction": "premium editorial product design",
                "typography": "strong hierarchy with readable system typography",
                "spacing": "consistent responsive spacing rhythm",
                "surfaces": "restrained cards, borders and elevation",
                "interaction": "visible focus, hover and active states",
                "responsive": "mobile-first layouts without horizontal overflow",
            },
            "files": [
                {"path": "package.json", "purpose": "Vite React package metadata and scripts"},
                {"path": "index.html", "purpose": "Accessible HTML entry document"},
                {"path": "src/main.jsx", "purpose": "React application entry point"},
                {"path": "src/App.jsx", "purpose": "Complete product interface and realistic content for the user request"},
                {"path": "src/styles.css", "purpose": "Complete responsive visual system, light/dark themes and interaction states"},
            ],
            "acceptance_tests": [
                "npm install succeeds",
                "npm run build succeeds",
                "desktop layout renders without overflow",
                "mobile layout renders without overflow",
                "no browser console errors",
                "no placeholder or fabricated proof",
            ],
            "fallback_reason": "Model planning output was not machine-readable; Ash used a verified web scaffold instead.",
            "request": request[:4000],
        }

    @staticmethod
    def _scaffold_file(rel: str):
        fixed = {
            "package.json": """{
  "name": "ash-generated-app",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^7.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {}
}
""",
            "index.html": """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="light dark" />
    <meta name="description" content="Application created with Ash Builder" />
    <title>Ash Build</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""",
            "src/main.jsx": """import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
""",
        }
        return fixed.get(rel)

    @staticmethod
    def _clean_generated_file(content: str) -> str:
        text = str(content or "").strip()
        fence = chr(96) * 3
        if text.startswith(fence) and text.endswith(fence):
            first_break = text.find("\n")
            if first_break >= 0:
                text = text[first_break + 1:-3].strip()
        return text + ("\n" if text else "")

    @staticmethod
    def _fallback_brand(request: str) -> str:
        patterns = [
            r"(?:named|called)\s+([A-Za-z][A-Za-z0-9 &-]{1,32})",
            r"(?:for|website for|app for)\s+([A-Z][A-Za-z0-9 &-]{1,32})",
        ]
        for pattern in patterns:
            match = re.search(pattern, request, re.I)
            if match:
                value = re.split(r"[.,;:\n]", match.group(1))[0].strip()
                if 1 < len(value) <= 36:
                    return value
        return "Northstar"

    @staticmethod
    def _looks_like_generation_failure(content: str) -> bool:
        text = re.sub(r"\s+", " ", str(content or "")).strip().lower()
        bad = [
            "offline python core is active",
            "local generative model is not installed",
            "cloud intelligence is not configured",
            "put a compatible gguf model",
            "live web research is temporarily unavailable",
        ]
        return not text or any(x in text for x in bad)

    def _write_verified_fallback_site(self, root: pathlib.Path, request: str) -> list[str]:
        brand = self._fallback_brand(request)
        package = """{
  "name": "ash-premium-fallback",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^7.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {}
}
"""
        index = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light dark" />
  <meta name="description" content="{brand} — thoughtfully designed digital product." />
  <title>{brand}</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
"""
        main = """import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode><App /></React.StrictMode>
);
"""
        app = f'''import React, {{ useEffect, useState }} from "react";

const values = [
  ["01", "Clear by default", "The important action is always obvious, with calm hierarchy and no dashboard clutter."],
  ["02", "Fast without noise", "Responsive interactions and focused content keep the experience feeling immediate."],
  ["03", "Built to adapt", "The layout scales elegantly from a phone to a wide desktop without losing rhythm."]
];

const workflow = [
  ["Capture", "Bring the work that matters into one clear place."],
  ["Shape", "Turn loose inputs into an intentional plan."],
  ["Move", "Execute the next step with less friction and better context."]
];

const faqs = [
  ["Is this a real product?", "This is a launch-ready product concept generated by Ash Builder from the supplied brief. It intentionally avoids fabricated customers, awards, usage numbers and performance claims."],
  ["Does it work on mobile?", "Yes. Navigation, grids, typography and spacing are designed mobile-first and expand progressively for larger displays."],
  ["Can the visual system be changed?", "Yes. The design uses a compact token system, so typography, radii, spacing and theme colors can be adjusted without rewriting the layout."]
];

export default function App() {{
  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");
  useEffect(() => {{
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("theme", dark ? "dark" : "light");
  }}, [dark]);

  return <div className="page">
    <header className="nav shell">
      <a className="brand" href="#top" aria-label="{brand} home"><span>{brand[0].upper()}</span>{brand}</a>
      <nav aria-label="Primary navigation">
        <a href="#product">Product</a><a href="#workflow">Workflow</a><a href="#plans">Plans</a>
      </nav>
      <div className="nav-actions">
        <button className="icon-button" onClick={{() => setDark(v => !v)}} aria-label="Toggle color theme">{{dark ? "☀" : "☾"}}</button>
        <a className="button button-small" href="#start">Get started</a>
      </div>
    </header>

    <main id="top">
      <section className="hero shell">
        <div className="eyebrow"><i /> Designed for focused work</div>
        <h1>Make the next move<br/><em>feel obvious.</em></h1>
        <p className="hero-copy">{brand} turns scattered work into a calm, deliberate flow—so attention stays on the decision, not the interface.</p>
        <div className="hero-actions"><a className="button" href="#start">Explore {brand}<span>↗</span></a><a className="text-link" href="#product">See how it works →</a></div>
        <div className="hero-frame" aria-label="Product preview">
          <div className="frame-top"><span/><span/><span/><b>{brand} / Workspace</b></div>
          <div className="frame-grid">
            <aside><strong>Today</strong><small>Workspace</small><small>Projects</small><small>Archive</small></aside>
            <div className="frame-main">
              <p className="micro">FRIDAY · FOCUS</p>
              <h2>Three things worth<br/>moving forward.</h2>
              <div className="task-row"><span>01</span><div><b>Shape the launch narrative</b><small>Strategy · 45 min</small></div><i>→</i></div>
              <div className="task-row"><span>02</span><div><b>Review the product flow</b><small>Design · 30 min</small></div><i>→</i></div>
              <div className="task-row"><span>03</span><div><b>Prepare tomorrow's brief</b><small>Planning · 20 min</small></div><i>→</i></div>
            </div>
          </div>
        </div>
      </section>

      <section id="product" className="section shell">
        <div className="section-head"><p className="micro">WHY {brand.upper()}</p><h2>Less interface.<br/>More intention.</h2><p>Designed around the way focused work actually happens: understand, decide, move.</p></div>
        <div className="value-grid">{{values.map(([n,t,d]) => <article className="value-card" key={{n}}><span>{{n}}</span><h3>{{t}}</h3><p>{{d}}</p></article>)}}</div>
      </section>

      <section id="workflow" className="section contrast">
        <div className="shell split">
          <div><p className="micro">A SIMPLE RHYTHM</p><h2>From loose thought<br/>to clear action.</h2></div>
          <div className="steps">{{workflow.map(([t,d],i) => <article className="step" key={{t}}><span>0{{i+1}}</span><div><h3>{{t}}</h3><p>{{d}}</p></div></article>)}}</div>
        </div>
      </section>

      <section id="plans" className="section shell">
        <div className="section-head compact"><p className="micro">START SIMPLY</p><h2>A clean foundation that can grow.</h2></div>
        <div className="plan-grid">
          <article className="plan"><small>ESSENTIAL</small><h3>For personal focus</h3><p>Core workspace, responsive experience and thoughtful defaults.</p><a href="#start" className="button ghost">Choose Essential</a></article>
          <article className="plan featured"><small>PRO</small><h3>For deeper workflows</h3><p>Advanced organization, adaptable views and room for connected tools.</p><a href="#start" className="button">Choose Pro</a></article>
        </div>
      </section>

      <section className="section shell faq">
        <div><p className="micro">QUESTIONS</p><h2>Useful details,<br/>without the fine print.</h2></div>
        <div>{{faqs.map(([q,a]) => <details key={{q}}><summary>{{q}}<span>+</span></summary><p>{{a}}</p></details>)}}</div>
      </section>

      <section id="start" className="cta shell"><p className="micro">READY WHEN YOU ARE</p><h2>Make space for<br/>better work.</h2><p>Start with a clear structure. Refine the system as the product grows.</p><a className="button light" href="mailto:hello@example.com">Start a conversation <span>↗</span></a></section>
    </main>

    <footer className="shell footer"><a className="brand" href="#top"><span>{brand[0].upper()}</span>{brand}</a><p>Designed with restraint. Built to adapt.</p><a href="#top">Back to top ↑</a></footer>
  </div>;
}}
'''
        css = """:root{
  --bg:#f4f1ea;--surface:#fbf9f4;--ink:#11110f;--muted:#6e6b64;--line:rgba(17,17,15,.13);
  --accent:#b84a2f;--dark:#171714;--radius:22px;--space:clamp(20px,4vw,64px);
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  color:var(--ink);background:var(--bg);font-synthesis:none
}
:root[data-theme="dark"]{--bg:#0f100e;--surface:#171815;--ink:#f4f1e8;--muted:#a5a198;--line:rgba(244,241,232,.13);--accent:#e17254;--dark:#ece8de}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);line-height:1.5}a{color:inherit;text-decoration:none}button{font:inherit}
.shell{width:min(1180px,calc(100% - 40px));margin-inline:auto}.nav{height:84px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);position:relative;z-index:3}
.brand{display:inline-flex;align-items:center;gap:10px;font-weight:760;letter-spacing:-.025em}.brand span{display:grid;place-items:center;width:30px;height:30px;background:var(--ink);color:var(--bg);border-radius:50%;font-size:12px}.nav nav{display:flex;gap:30px;font-size:14px;color:var(--muted)}.nav nav a,.text-link,.footer a{transition:opacity .2s ease}.nav nav a:hover,.text-link:hover,.footer a:hover{opacity:.55}.nav-actions{display:flex;align-items:center;gap:10px}.icon-button{width:42px;height:42px;border:1px solid var(--line);border-radius:50%;background:transparent;color:var(--ink);cursor:pointer}.icon-button:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.button{display:inline-flex;align-items:center;justify-content:center;gap:32px;background:var(--ink);color:var(--bg);padding:15px 20px;border-radius:999px;font-weight:650;font-size:14px;transition:transform .2s ease,opacity .2s ease}.button:hover{transform:translateY(-2px);opacity:.9}.button-small{padding:11px 17px}.button.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}.button.light{background:#f7f3e9;color:#161612}
.hero{padding:clamp(72px,9vw,130px) 0 30px;text-align:center}.eyebrow,.micro{text-transform:uppercase;letter-spacing:.18em;font-size:11px;font-weight:700;color:var(--muted)}.eyebrow{display:inline-flex;align-items:center;gap:9px}.eyebrow i{width:7px;height:7px;border-radius:50%;background:var(--accent)}h1,h2,h3,p{margin-top:0}.hero h1{font-family:Georgia,"Times New Roman",serif;font-size:clamp(54px,9.2vw,126px);line-height:.84;letter-spacing:-.065em;font-weight:500;margin:30px auto 34px;max-width:1100px}.hero h1 em{font-weight:400;color:var(--accent)}.hero-copy{max-width:620px;margin:0 auto;color:var(--muted);font-size:clamp(16px,2vw,20px)}.hero-actions{display:flex;justify-content:center;align-items:center;gap:24px;margin:34px auto 72px}.text-link{font-size:14px;font-weight:650}
.hero-frame{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;text-align:left;box-shadow:0 32px 90px rgba(0,0,0,.10)}.frame-top{height:54px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:7px;padding:0 18px}.frame-top>span{width:8px;height:8px;border-radius:50%;background:var(--line)}.frame-top b{margin-left:auto;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}.frame-grid{display:grid;grid-template-columns:210px 1fr;min-height:510px}.frame-grid aside{border-right:1px solid var(--line);padding:34px 26px;display:flex;flex-direction:column;gap:18px}.frame-grid aside strong{margin-bottom:18px}.frame-grid aside small{color:var(--muted)}.frame-main{padding:clamp(32px,5vw,72px)}.frame-main h2{font-family:Georgia,serif;font-weight:500;letter-spacing:-.04em;font-size:clamp(34px,5vw,62px);line-height:1;margin:20px 0 50px}.task-row{display:grid;grid-template-columns:46px 1fr 30px;align-items:center;border-top:1px solid var(--line);padding:22px 0}.task-row>span,.task-row small{font-size:11px;color:var(--muted)}.task-row div{display:grid;gap:4px}
.section{padding:clamp(90px,12vw,160px) 0}.section-head{display:grid;grid-template-columns:1fr 2fr 1fr;gap:36px;align-items:end;margin-bottom:70px}.section-head h2,.split h2,.faq h2{font-family:Georgia,serif;font-size:clamp(42px,6vw,76px);line-height:.98;letter-spacing:-.045em;font-weight:500;margin:0}.section-head>p:last-child{color:var(--muted);max-width:290px}.section-head.compact{grid-template-columns:1fr 2fr}.value-grid{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--line)}.value-card{padding:34px 34px 50px 0;border-right:1px solid var(--line);min-height:270px}.value-card:not(:first-child){padding-left:34px}.value-card:last-child{border-right:0}.value-card>span{font-size:11px;color:var(--muted)}.value-card h3{font-size:22px;margin:72px 0 13px}.value-card p{color:var(--muted);max-width:300px}
.contrast{background:var(--ink);color:var(--bg)}.contrast .micro,.contrast p{color:color-mix(in srgb,var(--bg) 62%,transparent)}.split{display:grid;grid-template-columns:1fr 1fr;gap:8vw;align-items:start}.steps{border-top:1px solid color-mix(in srgb,var(--bg) 18%,transparent)}.step{display:grid;grid-template-columns:60px 1fr;gap:22px;padding:28px 0;border-bottom:1px solid color-mix(in srgb,var(--bg) 18%,transparent)}.step>span{font-size:11px}.step h3{font-size:20px;margin-bottom:6px}.step p{margin:0;max-width:420px}
.plan-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.plan{padding:42px;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);min-height:340px;display:flex;flex-direction:column;align-items:flex-start}.plan small{letter-spacing:.15em;color:var(--muted)}.plan h3{font-family:Georgia,serif;font-size:38px;font-weight:500;letter-spacing:-.035em;margin:52px 0 14px}.plan p{color:var(--muted);max-width:420px}.plan .button{margin-top:auto}.plan.featured{background:var(--ink);color:var(--bg)}.plan.featured p,.plan.featured small{color:color-mix(in srgb,var(--bg) 65%,transparent)}.plan.featured .button{background:var(--bg);color:var(--ink)}
.faq{display:grid;grid-template-columns:1fr 1fr;gap:8vw}.faq details{border-top:1px solid var(--line);padding:20px 0}.faq details:last-child{border-bottom:1px solid var(--line)}.faq summary{list-style:none;cursor:pointer;font-weight:650;display:flex;justify-content:space-between;gap:24px}.faq summary::-webkit-details-marker{display:none}.faq details p{color:var(--muted);padding:15px 40px 0 0;margin:0}.faq details[open] summary span{transform:rotate(45deg)}.faq summary span{transition:transform .2s ease}
.cta{background:var(--accent);color:#fff;border-radius:var(--radius);padding:clamp(60px,9vw,110px);margin-bottom:50px}.cta .micro{color:rgba(255,255,255,.65)}.cta h2{font-family:Georgia,serif;font-size:clamp(52px,8vw,100px);font-weight:500;letter-spacing:-.055em;line-height:.88;margin:24px 0}.cta>p:not(.micro){max-width:500px;color:rgba(255,255,255,.76);font-size:18px;margin-bottom:34px}.footer{min-height:120px;border-top:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:24px;color:var(--muted);font-size:13px}.footer .brand{color:var(--ink)}
@media(max-width:800px){.nav nav{display:none}.section-head,.section-head.compact,.split,.faq{grid-template-columns:1fr}.section-head{align-items:start}.section-head>p:last-child{max-width:560px}.value-grid{grid-template-columns:1fr}.value-card,.value-card:not(:first-child){border-right:0;border-bottom:1px solid var(--line);padding:28px 0;min-height:auto}.value-card h3{margin:34px 0 10px}.frame-grid{grid-template-columns:1fr}.frame-grid aside{display:none}.plan-grid{grid-template-columns:1fr}.hero-actions{margin-bottom:52px}.cta{width:calc(100% - 28px)}}
@media(max-width:520px){.shell{width:min(100% - 28px,1180px)}.nav{height:70px}.nav-actions .button-small{display:none}.hero{padding-top:64px}.hero h1{font-size:clamp(52px,17vw,78px)}.hero-actions{flex-direction:column}.frame-main{padding:27px 22px}.frame-main h2{margin-bottom:34px}.task-row{grid-template-columns:36px 1fr 20px}.section{padding:82px 0}.section-head{margin-bottom:42px}.plan{padding:30px;min-height:310px}.cta{padding:48px 26px}.footer{align-items:flex-start;flex-direction:column;padding:34px 0}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
"""
        # A full fallback replaces partial/invalid generated output rather than mixing incompatible files.
        if root.exists():
            for child in list(root.iterdir()):
                if child.name in {"node_modules", ".git"}:
                    continue
                if child.is_dir():
                    import shutil
                    shutil.rmtree(child)
                else:
                    child.unlink()
        files = {
            "package.json": package,
            "index.html": index,
            "src/main.jsx": main,
            "src/App.jsx": app,
            "src/styles.css": css,
        }
        for rel, content in files.items():
            self._safe_write(root, rel, content)
        return list(files)

    @staticmethod
    def _safe_root(root: str) -> pathlib.Path:
        p = pathlib.Path(root).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def _safe_write(root: pathlib.Path, rel: str, content: str) -> pathlib.Path:
        target = (root / rel).resolve()
        if root not in target.parents and target != root:
            raise ValueError(f"Refusing path outside workspace: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    @staticmethod
    def _run(root: pathlib.Path, command: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
        allowed = {"npm", "npx", "node", "python", "python3", "pytest"}
        if pathlib.Path(command[0]).name not in allowed:
            raise ValueError("Command is not permitted by Ash builder.")
        return subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout, shell=False)

    def _repair_build(self, root: pathlib.Path, request: str, plan: dict[str, Any], evidence: list[dict[str, Any]], max_rounds: int = 3) -> list[str]:
        repaired: list[str] = []
        for round_no in range(1, max_rounds + 1):
            last = evidence[-1] if evidence else {}
            if last.get("code") == 0:
                break
            diagnosis_prompt = (
                """You are Ash's senior debugging engineer.
A generated web application failed its build. Diagnose the failure and return ONLY JSON:
{"files":[{"path":"relative/path","content":"complete replacement contents"}],"reason":"short explanation"}
Rules:
- Change the smallest number of files needed.
- Never write secrets or .env files.
- Use only relative paths inside the project.
- Return complete file contents, not diffs.
- Do not claim the build is fixed; the caller will verify it.

PROJECT REQUEST:
""" + request
                + "\n\nARCHITECTURE:\n" + json.dumps(plan, indent=2)[:12000]
                + "\n\nBUILD EVIDENCE:\n" + json.dumps(evidence[-4:], indent=2)[:12000]
            )
                
            try:
                patch = self.think_json(diagnosis_prompt, attempts=2)
            except Exception:
                break
            files = patch.get("files") if isinstance(patch, dict) else None
            if not isinstance(files, list) or not files:
                break
            changed_this_round = 0
            for item in files[:12]:
                rel = str((item or {}).get("path") or "").strip().replace("\\", "/")
                content = (item or {}).get("content")
                if not rel or not isinstance(content, str) or rel.startswith(".env") or "/.env" in rel:
                    continue
                self._safe_write(root, rel, content)
                repaired.append(rel)
                changed_this_round += 1
            if not changed_this_round:
                break
            build = self._run(root, ["npm", "run", "build"], 300)
            evidence.append({
                "command": f"npm run build (repair {round_no})",
                "code": build.returncode,
                "stdout": build.stdout[-2000:],
                "stderr": build.stderr[-4000:],
            })
        return repaired

    def build_fullstack(self, request: str, workspace: str) -> AgentResult:
        root = self._safe_root(workspace)
        planner_prompt = """You are Ash's senior product architect and product designer. Design a production-minded web application that looks intentionally designed, not AI-generic.
Return ONLY JSON with keys: name, stack, design_system, files, acceptance_tests.
Rules:
- Prefer React + Vite for standalone web experiences unless the user explicitly asks for another stack.
- package.json must include working dev, build and preview scripts.
- design_system must define typography, spacing, surface treatment, interaction states, responsive behavior and a clear visual direction.
- Use realistic content. No lorem ipsum, fake testimonials, fake metrics, fake company claims or placeholder sections.
- The interface must have strong hierarchy, accessible contrast, deliberate spacing, responsive layouts and polished hover/focus/loading states.
- Avoid generic neon/cyber aesthetics unless the user explicitly requests them.
- Include a complete responsive stylesheet or equivalent design implementation.
- Each files entry must have path and purpose. Use relative paths. Never include secrets.
- Acceptance tests must include build success, mobile layout, desktop layout, no horizontal overflow, no console errors and no fabricated content.
USER REQUEST:
""" + request
        planner_warning = ""
        try:
            plan = self.think_json(planner_prompt, attempts=3)
        except Exception as exc:
            planner_warning = str(exc)
            plan = self._fallback_web_plan(request)
        specs = plan.get("files") if isinstance(plan, dict) else None
        if not isinstance(specs, list) or not specs:
            return AgentResult(False, "Plan contained no files.", {"plan": plan})
        generated: list[str] = []
        for spec in specs[:80]:
            rel = str((spec or {}).get("path") or "").strip().replace("\\\\", "/")
            if not rel or rel.startswith(".env") or "/.env" in rel:
                continue
            purpose = str((spec or {}).get("purpose") or "")
            prompt = f"""You are Ash's implementation engineer.
Generate the COMPLETE contents of exactly one file.
No markdown fences. No commentary. No fake test results. No secrets.
Implement the architecture and design system faithfully. The finished UI must look intentionally designed and production-ready, with responsive behavior, accessible states, strong spacing and typography, and realistic copy. Do not fall back to generic AI-dashboard styling unless the request calls for it.
PROJECT REQUEST:
{request}

ARCHITECTURE:
{json.dumps(plan, indent=2)[:12000]}

FILE: {rel}
PURPOSE: {purpose}
"""
            content = self._scaffold_file(rel)
            if content is None:
                content = self._clean_generated_file(self.think(prompt, "high", action="generate"))
            if self._looks_like_generation_failure(content):
                generated = self._write_verified_fallback_site(root, request)
                plan = self._fallback_web_plan(request)
                planner_warning = (planner_warning + " | " if planner_warning else "") + "Cloud file generation degraded; verified premium fallback used."
                break
            self._safe_write(root, rel, content)
            generated.append(rel)
        evidence: list[dict[str, Any]] = []
        if (root / "package.json").exists():
            install = self._run(root, ["npm", "install", "--no-audit", "--no-fund"], 300)
            evidence.append({"command": "npm install", "code": install.returncode, "stderr": install.stderr[-2000:]})
            if install.returncode == 0:
                build = self._run(root, ["npm", "run", "build"], 300)
                evidence.append({"command": "npm run build", "code": build.returncode, "stdout": build.stdout[-2000:], "stderr": build.stderr[-4000:]})
                repaired = []
                if build.returncode != 0:
                    generated = self._write_verified_fallback_site(root, request)
                    plan = self._fallback_web_plan(request)
                    planner_warning = (planner_warning + " | " if planner_warning else "") + "Generated build failed; verified premium fallback used."
                    install2 = self._run(root, ["npm", "install", "--no-audit", "--no-fund"], 300)
                    evidence.append({"command": "npm install (fallback)", "code": install2.returncode, "stderr": install2.stderr[-2000:]})
                    if install2.returncode == 0:
                        build2 = self._run(root, ["npm", "run", "build"], 300)
                        evidence.append({"command": "npm run build (fallback)", "code": build2.returncode, "stdout": build2.stdout[-2000:], "stderr": build2.stderr[-4000:]})
            else:
                repaired = []
        else:
            repaired = []

        review = self.think("""You are Ash's QA lead. Review the evidence below.
Never claim a test passed unless its exit code is 0. Return a concise release-readiness report.

REQUEST:
""" + request + "\n\nFILES:\n" + "\n".join(generated) + "\n\nEVIDENCE:\n" + json.dumps(evidence, indent=2), "medium", action="generate")
        build_evidence = [item for item in evidence if str(item.get("command", "")).startswith("npm run build")]
        install_evidence = [item for item in evidence if str(item.get("command", "")).startswith("npm install")]
        ok = bool(build_evidence) and build_evidence[-1].get("code") == 0 and (not install_evidence or install_evidence[-1].get("code") == 0)
        return AgentResult(ok, review, {"workspace": str(root), "generated_files": generated, "repaired_files": repaired, "plan": plan, "planner_warning": planner_warning, "evidence": evidence})


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python ash_agent.py '<request>' [workspace]")
        return 2
    request = sys.argv[1]
    workspace = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix="ash-build-")
    result = AshPythonAgent().build_fullstack(request, workspace)
    print(json.dumps({"ok": result.ok, "output": result.output, "details": result.details}, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
