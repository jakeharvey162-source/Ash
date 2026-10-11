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
            if len(tasks) >= 100:
                raise ValueError("Local schedules are limited to 100 tasks.")
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

    def claim_due(self, now: float | None = None, lease_seconds: int = 3600) -> list[dict[str, Any]]:
        """Persist a lease before an autonomous run to avoid repeated same-cycle execution.

        A crashed process may retry after the lease expires. Scheduled prompts
        therefore must remain read-oriented and tools needing confirmation are blocked.
        """
        current = float(now if now is not None else time.time())
        if not 60 <= int(lease_seconds) <= 86400:
            raise ValueError("Lease must be between 1 minute and 24 hours.")
        with self._lock:
            tasks = self._load()
            claimed = []
            for task in tasks:
                if len(claimed) >= 4:
                    break
                if task.get("enabled") is not True:
                    continue
                if float(task.get("next_run") or 0) > current:
                    continue
                if float(task.get("lease_until") or 0) > current:
                    continue
                task["lease_until"] = current + int(lease_seconds)
                task["lease_id"] = str(uuid.uuid4())
                task["last_attempt"] = current
                claimed.append(dict(task))
            if claimed:
                self._save(tasks)
            return claimed

    def pause(self, task_id: str) -> bool:
        """Disable a task until it is reviewed and explicitly resumed."""
        with self._lock:
            tasks = self._load()
            match = next((t for t in tasks if str(t.get("id")) == str(task_id)), None)
            if match is None:
                return False
            match["enabled"] = False
            match["lease_until"] = 0
            match["lease_id"] = ""
            self._save(tasks)
            return True

    def resume(self, task_id: str) -> bool:
        with self._lock:
            tasks = self._load()
            match = next((t for t in tasks if str(t.get("id")) == str(task_id)), None)
            if match is None:
                return False
            match["enabled"] = True
            match["lease_until"] = 0
            match["lease_id"] = ""
            match["next_run"] = time.time() + max(60, int(match.get("interval_seconds") or 60))
            self._save(tasks)
            return True

    def complete(self, task_id: str, *, ok: bool, summary: str = "", error: str = "",
                 lease_id: str | None = None, needs_confirmation: bool = False) -> None:
        now = time.time()
        with self._lock:
            tasks = self._load()
            for task in tasks:
                if str(task.get("id")) != str(task_id):
                    continue
                # Ignore an old worker's completion after the task was re-claimed.
                if lease_id is not None and str(task.get("lease_id") or "") != lease_id:
                    return
                interval = max(60, int(task.get("interval_seconds") or 60))
                task["last_run"] = now
                task["last_error"] = "" if ok else str(error or summary)[:500]
                task["next_run"] = now + interval
                task["lease_until"] = 0
                task["lease_id"] = ""
                if needs_confirmation:
                    task["enabled"] = False
                    task["last_error"] = "Paused: an action requires user confirmation."
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
