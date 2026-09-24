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

    def think(self, prompt: str, mode: str = "high") -> str:
        try:
            return self._cloud(prompt, mode=mode)
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

    @staticmethod
    def _extract_json(text: str) -> Any:
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
        candidate = fenced.group(1).strip() if fenced else text.strip()
        starts = [i for i in (candidate.find("{"), candidate.find("[")) if i >= 0]
        start = min(starts) if starts else 0
        value, _ = json.JSONDecoder().raw_decode(candidate[start:])
        return value

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
            diagnosis = self.think(
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
""" + request + "\n\nARCHITECTURE:\n" + json.dumps(plan, indent=2)[:12000] +
                "\n\nBUILD EVIDENCE:\n" + json.dumps(evidence[-4:], indent=2)[:12000],
                "high",
            )
            try:
                patch = self._extract_json(diagnosis)
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
        planner = self.think("""You are Ash's senior product architect. Design a production-minded full-stack web app.
Return ONLY JSON with keys: name, stack, files, acceptance_tests.
Each files entry must have path and purpose. Use relative paths. Never include secrets.
USER REQUEST:
""" + request, "high")
        try:
            plan = self._extract_json(planner)
        except Exception as exc:
            return AgentResult(False, "Planning did not return valid JSON.", {"error": str(exc)})
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
PROJECT REQUEST:
{request}

ARCHITECTURE:
{json.dumps(plan, indent=2)[:12000]}

FILE: {rel}
PURPOSE: {purpose}
"""
            content = self.think(prompt, "high")
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
""" + request + "\n\nFILES:\n" + "\n".join(generated) + "\n\nEVIDENCE:\n" + json.dumps(evidence, indent=2), "medium")
        ok = all(item.get("code") == 0 for item in evidence) if evidence else True
        return AgentResult(ok, review, {"workspace": str(root), "generated_files": generated, "repaired_files": repaired, "plan": plan, "evidence": evidence})


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
