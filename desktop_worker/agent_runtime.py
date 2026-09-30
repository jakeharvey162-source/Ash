from __future__ import annotations

import ast
import json
import math
import os
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class RuntimeResult:
    ok: bool
    output: str
    tools_used: list[str]
    evidence: list[dict[str, Any]]
    requires_confirmation: bool = False
    pending_tool: dict[str, Any] | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[[dict[str, Any]], Any]
    confirmation_required: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,63}", spec.name):
            raise ValueError("Invalid Ash tool name.")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(name)
        return self._tools[name]

    def descriptions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "confirmation_required": spec.confirmation_required,
            }
            for spec in self._tools.values()
        ]


class AshAgentRuntime:
    """OpenJarvis-inspired local orchestration layer for Ash.

    It adds a typed tool registry and bounded multi-step tool loop while keeping
    Ash's existing provider routing, builder, memory and confirmation boundaries.
    The model never receives unrestricted shell access from this runtime.
    """

    MAX_STEPS = 6

    def __init__(self, agent, workspace_root: pathlib.Path | None = None) -> None:
        self.agent = agent
        self.workspace_root = (
            workspace_root
            or pathlib.Path(
                os.environ.get("ASH_WORKSPACE_ROOT", str(pathlib.Path.home() / "AshWorkspaces"))
            ).expanduser()
        ).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.tools = ToolRegistry()
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        self.tools.register(ToolSpec(
            "calculator",
            "Safely evaluate arithmetic using numbers, parentheses and common math operators.",
            self._tool_calculator,
        ))
        self.tools.register(ToolSpec(
            "memory.search",
            "Search Ash's private local memory for relevant previous information.",
            self._tool_memory_search,
        ))
        self.tools.register(ToolSpec(
            "memory.store",
            "Store a user-approved note in Ash's private local memory.",
            self._tool_memory_store,
            confirmation_required=True,
        ))
        self.tools.register(ToolSpec(
            "files.list",
            "List files and folders inside the Ash workspace only.",
            self._tool_files_list,
        ))
        self.tools.register(ToolSpec(
            "files.read",
            "Read a UTF-8 text file inside the Ash workspace only.",
            self._tool_files_read,
        ))
        self.tools.register(ToolSpec(
            "files.write",
            "Create or replace a UTF-8 text file inside the Ash workspace.",
            self._tool_files_write,
            confirmation_required=True,
        ))
        self.tools.register(ToolSpec(
            "research.live",
            "Use Ash live research mode for current facts when the cloud gateway is available.",
            self._tool_research,
        ))
        self.tools.register(ToolSpec(
            "ash.status",
            "Inspect local Ash backend health, memory and capability status.",
            self._tool_status,
        ))

    @staticmethod
    def _safe_math(expression: str) -> int | float:
        tree = ast.parse(expression, mode="eval")
        binary = {
            ast.Add: lambda a, b: a + b,
            ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b,
            ast.FloorDiv: lambda a, b: a // b,
            ast.Mod: lambda a, b: a % b,
            ast.Pow: lambda a, b: a ** b,
        }
        unary = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}

        def walk(node):
            if isinstance(node, ast.Expression):
                return walk(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in binary:
                value = binary[type(node.op)](walk(node.left), walk(node.right))
                if not math.isfinite(float(value)) or abs(float(value)) > 1e100:
                    raise ValueError("Result is too large.")
                return value
            if isinstance(node, ast.UnaryOp) and type(node.op) in unary:
                return unary[type(node.op)](walk(node.operand))
            raise ValueError("Unsupported arithmetic expression.")

        return walk(tree)

    def _safe_path(self, raw: str) -> pathlib.Path:
        rel = pathlib.Path(str(raw or "."))
        if rel.is_absolute():
            target = rel.expanduser().resolve()
        else:
            target = (self.workspace_root / rel).resolve()
        try:
            target.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError("Ash tools can only access the configured workspace.") from exc
        return target

    def _tool_calculator(self, args: dict[str, Any]) -> Any:
        expression = str(args.get("expression") or "").strip()
        if not expression or len(expression) > 180:
            raise ValueError("Calculator expression is missing or too long.")
        return {"expression": expression, "result": self._safe_math(expression)}

    def _tool_memory_search(self, args: dict[str, Any]) -> Any:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("Memory search query is required.")
        limit = min(8, max(1, int(args.get("limit") or 5)))
        return {"matches": self.agent.offline.memory.search(query, limit=limit)}

    def _tool_memory_store(self, args: dict[str, Any]) -> Any:
        content = str(args.get("content") or "").strip()
        if not content:
            raise ValueError("Memory content is required.")
        self.agent.offline.memory.add(content[:12000], "user_note")
        return {"stored": True}

    def _tool_files_list(self, args: dict[str, Any]) -> Any:
        target = self._safe_path(str(args.get("path") or "."))
        if not target.exists():
            raise FileNotFoundError(str(target))
        if not target.is_dir():
            raise ValueError("files.list requires a directory.")
        items = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:120]:
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })
        return {"path": str(target.relative_to(self.workspace_root)), "items": items}

    def _tool_files_read(self, args: dict[str, Any]) -> Any:
        target = self._safe_path(str(args.get("path") or ""))
        if not target.is_file():
            raise FileNotFoundError(str(target))
        if target.stat().st_size > 200_000:
            raise ValueError("Ash local read is limited to 200 KB per file.")
        content = target.read_text(encoding="utf-8")
        return {"path": str(target.relative_to(self.workspace_root)), "content": content}

    def _tool_files_write(self, args: dict[str, Any]) -> Any:
        target = self._safe_path(str(args.get("path") or ""))
        content = str(args.get("content") or "")
        if not target.name or len(content) > 250_000:
            raise ValueError("Invalid file write.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": str(target.relative_to(self.workspace_root)), "bytes": len(content.encode("utf-8"))}

    def _tool_research(self, args: dict[str, Any]) -> Any:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("Research query is required.")
        answer = self.agent._cloud(query, mode="high", action="research")
        return {"answer": answer}

    def _tool_status(self, _args: dict[str, Any]) -> Any:
        return {
            "routing": self.agent.kernel.health_snapshot(),
            "offline": self.agent.offline.status().__dict__,
            "workspace": str(self.workspace_root),
            "skills": bool(self.agent.kernel.skill_context("research debug build memory")),
        }

    def _planner_prompt(self, request: str) -> str:
        tools = json.dumps(self.tools.descriptions(), ensure_ascii=False)
        return (
            "You are Ash's task router. Decide whether local tools are needed. "
            "Do not reveal hidden reasoning or chain-of-thought. Return one JSON object only. "
            "Use at most 6 steps and only tools from the supplied list. "
            "Prefer zero tool calls for normal conversation. Use research.live for facts that may have changed. "
            "Never invent a path, memory result, file content or tool result. "
            "Do not request files.write or memory.store unless the user's request clearly asks to save/change something. "
            "Schema: {\"steps\":[{\"tool\":\"tool.name\",\"args\":{}}],\"answer_instruction\":\"brief instruction for final response\"}.\n"
            f"TOOLS: {tools}\n"
            f"USER REQUEST: {request[:12000]}"
        )

    def _plan(self, request: str) -> dict[str, Any]:
        try:
            plan = self.agent.think_json(self._planner_prompt(request), attempts=2)
        except Exception:
            return {"steps": [], "answer_instruction": "Answer the user's request directly."}
        if not isinstance(plan, dict):
            return {"steps": [], "answer_instruction": "Answer the user's request directly."}
        steps = []
        for raw in list(plan.get("steps") or [])[: self.MAX_STEPS]:
            if not isinstance(raw, dict):
                continue
            tool = str(raw.get("tool") or "")
            if tool not in self.tools._tools:
                continue
            args = raw.get("args") if isinstance(raw.get("args"), dict) else {}
            steps.append({"tool": tool, "args": args})
        return {
            "steps": steps,
            "answer_instruction": str(plan.get("answer_instruction") or "Use the verified tool results to answer clearly.")[:800],
        }

    def run(self, request: str, mode: str = "high", *, allow_side_effects: bool = False) -> RuntimeResult:
        prompt = str(request or "").strip()
        if not prompt:
            return RuntimeResult(False, "No task was provided.", [], [])

        plan = self._plan(prompt)
        evidence: list[dict[str, Any]] = []
        tools_used: list[str] = []

        for step in plan["steps"]:
            name = step["tool"]
            spec = self.tools.get(name)
            if spec.confirmation_required and not allow_side_effects:
                return RuntimeResult(
                    ok=False,
                    output=f"Ash needs confirmation before running {name}.",
                    tools_used=tools_used,
                    evidence=evidence,
                    requires_confirmation=True,
                    pending_tool=step,
                )
            try:
                result = spec.handler(step["args"])
                tools_used.append(name)
                evidence.append({"tool": name, "ok": True, "result": result})
            except Exception as exc:
                evidence.append({"tool": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:600]})

        if not evidence:
            return RuntimeResult(True, self.agent.think(prompt, mode), [], [])

        evidence_text = json.dumps(evidence, ensure_ascii=False)[:24000]
        final_prompt = (
            "Answer the user's original request using the VERIFIED TOOL EVIDENCE below. "
            "Do not claim a tool succeeded when its evidence says it failed. "
            "Do not invent extra results. Be concise and useful.\n\n"
            f"ORIGINAL REQUEST:\n{prompt}\n\n"
            f"ANSWER INSTRUCTION:\n{plan['answer_instruction']}\n\n"
            f"VERIFIED TOOL EVIDENCE:\n{evidence_text}"
        )
        answer = self.agent.think(final_prompt, mode)
        return RuntimeResult(True, answer, tools_used, evidence)
