from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any

import httpx

from voice_runtime.claude_cli import ClaudeCodeBackend
from offline_brain import AshOfflineBrain
from agent_kernel import AgentKernel
from agent_runtime import AshAgentRuntime
from openjarvis_bridge import OpenJarvisBackend


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
        self.device_id = os.environ.get("ASH_DEVICE_ID", "")
        self.device_secret = os.environ.get("ASH_DEVICE_SECRET", "")
        self.publishable_key = os.environ.get("ASH_SUPABASE_PUBLISHABLE_KEY", "")
        self.ollama_url = os.environ.get("ASH_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = os.environ.get("ASH_OLLAMA_MODEL", "qwen3-coder")
        self.ollama_vision_model = os.environ.get("ASH_OLLAMA_VISION_MODEL", "qwen3-vl:4b")
        self.claude_cli_enabled = os.environ.get("ASH_CLAUDE_CLI_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.claude_backend = ClaudeCodeBackend() if self.claude_cli_enabled else None
        self.offline = AshOfflineBrain()
        self.kernel = AgentKernel()
        self.runtime = AshAgentRuntime(self)
        self.openjarvis = OpenJarvisBackend()
        self.timeout = httpx.Timeout(45.0, connect=6.0)

    def set_device_credentials(self, device_id: str, device_secret: str) -> None:
        self.device_id = str(device_id or "")
        self.device_secret = str(device_secret or "")

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        elif self.device_id and self.device_secret and self.publishable_key:
            # Supabase's edge transport expects an Authorization header even when
            # Ash authenticates the principal with its own revocable device secret.
            h["Authorization"] = f"Bearer {self.publishable_key}"
        if self.device_id and self.device_secret:
            h["X-Ash-Device-ID"] = self.device_id
            h["X-Ash-Device-Secret"] = self.device_secret
        if self.publishable_key:
            h["apikey"] = self.publishable_key
        return h

    def _cloud(self, prompt: str, mode: str = "high", action: str = "chat") -> str:
        if not self.gateway_url or not (self.access_token or (self.device_id and self.device_secret)):
            raise RuntimeError("Ash cloud or paired-device session is not configured.")
        source_mode = action == "generate" and prompt.startswith("You are Ash's implementation engineer.\nGenerate the COMPLETE contents of exactly one file.")
        payload = {"action": action, "message": prompt, "mode": mode, "history": []}
        if source_mode:
            payload["output_format"] = "source"
        # The source route has a 65-second budget; do not abandon it at 45 seconds.
        timeout = httpx.Timeout(70.0, connect=6.0) if source_mode else self.timeout
        with httpx.Client(timeout=timeout) as client:
            r = client.post(self.gateway_url, headers=self._headers(), json=payload)
            r.raise_for_status()
            answer = str(r.json().get("answer") or "").strip()
            if not answer:
                raise RuntimeError("Ash gateway returned no answer.")
            return answer

    def _generate_source(self, prompt: str) -> str:
        def checked(generate):
            source = self._clean_generated_file(generate())
            if self._looks_like_generation_failure(source):
                raise RuntimeError("Provider returned an assistant fallback instead of source.")
            return source

        try:
            return self.kernel.route(
                prompt,
                [
                    ("cloud", lambda: checked(lambda: self._cloud(prompt, mode="high", action="generate")), 0.0),
                    ("ollama", lambda: checked(lambda: self._local(prompt)), 8.0),
                ],
                action="generate",
                mode="high",
                preserve_whitespace=True,
            )
        except RuntimeError as exc:
            raise RuntimeError("Source generation unavailable: " + str(exc)) from exc

    @staticmethod
    def _map_plan_coordinates(data: dict[str, Any], width: int, height: int) -> dict[str, Any]:
        """Convert model-normalized pointer coordinates to real screen pixels."""
        if not isinstance(data, dict):
            raise RuntimeError("Ash computer vision returned an invalid plan.")
        space = str(data.get("coordinate_space") or "").strip().lower()
        actions = []
        for raw in list(data.get("actions") or [])[:4]:
            if not isinstance(raw, dict):
                continue
            action = dict(raw)
            if space == "normalized_1000" and str(action.get("type") or "") in {"move", "click", "double_click"}:
                try:
                    nx = max(0.0, min(1000.0, float(action.get("x", 0))))
                    ny = max(0.0, min(1000.0, float(action.get("y", 0))))
                    action["x"] = round(nx / 1000.0 * max(1, int(width) - 1))
                    action["y"] = round(ny / 1000.0 * max(1, int(height) - 1))
                except Exception:
                    pass
            actions.append(action)
        return {
            **data,
            "actions": actions,
            "coordinate_space": "screen_pixels",
        }

    def _local_computer_plan(self, goal: str, screenshot_base64: str, width: int, height: int) -> dict[str, Any]:
        prompt = "\n".join([
            "You are Ash Computer Control running locally on the user's own computer.",
            "Inspect the screenshot and choose the smallest safe next actions toward the goal.",
            'Return ONE JSON object only using this schema: {"done":boolean,"summary":string,"coordinate_space":"normalized_1000","actions":[{"type":"launch_app|open_url|move|click|double_click|type_text|press|hotkey|scroll|wait","x":number,"y":number,"text":string,"key":string,"keys":[string],"amount":number,"seconds":number}]}',
            "Maximum 4 actions.",
            "For pointer actions, x and y MUST use normalized 0-1000 coordinates: 0,0 is top-left and 1000,1000 is bottom-right regardless of screenshot size.",
            "For click or double-click targets, aim near the visual center of the target with a clear margin from its edges.",
            "Never type passwords, OTPs, card numbers, recovery codes, private keys, or other authentication secrets.",
            "Never approve purchases, financial transfers, destructive deletion, security-setting changes, or account permission changes.",
            "If a sensitive/manual step is required, return done=true with a summary asking the user to do it manually.",
            "Do not claim success unless the screenshot proves it.",
            "GOAL: " + str(goal or ""),
        ])
        with httpx.Client(timeout=httpx.Timeout(35.0, connect=2.0)) as client:
            r = client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_vision_model,
                    "stream": False,
                    "format": "json",
                    "messages": [{"role": "user", "content": prompt, "images": [str(screenshot_base64 or "")]}],
                    "options": {"temperature": 0.1},
                },
            )
            r.raise_for_status()
            raw = str((r.json().get("message") or {}).get("content") or "").strip()
        if not raw:
            raise RuntimeError("Local Ash vision returned no plan.")
        data = self._extract_json(raw)
        if not isinstance(data, dict):
            raise RuntimeError("Local Ash vision returned an invalid plan.")
        allowed = {"launch_app", "open_url", "move", "click", "double_click", "type_text", "press", "hotkey", "scroll", "wait"}
        actions = [a for a in (data.get("actions") or []) if isinstance(a, dict) and str(a.get("type") or "") in allowed][:4]
        mapped = self._map_plan_coordinates({
            "done": data.get("done") is True,
            "summary": str(data.get("summary") or ""),
            "coordinate_space": str(data.get("coordinate_space") or ""),
            "actions": actions,
            "vision_source": "local",
        }, width, height)
        return mapped

    def plan_computer(self, goal: str, screenshot_base64: str, width: int, height: int) -> dict[str, Any]:
        cloud_error: Exception | None = None
        if self.gateway_url and (self.access_token or (self.device_id and self.device_secret)):
            payload = {
                "action": "computer_plan",
                "message": str(goal or ""),
                "screenshot_base64": str(screenshot_base64 or ""),
                "screen_width": int(width),
                "screen_height": int(height),
            }
            try:
                last_error: Exception | None = None
                for attempt in range(2):
                    try:
                        with httpx.Client(timeout=httpx.Timeout(42.0, connect=6.0)) as client:
                            r = client.post(self.gateway_url, headers=self._headers(), json=payload)
                            if r.status_code >= 400:
                                raise RuntimeError(f"Ash computer vision returned HTTP {r.status_code}: {r.text[:300]}")
                            data = r.json()
                        if not isinstance(data, dict):
                            raise RuntimeError("Ash computer vision returned an invalid plan.")
                        data.setdefault("vision_source", "cloud")
                        return self._map_plan_coordinates(data, width, height)
                    except Exception as exc:
                        last_error = exc
                        transient = isinstance(exc, httpx.TransportError) or any(
                            f"HTTP {status}" in str(exc) for status in (429, 502, 503, 504)
                        )
                        if attempt == 0 and transient:
                            time.sleep(4)
                            continue
                        raise
                if last_error is not None:
                    raise last_error
            except Exception as exc:
                cloud_error = exc

        try:
            return self._local_computer_plan(goal, screenshot_base64, width, height)
        except Exception as local_exc:
            if cloud_error is not None:
                raise RuntimeError(
                    "Ash computer vision is unavailable in both cloud and local modes. "
                    f"Cloud: {cloud_error}. Local model {self.ollama_vision_model}: {local_exc}"
                ) from local_exc
            raise RuntimeError(
                "Ash computer vision needs either a paired/cloud session or a local Ollama vision model. "
                f"Local model {self.ollama_vision_model} failed: {local_exc}"
            ) from local_exc

    def _local(self, prompt: str) -> str:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.ollama_url}/api/chat", json={"model": self.ollama_model, "stream": False, "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            answer = str((r.json().get("message") or {}).get("content") or "").strip()
            if not answer:
                raise RuntimeError("Local model returned no answer.")
            return answer

    @staticmethod
    def _openjarvis_profile_for(prompt: str, action: str = "chat") -> str:
        if action == "research":
            return "research"
        text = str(prompt or "").lower()
        if len(text) > 14000 or any(k in text for k in ("long document", "large document", "many files", "recursive", "decompose")):
            return "long_context"
        if any(k in text for k in ("debug", "traceback", "why is this failing", "root cause", "diagnose", "regression")):
            return "react"
        if any(k in text for k in ("research", "investigate", "compare sources", "fact check", "deep dive")):
            return "research"
        return "orchestrator"

    def think(self, prompt: str, mode: str = "high", action: str = "chat") -> str:
        prepared = self.kernel.prepare_prompt(prompt, action=action)
        candidates = [
            ("cloud", lambda: self._cloud(prepared, mode=mode, action=action), 0.0 if action == "generate" else 12.0),
        ]
        if self.claude_backend is not None:
            candidates.append(("claude_cli", lambda: self.claude_backend.process(prepared), 20.0))
        if self.openjarvis.available:
            oj_profile = self._openjarvis_profile_for(prompt, action)
            candidates.append(("openjarvis", lambda: self.openjarvis.ask(prepared, profile=oj_profile), 20.0))
        candidates.extend([
            ("ollama", lambda: self._local(prepared), 8.0),
            ("offline", lambda: self.offline.respond(prompt, mode=mode), 0.0),
        ])
        return self.kernel.route(prompt, candidates, action=action, mode=mode)

    def run_agent(self, prompt: str, mode: str = "high", *, allow_side_effects: bool = False):
        """Run Ash's bounded tool-using desktop agent."""
        return self.runtime.run(prompt, mode=mode, allow_side_effects=allow_side_effects)

    def think_stream(self, prompt: str, mode: str = "high", on_narration=None) -> str:
        prepared = self.kernel.prepare_prompt(prompt, action="chat")

        try:
            answer = self.kernel.invoke(
                "cloud",
                lambda: self._cloud(prepared, mode=mode),
                prompt=prompt,
                action="chat",
                mode=mode,
                cooldown_seconds=12.0,
            )
            if on_narration:
                on_narration(answer)
            return answer
        except Exception:
            pass

        if self.claude_backend is not None:
            try:
                return self.kernel.invoke(
                    "claude_cli",
                    lambda: self.claude_backend.process(prepared, on_narration=on_narration),
                    prompt=prompt,
                    action="chat",
                    mode=mode,
                    cooldown_seconds=20.0,
                )
            except Exception:
                pass

        if self.openjarvis.available:
            try:
                oj_profile = self._openjarvis_profile_for(prompt, "chat")
                answer = self.kernel.invoke(
                    "openjarvis",
                    lambda: self.openjarvis.ask(prepared, profile=oj_profile),
                    prompt=prompt,
                    action="chat",
                    mode=mode,
                    cooldown_seconds=20.0,
                )
                if on_narration:
                    on_narration(answer)
                return answer
            except Exception:
                pass

        try:
            answer = self.kernel.invoke(
                "ollama",
                lambda: self._local(prepared),
                prompt=prompt,
                action="chat",
                mode=mode,
                cooldown_seconds=8.0,
            )
        except Exception:
            answer = self.kernel.invoke(
                "offline",
                lambda: self.offline.respond(prompt, mode=mode),
                prompt=prompt,
                action="chat",
                mode=mode,
                cooldown_seconds=0.0,
            )
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

    def _write_verified_fallback_site(self, root: pathlib.Path, request: str, plan: dict[str, Any] | None = None) -> list[str]:
        plan = plan if isinstance(plan, dict) else {}
        brand = str(plan.get("name") or self._fallback_brand(request)).strip()[:48] or self._fallback_brand(request)
        content_plan = plan.get("content") if isinstance(plan.get("content"), dict) else {}
        hero_title = str(content_plan.get("hero_title") or "Make the next move feel obvious.").strip()[:120]
        hero_summary = str(content_plan.get("hero_summary") or f"{brand} turns scattered work into a calm, deliberate flow—so attention stays on the decision, not the interface.").strip()[:320]
        primary_cta = str(content_plan.get("primary_cta") or f"Explore {brand}").strip()[:60]
        admin_requested = "ADMIN REQUIREMENT:" in request or bool(re.search(r"\badmin(?: area| panel| dashboard)?\b", request, re.I))
        planned_features = content_plan.get("features") if isinstance(content_plan.get("features"), list) else []
        safe_features = []
        for item in planned_features[:3]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()[:70]
            body = str(item.get("body") or "").strip()[:220]
            if title and body:
                safe_features.append([f"{len(safe_features)+1:02d}", title, body])
        if len(safe_features) != 3:
            safe_features = [
                ["01", "Clear by default", "The important action is always obvious, with calm hierarchy and no dashboard clutter."],
                ["02", "Fast without noise", "Responsive interactions and focused content keep the experience feeling immediate."],
                ["03", "Built to adapt", "The layout scales elegantly from a phone to a wide desktop without losing rhythm."],
            ]
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

