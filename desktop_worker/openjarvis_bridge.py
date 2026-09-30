from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenJarvisProfile:
    name: str
    agent: str
    tools: tuple[str, ...]
    description: str
    side_effects: bool = False


class OpenJarvisBackend:
    """Full optional OpenJarvis specialist pack behind Ash's safety boundary.

    OpenJarvis is used as a specialist runtime, not as Ash's owner. Ash keeps
    identity, voice, device pairing, confirmation gates, cloud research, memory
    and computer-control policy. The bridge exposes multiple OpenJarvis agent
    styles while deliberately separating read-oriented profiles from profiles
    that can execute code or mutate state.
    """

    PROFILES: dict[str, OpenJarvisProfile] = {
        "orchestrator": OpenJarvisProfile(
            "orchestrator",
            "orchestrator",
            ("calculator", "think", "web_search", "file_read", "retrieval"),
            "General multi-step specialist with safe read-oriented tools.",
        ),
        "research": OpenJarvisProfile(
            "research",
            "deep_research",
            ("web_search", "retrieval", "think", "file_read"),
            "Deep research specialist for multi-source investigation.",
        ),
        "react": OpenJarvisProfile(
            "react",
            "native_react",
            ("calculator", "think", "web_search", "file_read", "retrieval"),
            "ReAct-style specialist for tool-heavy reasoning and debugging.",
        ),
        "long_context": OpenJarvisProfile(
            "long_context",
            "rlm",
            ("think", "retrieval", "file_read"),
            "Recursive long-context specialist for large documents and decomposition.",
        ),
        "simple": OpenJarvisProfile(
            "simple",
            "simple",
            (),
            "Low-overhead local specialist for direct single-turn work.",
        ),
        "code": OpenJarvisProfile(
            "code",
            "native_openhands",
            ("calculator", "think", "file_read", "code_interpreter"),
            "CodeAct specialist. This profile can execute code and is confirmation-gated by Ash.",
            side_effects=True,
        ),
    }

    def __init__(self) -> None:
        setting = os.environ.get("ASH_OPENJARVIS_ENABLED", "auto").strip().lower()
        self.enabled = setting not in {"0", "false", "no", "off"}
        self._jarvis = None
        self._lock = threading.RLock()
        self._error = ""
        self._last_profile = ""

    @property
    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            import openjarvis  # noqa: F401
            return True
        except Exception:
            return False

    def _version(self) -> str | None:
        if not self.available:
            return None
        try:
            import openjarvis
            return str(getattr(openjarvis, "__version__", "") or "") or None
        except Exception:
            return None

    def capabilities(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "profiles": {
                name: {
                    "agent": profile.agent,
                    "tools": list(profile.tools),
                    "description": profile.description,
                    "side_effects": profile.side_effects,
                }
                for name, profile in self.PROFILES.items()
            },
            "supports_memory": self.available,
            "supports_streaming": self.available,
            "supports_scheduler": self.available,
            "supports_skills": self.available,
            "supports_a2a": self.available,
        }

    def status(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "available": self.available,
            "version": self._version(),
            "last_profile": self._last_profile,
            "last_error": self._error,
            "capabilities": self.capabilities() if self.available else {"available": False},
        }

    def _get(self):
        if self._jarvis is not None:
            return self._jarvis
        if not self.available:
            raise RuntimeError("OpenJarvis specialist is not installed.")
        from openjarvis import Jarvis
        self._jarvis = Jarvis()
        return self._jarvis

    @classmethod
    def profile(cls, name: str | None) -> OpenJarvisProfile:
        key = str(name or "orchestrator").strip().lower().replace("-", "_")
        aliases = {
            "deep_research": "research",
            "researcher": "research",
            "native_react": "react",
            "rlm": "long_context",
            "long": "long_context",
            "native_openhands": "code",
            "coding": "code",
            "developer": "code",
        }
        return cls.PROFILES.get(aliases.get(key, key), cls.PROFILES["orchestrator"])

    def ask(self, prompt: str, profile: str = "orchestrator", *, allow_side_effects: bool = False) -> str:
        selected = self.profile(profile)
        if selected.side_effects and not allow_side_effects:
            raise PermissionError(
                "This OpenJarvis profile can execute code and requires explicit Ash confirmation."
            )
        with self._lock:
            jarvis = self._get()
            try:
                try:
                    answer = jarvis.ask(
                        prompt,
                        agent=selected.agent,
                        tools=list(selected.tools),
                        context=True,
                    )
                except Exception:
                    # A model/engine may not support every advanced agent. Fall
                    # back to the safest general OpenJarvis agent before giving up.
                    if selected.name != "orchestrator":
                        fallback = self.PROFILES["orchestrator"]
                        answer = jarvis.ask(
                            prompt,
                            agent=fallback.agent,
                            tools=list(fallback.tools),
                            context=True,
                        )
                    else:
                        answer = jarvis.ask(prompt, agent="orchestrator", context=True)
                text = str(answer or "").strip()
                if not text:
                    raise RuntimeError("OpenJarvis returned no answer.")
                self._last_profile = selected.name
                self._error = ""
                return text
            except Exception as exc:
                self._error = f"{type(exc).__name__}: {exc}"[:300]
                raise

    def memory_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        with self._lock:
            jarvis = self._get()
            try:
                results = jarvis.memory.search(str(query or ""), top_k=max(1, min(12, int(top_k))))
                return list(results or [])
            except Exception as exc:
                self._error = f"{type(exc).__name__}: {exc}"[:300]
                raise

    def memory_index(self, path: str) -> dict[str, Any]:
        with self._lock:
            jarvis = self._get()
            try:
                result = jarvis.memory.index(str(path))
                return dict(result or {})
            except Exception as exc:
                self._error = f"{type(exc).__name__}: {exc}"[:300]
                raise

    def close(self) -> None:
        with self._lock:
            jarvis, self._jarvis = self._jarvis, None
            if jarvis is not None:
                try:
                    jarvis.close()
                except Exception:
                    pass
