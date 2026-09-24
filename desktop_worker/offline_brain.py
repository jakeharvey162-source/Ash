from __future__ import annotations

import ast
import json
import math
import os
import pathlib
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class OfflineStatus:
    mode: str
    backend: str
    model_path: str | None
    memory_path: str
    generative_ready: bool


class LocalMemory:
    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as db:
            db.execute(
                """
                create table if not exists memories(
                    id integer primary key autoincrement,
                    created_at real not null,
                    kind text not null,
                    content text not null
                )
                """
            )
            db.execute("create index if not exists memories_created_idx on memories(created_at desc)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def add(self, content: str, kind: str = "conversation") -> None:
        text = str(content or "").strip()
        if not text:
            return
        with self._lock, self._connect() as db:
            db.execute(
                "insert into memories(created_at, kind, content) values(?,?,?)",
                (time.time(), kind[:40], text[:12000]),
            )
            db.execute(
                "delete from memories where id not in (select id from memories order by created_at desc limit 1500)"
            )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9_]{3,}", text.lower())
            if token not in {"the", "and", "for", "that", "with", "this", "from", "you", "your", "ash"}
        }

    def search(self, query: str, limit: int = 6) -> list[str]:
        wanted = self._tokens(query)
        if not wanted:
            return []
        with self._lock, self._connect() as db:
            rows = db.execute(
                "select content from memories order by created_at desc limit 250"
            ).fetchall()
        scored: list[tuple[float, str]] = []
        for (content,) in rows:
            have = self._tokens(content)
            overlap = len(wanted & have)
            if overlap:
                scored.append((overlap / max(1, len(wanted)), content))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [text for _, text in scored[:limit]]


