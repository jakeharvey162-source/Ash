"""Opt-in owner-only telephone alerts for decisions waiting in Ash.

This module NEVER approves a job, authorizes a payment or sends a trading order.
A carrier number and credentials must be configured explicitly. No secret is logged.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import pathlib
import re
import tempfile
import threading
import urllib.parse
import urllib.request
import xml.sax.saxutils

_ALLOWED = {
    "approval_needed": "Ash needs your approval for an action. Sign in to Ash and open Activity to review it.",
    "job_failed": "An Ash automation encountered a problem. Sign in to Ash and check Activity.",
}
_LOCK = threading.Lock()
_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")
_SID = re.compile(r"^AC[a-fA-F0-9]{32}$")


class OwnerCallAlerts:
    def __init__(self, environ=None, ledger_path=None, opener=None):
        self.env = dict(os.environ if environ is None else environ)
        self.path = pathlib.Path(ledger_path or pathlib.Path.home() / ".ash" / "call-alert-ledger.json")
        self.opener = opener or urllib.request.urlopen

    def configured(self):
        return (self.env.get("ASH_CALL_ALERTS_ENABLED") == "1"
                and bool(_E164.fullmatch(self.env.get("ASH_OWNER_PHONE", "")))
                and bool(_E164.fullmatch(self.env.get("TWILIO_FROM_NUMBER", "")))
                and bool(_SID.fullmatch(self.env.get("TWILIO_ACCOUNT_SID", "")))
                and bool(self.env.get("TWILIO_AUTH_TOKEN", "")))

    def _read(self):
        try:
            obj = json.loads(self.path.read_text(encoding="utf-8"))
            return obj if isinstance(obj, dict) else {}
        except (FileNotFoundError, ValueError, OSError):
            return {}

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as f:
                name = f.name
                json.dump(data, f, separators=(",", ":"))
            os.replace(name, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def alert(self, *, job_id: str, category: str = "approval_needed"):
        if category not in _ALLOWED:
            raise ValueError("Unsupported owner alert.")
        if not self.configured():
            return {"sent": False, "reason": "not_configured"}
        job = str(job_id).strip()
        if not 1 <= len(job) <= 120 or not re.fullmatch(r"[a-zA-Z0-9_.:-]+", job):
            raise ValueError("Invalid job identifier.")
        today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        key = today + ":" + category + ":" + job
        try:
            limit = max(1, min(3, int(self.env.get("ASH_CALL_ALERT_MAX_DAILY", "2"))))
        except ValueError:
            limit = 2
        with _LOCK:
            state = self._read()
            attempts = {k: v for k, v in state.items() if k.startswith(today + ":")}
            if key in attempts:
                return {"sent": False, "reason": "already_attempted"}
            if len(attempts) >= limit:
                return {"sent": False, "reason": "daily_limit"}
            # Persist BEFORE trying the paid call: repeated worker attempts cannot spam.
            attempts[key] = "attempted"
            self._write(attempts)

        sid = self.env["TWILIO_ACCOUNT_SID"]
        auth = base64.b64encode((sid+":"+self.env["TWILIO_AUTH_TOKEN"]).encode()).decode()
        words = xml.sax.saxutils.escape(_ALLOWED[category])
        twiml = '<Response><Say voice="alice">'+words+'</Say></Response>'
        body = urllib.parse.urlencode({
            "To": self.env["ASH_OWNER_PHONE"],
            "From": self.env["TWILIO_FROM_NUMBER"],
            "Twiml": twiml,
        }).encode()
        request = urllib.request.Request(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
            data=body, method="POST",
            headers={"Authorization":"Basic "+auth,"Content-Type":"application/x-www-form-urlencoded"},
        )
        try:
            with self.opener(request, timeout=12) as resp:
                if int(getattr(resp, "status", 0)) not in (200, 201):
                    return {"sent": False, "reason": "carrier_failed"}
                return {"sent": True, "reason": "carrier_accepted"}
        except Exception:
            # Do not leak response bodies, keys, phone numbers or provider errors.
            return {"sent": False, "reason": "carrier_unavailable"}