const values = {json.dumps(safe_features, ensure_ascii=False)};

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
        <h1>{hero_title}</h1>
        <p className="hero-copy">{hero_summary}</p>
        <div className="hero-actions"><a className="button" href="#start">{primary_cta}<span>↗</span></a><a className="text-link" href="#product">See how it works →</a></div>
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
        if admin_requested:
            app = app.replace(
                '  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");',
                '  const [dark, setDark] = useState(() => localStorage.getItem("theme") !== "light");\n'
                '  const [adminOpen, setAdminOpen] = useState(false);\n'
                '  const [siteCopy, setSiteCopy] = useState(() => { try { return JSON.parse(localStorage.getItem("site-copy") || "null") || {hero_title: ' + json.dumps(hero_title) + ', hero_summary: ' + json.dumps(hero_summary) + '}; } catch { return {hero_title: ' + json.dumps(hero_title) + ', hero_summary: ' + json.dumps(hero_summary) + '}; } });\n'
                '  const [draftCopy, setDraftCopy] = useState(siteCopy);'
            )
            app = app.replace('<h1>{hero_title}</h1>', '<h1>{siteCopy.hero_title}</h1>')
            app = app.replace('<p className="hero-copy">{hero_summary}</p>', '<p className="hero-copy">{siteCopy.hero_summary}</p>')
            app = app.replace(
                '<a className="button button-small" href="#start">Get started</a>',
                '<button className="admin-trigger" onClick={() => { setDraftCopy(siteCopy); setAdminOpen(true); }}>Admin</button><a className="button button-small" href="#start">Get started</a>'
            )
            admin_panel = '''
      {adminOpen && <section className="admin-shell" id="admin" aria-label="Local content admin">
        <div className="admin-panel">
          <div className="admin-head"><div><p className="micro">LOCAL ADMIN DEMO</p><h2>Edit homepage content</h2></div><button className="icon-button" onClick={() => setAdminOpen(false)} aria-label="Close admin">×</button></div>
          <p className="admin-note">Changes are saved only in this browser. This demo is not cloud sync and has no production authentication.</p>
          <label>Hero title<input value={draftCopy.hero_title} onChange={e => setDraftCopy({...draftCopy, hero_title:e.target.value})} maxLength="120" /></label>
          <label>Hero summary<textarea rows="4" value={draftCopy.hero_summary} onChange={e => setDraftCopy({...draftCopy, hero_summary:e.target.value})} maxLength="320" /></label>
          <div className="admin-actions"><button className="button ghost" onClick={() => { setDraftCopy(siteCopy); setAdminOpen(false); }}>Cancel</button><button className="button" onClick={() => { setSiteCopy(draftCopy); localStorage.setItem("site-copy", JSON.stringify(draftCopy)); setAdminOpen(false); }}>Save changes</button></div>
        </div>
      </section>}
'''
            app = app.replace('    </main>', admin_panel + '\n    </main>')

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
.admin-trigger{border:1px solid var(--line);background:transparent;color:var(--ink);padding:10px 14px;border-radius:999px;cursor:pointer}.admin-trigger:hover{border-color:var(--accent)}
.admin-shell{position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.48);display:grid;place-items:center;padding:20px;backdrop-filter:blur(12px)}.admin-panel{width:min(680px,100%);max-height:88vh;overflow:auto;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:24px;padding:28px;box-shadow:0 30px 100px rgba(0,0,0,.3)}.admin-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.admin-head h2{font-family:Georgia,serif;font-size:36px;font-weight:500;margin:8px 0 18px}.admin-note{color:var(--muted);font-size:13px}.admin-panel label{display:grid;gap:8px;font-weight:650;margin-top:18px}.admin-panel input,.admin-panel textarea{width:100%;border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:14px;padding:13px 14px;font:inherit}.admin-panel input:focus,.admin-panel textarea:focus{outline:2px solid var(--accent);outline-offset:2px}.admin-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:24px}
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
Return ONLY one compact JSON object with keys: name, stack, design_system, content, files, acceptance_tests.
STRICT SIZE LIMIT: keep the entire JSON under 3200 characters. Do not include file contents in this planning response.
Rules:
- Prefer React + Vite for standalone web experiences unless the user explicitly asks for another stack.
- Keep stack to a short array of technologies.
- design_system must use short string values for: direction, typography, spacing, surfaces, interaction, responsive.
- content must contain: hero_title, hero_summary, primary_cta, and features. features must be exactly 3 objects with title and body, all specific to the user's requested product/business and containing no fabricated proof.
- files must contain no more than 8 items and each item must contain only path and a one-sentence purpose.
- package.json must include working dev, build and preview scripts when generated later.
- Use realistic content. No lorem ipsum, fake testimonials, fake metrics, fake company claims or placeholder sections.
- The interface must have strong hierarchy, accessible contrast, deliberate spacing, responsive layouts and polished hover/focus/loading states.
- Avoid generic neon/cyber aesthetics unless the user explicitly requests them.
- Include a complete responsive stylesheet or equivalent design implementation.
- Use relative paths. Never include secrets.
- acceptance_tests must be a short array covering build success, mobile layout, desktop layout, no horizontal overflow, no console errors and no fabricated content.
USER REQUEST:
""" + request
        planner_warning = ""
        live_plan = True
        generation_mode = "generated_source"
        try:
            plan = self.think_json(planner_prompt, attempts=3)
        except Exception as exc:
            live_plan = False
            generation_mode = "fallback_scaffold"
            planner_warning = str(exc)
            plan = self._fallback_web_plan(request)
        specs = plan.get("files") if isinstance(plan, dict) else None
        if not isinstance(specs, list) or not specs:
            return AgentResult(False, "Plan contained no files.", {"plan": plan})
        generated: list[str] = []
        request_lc = request.lower()
        marketing_surface = live_plan and any(token in request_lc for token in (
            "website", "landing page", "landing experience", "marketing site", "product site",
            "portfolio", "restaurant", "coffee shop", "cafe", "saas", "startup", "pricing page"
        ))
        raw_source_opt_in = os.environ.get("ASH_BUILDER_RAW_SOURCE", "").strip().lower() in {"1", "true", "yes", "on"}
        if marketing_surface and not raw_source_opt_in:
            generation_mode = "planned_renderer"
            generated = self._write_verified_fallback_site(root, request, plan)
            planner_warning = (planner_warning + " | " if planner_warning else "") + "Live AI brief, design system and content rendered through Ash's verified production renderer."
            specs = []
        for spec in specs[:80]:
            rel = str((spec or {}).get("path") or "").strip().replace("\\\\", "/")
            if not rel or rel.startswith(".env") or "/.env" in rel:
                continue
            purpose = str((spec or {}).get("purpose") or "")
            prompt = f"""You are Ash's implementation engineer.
