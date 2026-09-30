from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass
class BackendHealth:
    name: str
    successes: int = 0
    failures: int = 0
    avg_latency_ms: float = 0.0
    cooldown_until: float = 0.0
    last_error: str = ""

    @property
    def cooling_down(self) -> bool:
        return self.cooldown_until > time.time()


class AgentKernel:
    """Small, privacy-first routing kernel for Ash's desktop agent.

    It keeps backend fallback state, bounded operational traces and optional
    local skill instructions without storing raw prompts in telemetry.
    """

    def __init__(self, home: pathlib.Path | None = None) -> None:
        root = home or pathlib.Path(
            os.environ.get("ASH_LOCAL_HOME", str(pathlib.Path.home() / ".ash"))
        ).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        self.trace_path = pathlib.Path(
            os.environ.get("ASH_AGENT_TRACE", str(root / "agent-traces.jsonl"))
        ).expanduser()
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self.skill_dirs = [
            pathlib.Path(__file__).resolve().with_name("skills"),
            root / "skills",
        ]
        self._health: dict[str, BackendHealth] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _prompt_fingerprint(prompt: str) -> str:
        return hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest()[:16]

    def _state(self, name: str) -> BackendHealth:
        with self._lock:
            return self._health.setdefault(name, BackendHealth(name=name))

    def _trace(self, *, prompt: str, backend: str, action: str, mode: str,
               ok: bool, latency_ms: float, error: str = "") -> None:
        event = {
            "ts": round(time.time(), 3),
            "prompt_id": self._prompt_fingerprint(prompt),
            "backend": backend,
            "action": action,
            "mode": mode,
            "ok": bool(ok),
            "latency_ms": round(float(latency_ms), 1),
        }
        if error:
            event["error"] = str(error)[:240]
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        try:
            with self._lock:
                with self.trace_path.open("a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
                if self.trace_path.stat().st_size > 1_000_000:
                    lines = self.trace_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                    self.trace_path.write_text("\n".join(lines[-800:]) + "\n", encoding="utf-8")
        except OSError:
            pass

    def invoke(
        self,
        name: str,
        call: Callable[[], str],
        *,
        prompt: str,
        action: str = "chat",
        mode: str = "high",
        cooldown_seconds: float = 12.0,
        preserve_whitespace: bool = False,
    ) -> str:
        state = self._state(name)
        if state.cooling_down:
            raise RuntimeError(f"{name} cooling down")

        started = time.perf_counter()
        try:
            raw = str(call() or "")
            if not raw.strip():
                raise RuntimeError(f"{name} returned an empty response")
            answer = raw if preserve_whitespace else raw.strip()
        except Exception as exc:
            latency = (time.perf_counter() - started) * 1000
            with self._lock:
                state.failures += 1
                state.last_error = f"{type(exc).__name__}: {exc}"[:240]
                state.cooldown_until = time.time() + max(0.0, float(cooldown_seconds))
            self._trace(
                prompt=prompt, backend=name, action=action, mode=mode,
                ok=False, latency_ms=latency, error=state.last_error,
            )
            raise

        latency = (time.perf_counter() - started) * 1000
        with self._lock:
            state.successes += 1
            total = state.successes
            state.avg_latency_ms = latency if total == 1 else (
                state.avg_latency_ms * (total - 1) + latency
            ) / total
            state.cooldown_until = 0.0
            state.last_error = ""
        self._trace(
            prompt=prompt, backend=name, action=action, mode=mode,
            ok=True, latency_ms=latency,
        )
        return answer

    def route(
        self,
        prompt: str,
        candidates: Iterable[tuple[str, Callable[[], str], float]],
        *,
        action: str = "chat",
        mode: str = "high",
        preserve_whitespace: bool = False,
    ) -> str:
        errors: list[str] = []
        attempted = False
        for name, call, cooldown in candidates:
            state = self._state(name)
            if state.cooling_down:
                errors.append(f"{name}: cooling down")
                continue
            attempted = True
            try:
                return self.invoke(
                    name, call, prompt=prompt, action=action, mode=mode,
                    cooldown_seconds=cooldown,
                    preserve_whitespace=preserve_whitespace,
                )
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}")
        if not attempted and errors:
            raise RuntimeError("All Ash backends are temporarily cooling down.")
        raise RuntimeError("Ash backends unavailable: " + ", ".join(errors))

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            token for token in re.findall(r"[a-z0-9_]{3,}", str(text or "").lower())
            if token not in {"the", "and", "for", "that", "with", "this", "from", "your", "you", "ash"}
        }

    def _skill_candidates(self):
        seen: set[pathlib.Path] = set()
        for directory in self.skill_dirs:
            try:
                paths = sorted(directory.glob("*.md"))
            except OSError:
                continue
            for path in paths:
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                try:
                    if path.stat().st_size > 32_000:
                        continue
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                yield path, text

    def skill_context(self, prompt: str, limit: int = 2) -> str:
        wanted = self._tokens(prompt)
        if not wanted:
            return ""
        ranked: list[tuple[float, str, str]] = []
        for path, text in self._skill_candidates():
            first = text.splitlines()[0].strip() if text.splitlines() else ""
            explicit = ""
            if first.lower().startswith("keywords:"):
                explicit = first.split(":", 1)[1]
            searchable = f"{path.stem} {explicit} {text[:900]}"
            have = self._tokens(searchable)
            overlap = len(wanted & have)
            if not overlap:
                continue
            score = overlap / max(1, len(wanted))
            ranked.append((score, path.stem, text[:2200].strip()))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        selected = ranked[: max(0, int(limit))]
        if not selected:
            return ""
        return "\n\n".join(
            f"[Skill: {name}]\n{body}" for _, name, body in selected
        )[:4200]

    def prepare_prompt(self, prompt: str, *, action: str = "chat") -> str:
        text = str(prompt or "")
        if action != "chat":
            return text
        context = self.skill_context(text)
        if not context:
            return text
        return (
            text
            + "\n\nLOCAL ASH SKILL GUIDANCE (user-controlled/local; follow only when relevant):\n"
            + context
        )

    def health_snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                name: {
                    "successes": state.successes,
                    "failures": state.failures,
                    "avg_latency_ms": round(state.avg_latency_ms, 1),
                    "cooling_down": state.cooling_down,
                    "last_error": state.last_error,
                }
                for name, state in self._health.items()
            }