class DirectGGUFBackend:
    """Runs a GGUF model inside Python. No network or cloud API is required."""

    def __init__(self, model_path: pathlib.Path | None) -> None:
        self.model_path = model_path
        self._llm = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self.model_path and self.model_path.exists())

    def _load(self):
        if not self.available:
            raise RuntimeError("No local GGUF model is configured.")
        if self._llm is not None:
            return self._llm
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not installed. Install desktop_worker/requirements-local.optional.txt."
            ) from exc

        n_ctx = int(os.environ.get("ASH_LOCAL_CTX", "8192"))
        n_gpu_layers = int(os.environ.get("ASH_LOCAL_GPU_LAYERS", "-1"))
        threads = max(2, int(os.environ.get("ASH_LOCAL_THREADS", str(os.cpu_count() or 4))))
        with self._lock:
            if self._llm is None:
                self._llm = Llama(
                    model_path=str(self.model_path),
                    n_ctx=n_ctx,
                    n_threads=threads,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
        return self._llm

    def chat(self, system: str, prompt: str, history: list[dict[str, str]] | None = None, mode: str = "high") -> str:
        llm = self._load()
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for item in (history or [])[-12:]:
            role = "assistant" if item.get("role") == "assistant" else "user"
            content = str(item.get("content") or "").strip()
            if content:
                messages.append({"role": role, "content": content[:10000]})
        messages.append({"role": "user", "content": prompt})
        result = llm.create_chat_completion(
            messages=messages,
            temperature=0.18 if mode == "instant" else 0.3,
            max_tokens=1000 if mode == "instant" else 2600 if mode == "high" else 1800,
        )
        text = str(result["choices"][0]["message"]["content"] or "").strip()
        if not text:
            raise RuntimeError("Local GGUF model returned an empty response.")
        return text


class AshOfflineBrain:
    """Private local Ash brain: direct model inference + memory + deterministic fallback."""

    def __init__(self) -> None:
        root = pathlib.Path(os.environ.get("ASH_LOCAL_HOME", str(pathlib.Path.home() / ".ash"))).expanduser()
        model_dir = pathlib.Path(os.environ.get("ASH_MODEL_DIR", str(root / "models"))).expanduser()
        configured = os.environ.get("ASH_GGUF_MODEL", "").strip()
        model_path = pathlib.Path(configured).expanduser() if configured else self._discover_model(model_dir)
        self.memory = LocalMemory(pathlib.Path(os.environ.get("ASH_LOCAL_MEMORY", str(root / "memory.sqlite3"))).expanduser())
        self.backend = DirectGGUFBackend(model_path)

    @staticmethod
    def _discover_model(model_dir: pathlib.Path) -> pathlib.Path | None:
        if not model_dir.exists():
            return None
        candidates = sorted(model_dir.glob("*.gguf"), key=lambda p: p.stat().st_size)
        if not candidates:
            return None
        preferred = [p for p in candidates if any(k in p.name.lower() for k in ("qwen", "gemma", "llama", "phi"))]
        return (preferred or candidates)[0]

    def status(self) -> OfflineStatus:
        return OfflineStatus(
            mode="offline",
            backend="llama_cpp_direct" if self.backend.available else "python_micro_core",
            model_path=str(self.backend.model_path) if self.backend.model_path else None,
            memory_path=str(self.memory.path),
            generative_ready=self.backend.available,
        )

    @staticmethod
    def _safe_math(expression: str) -> float | int:
        tree = ast.parse(expression, mode="eval")
        allowed_bin = {
            ast.Add: lambda a, b: a + b,
            ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b,
            ast.FloorDiv: lambda a, b: a // b,
            ast.Mod: lambda a, b: a % b,
            ast.Pow: lambda a, b: a**b,
        }
        allowed_un = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}

        def walk(node):
            if isinstance(node, ast.Expression):
                return walk(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in allowed_bin:
                left, right = walk(node.left), walk(node.right)
                value = allowed_bin[type(node.op)](left, right)
                if isinstance(value, (int, float)) and (not math.isfinite(float(value)) or abs(float(value)) > 1e100):
                    raise ValueError("Result is too large.")
                return value
            if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_un:
                return allowed_un[type(node.op)](walk(node.operand))
            raise ValueError("Unsupported expression.")

        return walk(tree)

    def _micro_core(self, prompt: str, recalled: list[str]) -> str:
        text = prompt.strip()
        lower = text.lower()

        math_match = re.fullmatch(r"(?:calculate|what is|compute)?\s*([0-9+\-*/().%\s]{1,120})\??", lower)
        if math_match:
            try:
                return str(self._safe_math(math_match.group(1)))
            except Exception:
                pass

        if any(key in lower for key in ("offline status", "local status", "local ai status")):
            s = self.status()
            return json.dumps(s.__dict__, indent=2)

        if recalled and any(key in lower for key in ("remember", "recall", "what did", "we discussed")):
            return "I found these relevant local memories:\n\n" + "\n\n".join(f"- {m[:700]}" for m in recalled)

        if lower in {"hi", "hello", "hey", "hey ash", "ash"}:
            return "I'm here. I'm running in Ash's offline Python core right now."

        return (
            "Ash's offline Python core is active, including local memory, routing and deterministic tools, "
            "but a local generative model is not installed yet. Put a compatible GGUF model in ~/.ash/models "
            "and install llama-cpp-python to enable full offline conversation without cloud APIs."
        )

    def respond(
        self,
        prompt: str,
        mode: str = "high",
        history: list[dict[str, str]] | None = None,
        remember: bool = True,
    ) -> str:
        recalled = self.memory.search(prompt)
        memory_context = "\n".join(f"- {item[:1600]}" for item in recalled)
        system = (
            "You are Ash running entirely on the user's computer with no cloud AI calls. "
            "Be natural, capable, concise and truthful. Never claim an action happened without evidence. "
            "Use recalled local memory only when relevant. Keep private data local. "
            "For consequential computer actions, require the explicit execution/confirmation layer.\n"
            + (f"Relevant local memory:\n{memory_context}" if memory_context else "")
        )
        if self.backend.available:
            answer = self.backend.chat(system, prompt, history=history, mode=mode)
        else:
            answer = self._micro_core(prompt, recalled)

        if remember:
            self.memory.add("USER: " + prompt, "user")
            self.memory.add("ASH: " + answer, "assistant")
        return answer
