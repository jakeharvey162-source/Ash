from __future__ import annotations

import json
import pathlib
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class LocalTask:
    id: str
    name: str
    prompt: str
    interval_seconds: int
    next_run: float
    enabled: bool = True
    created_at: float = 0.0
    last_run: float | None = None
    last_error: str = ""


class LocalScheduler:
    """Tiny offline scheduler for Ash desktop.

    Cloud automations remain the primary cross-device scheduler. This store gives
    the downloaded desktop companion a local-first recurring task path when the
    cloud is unavailable.
    """

    def __init__(self, home: pathlib.Path | None = None) -> None:
        root = home or pathlib.Path.home() / ".ash"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "local-schedules.json"
        self.results_path = root / "local-schedule-results.jsonl"
        self._lock = threading.Lock()

    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return list(data.get("tasks") or []) if isinstance(data, dict) else []
        except Exception:
            return []

    def _save(self, tasks: list[dict[str, Any]]) -> None:
        payload = {"version": 1, "tasks": tasks[:100]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._load()

    def create(self, name: str, prompt: str, interval_minutes: int) -> dict[str, Any]:
        interval = int(interval_minutes)
        if interval < 1 or interval > 43_200:
            raise ValueError("Local schedule interval must be between 1 minute and 30 days.")
        clean_prompt = str(prompt or "").strip()
        if not clean_prompt:
            raise ValueError("Scheduled task prompt is required.")
        now = time.time()
        task = LocalTask(
            id=str(uuid.uuid4()),
            name=(str(name or "Ash task").strip() or "Ash task")[:80],
            prompt=clean_prompt[:8000],
            interval_seconds=interval * 60,
            next_run=now + interval * 60,
            enabled=True,
            created_at=now,
        )
        with self._lock:
            tasks = self._load()
            tasks.append(asdict(task))
            self._save(tasks)
        return asdict(task)

    def cancel(self, task_id: str) -> bool:
        wanted = str(task_id or "")
        with self._lock:
            tasks = self._load()
            kept = [t for t in tasks if str(t.get("id")) != wanted]
            changed = len(kept) != len(tasks)
            if changed:
                self._save(kept)
            return changed

    def due(self, now: float | None = None) -> list[dict[str, Any]]:
        current = float(now if now is not None else time.time())
        with self._lock:
            tasks = self._load()
            return [
                t for t in tasks
                if t.get("enabled") is True and float(t.get("next_run") or 0) <= current
            ][:4]

    def complete(self, task_id: str, *, ok: bool, summary: str = "", error: str = "") -> None:
        now = time.time()
        with self._lock:
            tasks = self._load()
            for task in tasks:
                if str(task.get("id")) != str(task_id):
                    continue
                interval = max(60, int(task.get("interval_seconds") or 60))
                task["last_run"] = now
                task["last_error"] = "" if ok else str(error or summary)[:500]
                task["next_run"] = now + interval
                break
            self._save(tasks)
            record = {
                "ts": now,
                "task_id": str(task_id),
                "ok": bool(ok),
                "summary": str(summary)[:1200],
                "error": str(error)[:500],
            }
            try:
                with self.results_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                pass