Generate the COMPLETE contents of exactly one file.
Keep source concise and under 14000 characters. Finish all components, functions and delimiters.
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
                try:
                    content = self._generate_source(prompt)
                except Exception as exc:
                    planner_warning = (planner_warning + " | " if planner_warning else "") + str(exc)
                    content = ""
            if self._looks_like_generation_failure(content):
                generation_mode = "recovery_renderer" if live_plan else "fallback_scaffold"
                if live_plan:
                    generated = self._write_verified_fallback_site(root, request, plan)
                    planner_warning = (planner_warning + " | " if planner_warning else "") + "Live AI plan rendered through the verified production source renderer after the long-form source route degraded."
                else:
                    generated = self._write_verified_fallback_site(root, request)
                    plan = self._fallback_web_plan(request)
                    planner_warning = (planner_warning + " | " if planner_warning else "") + "Cloud planning and file generation degraded; verified premium fallback used."
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
                    repaired = self._repair_build(root, request, plan, evidence, max_rounds=2)
                if evidence[-1].get("code") != 0:
                    generation_mode = "recovery_renderer" if live_plan else "fallback_scaffold"
                    if live_plan:
                        generated = self._write_verified_fallback_site(root, request, plan)
                        planner_warning = (planner_warning + " | " if planner_warning else "") + "Generated build failed; live AI plan was repaired through the verified production source renderer."
                    else:
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

        build_evidence = [item for item in evidence if str(item.get("command", "")).startswith("npm run build")]
        install_evidence = [item for item in evidence if str(item.get("command", "")).startswith("npm install")]
        ok = bool(build_evidence) and build_evidence[-1].get("code") == 0 and (not install_evidence or install_evidence[-1].get("code") == 0)
        degraded = generation_mode in {"fallback_scaffold", "recovery_renderer"}
        review = ("Build passed." if ok else "Build failed; inspect the command evidence.")
        if degraded:
            review += " A fallback renderer was used; the original requested functionality is not verified."
        elif generation_mode == "planned_renderer":
            review += " The site uses an AI plan with the built-in renderer."
        if repaired:
            review += f" Repaired {len(set(repaired))} file(s) before rebuilding."
        review += " Browser interactions, accessibility and task requirements still need acceptance testing."
        return AgentResult(ok, review, {"workspace": str(root), "generated_files": generated, "repaired_files": repaired, "plan": plan, "planner_warning": planner_warning, "evidence": evidence, "generation_mode": generation_mode, "degraded": degraded, "verification": {"build_passed": ok, "requirements_verified": False, "browser_verified": False}})


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
