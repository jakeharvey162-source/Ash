"""Free, opt-in owner notifications through ntfy.sh.

Ash's desktop worker uses these only to tell its owner to review Activity.
Unsecured ntfy topics can be read by anyone who knows the topic. Publish only
generic fixed messages, use a long unguessable private topic, and never send
customer data, account balances, job IDs, passwords or trade details.
No paid phone calls, trade orders or approvals are performed here.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import tempfile
import threading
import urllib.request
from typing import Any

_MESSAGES = {
    "approval_needed": ("Ash needs your decision", "An Ash action is waiting for your approval. Open your Ash Activity page and sign in."),
    "website_ready": ("Customer website ready to review", "Ash finished a website build. Please review the verified result in your Ash Business Desk before delivery."),
    "job_failed": ("Ash needs attention", "An Ash task needs your attention. Open Ash Activity and review the result."),
    "test": ("Ash notifications are ready", "This is a test notification from Ash. No approval or action is required."),
}
_TOPIC_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{32,80}$")
_LOCK = threading.Lock()
_URL = "https://ntfy.sh/"
_ACTION = "https://ash-f4.vercel.app/"


class FreeOwnerAlerts:
    """Uses a free push topic; OFF until owner opts in on their own desktop."""

    def __init__(self, environ=None, ledger_path=None, opener=None):
        self.env = dict(os.environ if environ is None else environ)
        self.path = pathlib.Path(ledger_path or pathlib.Path.home() / ".ash" / "push-alert-ledger.json")
        self.opener = opener or urllib.request.urlopen

    def configured(self) -> bool:
        topic = str(self.env.get("ASH_NTFY_TOPIC", ""))
        return (self.env.get("ASH_PUSH_ENABLED") == "1"
                and bool(_TOPIC_PATTERN.fullmatch(topic))
                and len(set(topic)) >= 12)

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            return {}

    def _write(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
                name = handle.name
                json.dump(state, handle, separators=(",", ":"))
            os.replace(name, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def alert(self, *, job_id: str, category: str = "approval_needed") -> dict[str, Any]:
        if category not in _MESSAGES:
            raise ValueError("Unsupported owner notification category.")
        if not self.configured():
            return {"sent": False, "reason": "not_configured"}
        job = str(job_id or "").strip()
        if not 1 <= len(job) <= 120 or not re.fullmatch(r"[a-zA-Z0-9_.:-]+", job):
            raise ValueError("Invalid job identifier.")
        today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        key = today + ":" + category + ":" + job
        try:
            max_daily = min(30, max(1, int(self.env.get("ASH_PUSH_MAX_DAILY", "12"))))
        except ValueError:
            max_daily = 12

        with _LOCK:
            items = {k: v for k, v in self._read().items() if k.startswith(today + ":")}
            if key in items:
                return {"sent": False, "reason": "already_attempted"}
            if len(items) >= max_daily:
                return {"sent": False, "reason": "daily_limit"}
            # Mark attempted before external I/O to avoid duplicate sends on retries.
            items[key] = "attempted"
            self._write(items)

        title, message = _MESSAGES[category]
        request = urllib.request.Request(
            _URL + self.env["ASH_NTFY_TOPIC"],
            data=message.encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "Title": title,
                "Priority": "high" if category == "approval_needed" else "default",
                "Click": _ACTION,
                "Cache": "no",
            },
        )
        try:
            with self.opener(request, timeout=12) as response:
                if int(getattr(response, "status", 0)) not in (200, 201, 202):
                    return {"sent": False, "reason": "provider_error"}
            return {"sent": True, "reason": "notification_accepted"}
        except Exception:
            return {"sent": False, "reason": "network_unavailable"}
