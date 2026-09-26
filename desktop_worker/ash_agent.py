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
            self._safe_write(root, rel, content)
            generated.append(rel)
        evidence: list[dict[str, Any]] = []
        if (root / "package.json").exists():
            install = self._run(root, ["npm", "install", "--no-audit", "--no-fund"], 300)
            evidence.append({"command": "npm install", "code": install.returncode, "stderr": install.stderr[-2000:]})
            if install.returncode == 0:
                build = self._run(root, ["npm", "run", "build"], 300)
                evidence.append({"command": "npm run build", "code": build.returncode, "stdout": build.stdout[-2000:], "stderr": build.stderr[-4000:]})
                repaired = self._repair_build(root, request, plan, evidence) if build.returncode != 0 else []
            else:
                repaired = []
        else:
            repaired = []

        review = self.think("""You are Ash's QA lead. Review the evidence below.
Never claim a test passed unless its exit code is 0. Return a concise release-readiness report.

REQUEST:
""" + request + "\n\nFILES:\n" + "\n".join(generated) + "\n\nEVIDENCE:\n" + json.dumps(evidence, indent=2), "medium", action="generate")
        ok = all(item.get("code") == 0 for item in evidence) if evidence else True
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
