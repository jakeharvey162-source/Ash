from __future__ import annotations

import os
import threading


class OpenJarvisBackend:
    """Optional bridge to the Apache-2.0 OpenJarvis runtime.

    Ash keeps its own gateway, permissions and UX. When OpenJarvis is installed,
    this bridge makes its local engine/agent stack available as another specialist
    fallback instead of replacing Ash.
    """

    def __init__(self) -> None:
        setting = os.environ.get("ASH_OPENJARVIS_ENABLED", "auto").strip().lower()
        self.enabled = setting not in {"0", "false", "no", "off"}
        self._jarvis = None
        self._lock = threading.Lock()
        self._error = ""

    @property
    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            import openjarvis  # noqa: F401
            return True
        except Exception:
            return False

    def status(self) -> dict[str, object]:
        version = None
        if self.available:
            try:
                import openjarvis
                version = getattr(openjarvis, "__version__", None)
            except Exception:
                pass
        return {
            "enabled": self.enabled,
            "available": self.available,
            "version": version,
            "last_error": self._error,
        }

    def _get(self):
        if self._jarvis is not None:
            return self._jarvis
        if not self.available:
            raise RuntimeError("OpenJarvis specialist is not installed.")
        from openjarvis import Jarvis
        self._jarvis = Jarvis()
        return self._jarvis

    def ask(self, prompt: str) -> str:
        with self._lock:
            jarvis = self._get()
            try:
                # Keep the tool surface deliberately read-oriented here. Ash's own
                # confirmation layer remains responsible for writes and computer control.
                try:
                    answer = jarvis.ask(
                        prompt,
                        agent="orchestrator",
                        tools=["calculator", "think", "web_search", "file_read", "memory_retrieve"],
                    )
                except Exception:
                    answer = jarvis.ask(prompt, agent="orchestrator")
                text = str(answer or "").strip()
                if not text:
                    raise RuntimeError("OpenJarvis returned no answer.")
                self._error = ""
                return text
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
