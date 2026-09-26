from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import socket
import time
from typing import Any

import httpx

from ash_agent import AshPythonAgent
from computer_control import AshComputerController, ComputerControlUnavailable

DEFAULT_LINK_URL = "https://ftsomveafuskrutqzsvs.supabase.co/functions/v1/ash-device-link"


class AshRemoteWorker:
    def __init__(self, pair_code: str = "") -> None:
        self.base = os.environ.get("ASH_SUPABASE_URL", "").rstrip("/")
        self.key = os.environ.get("ASH_SUPABASE_PUBLISHABLE_KEY", "")
        self.token = os.environ.get("ASH_ACCESS_TOKEN", "")
        self.link_url = os.environ.get("ASH_DEVICE_LINK_URL", "") or (f"{self.base}/functions/v1/ash-device-link" if self.base else DEFAULT_LINK_URL)
        self.device_name = os.environ.get("ASH_DEVICE_NAME", socket.gethostname() or "Ash Desktop")
        self.workspace_root = pathlib.Path(os.environ.get("ASH_WORKSPACE_ROOT", str(pathlib.Path.home() / "AshWorkspaces"))).expanduser().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.config_path = pathlib.Path(os.environ.get("ASH_DEVICE_CONFIG", str(pathlib.Path.home() / ".ash" / "device.json"))).expanduser()
        self.preferences_path = pathlib.Path(os.environ.get("ASH_PREFERENCES_FILE", str(pathlib.Path.home() / ".ash" / "preferences.json"))).expanduser()
        self.client = httpx.Client(timeout=httpx.Timeout(45.0, connect=8.0))
        self.agent = AshPythonAgent()
        self.user_id = ""
        self.device_id = ""
        self.device_secret = ""
        self.pair_code = pair_code or os.environ.get("ASH_PAIR_CODE", "")
        self._load_device_config()
        if hasattr(self.agent, "set_device_credentials"):
            self.agent.set_device_credentials(self.device_id, self.device_secret)

    def _load_device_config(self) -> None:
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            return
        self.device_id = str(data.get("device_id") or "")
        self.device_secret = str(data.get("device_secret") or "")
        self.user_id = str(data.get("user_id") or "")

    def _save_device_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps({
            "device_id": self.device_id,
            "device_secret": self.device_secret,
            "user_id": self.user_id,
            "link_url": self.link_url,
            "device_name": self.device_name,
        }, indent=2), encoding="utf-8")

    def capabilities(self) -> dict[str, bool]:
        return {
            "builder": True,
            "local_ai": True,
            "offline_brain": True,
            "verified_builds": True,
            "auto_repair": True,
            "voice_runtime": True,
            "computer_control": os.environ.get("ASH_COMPUTER_CONTROL", "").strip().lower() in {"1", "true", "yes", "on"},
            "screen_vision": True,
        }

    def broker(self, action: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.device_id and self.device_secret:
            headers["X-Ash-Device-ID"] = self.device_id
            headers["X-Ash-Device-Secret"] = self.device_secret
        payload = {"action": action, **(body or {})}
        r = self.client.post(self.link_url, headers=headers, json=payload)
        if r.status_code >= 400:
            try:
                detail = r.json().get("error") or r.text
            except Exception:
                detail = r.text
            raise RuntimeError(f"Ash device link returned HTTP {r.status_code}: {detail}")
        return r.json() if r.text else {}

    def pair(self, code: str) -> None:
        r = self.client.post(self.link_url, headers={"Content-Type": "application/json"}, json={
            "action": "claim_pairing",
            "code": code,
            "device_name": self.device_name,
            "platform": platform.system().lower() or os.name,
            "app_version": "ash-desktop-worker-3",
            "capabilities": self.capabilities(),
        })
        if r.status_code >= 400:
            try:
                detail = r.json().get("error") or r.text
            except Exception:
                detail = r.text
            raise RuntimeError(f"Could not link this computer: {detail}")
        data = r.json()
        self.device_id = str(data.get("device_id") or "")
        self.device_secret = str(data.get("device_secret") or "")
        self.user_id = str(data.get("user_id") or "")
        if not self.device_id or not self.device_secret:
            raise RuntimeError("Ash did not return a device credential.")
        self._save_device_config()
        if hasattr(self.agent, "set_device_credentials"):
            self.agent.set_device_credentials(self.device_id, self.device_secret)

    def headers(self, prefer: str | None = None) -> dict[str, str]:
        h = {"apikey": self.key, "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        if prefer:
            h["Prefer"] = prefer
        return h

    def validate(self) -> None:
        if self.pair_code:
            self.pair(self.pair_code)
            self.pair_code = ""
        if self.device_id and self.device_secret:
            self.broker("heartbeat")
            return
        if not self.base or not self.key or not self.token:
            raise RuntimeError("This computer is not linked. In Ash open Preferences > Linked computers > Link a computer, then run remote_worker.py --pair CODE.")
        r = self.client.get(f"{self.base}/auth/v1/user", headers=self.headers())
        r.raise_for_status()
        self.user_id = str(r.json().get("id") or "")
        if not self.user_id:
            raise RuntimeError("Could not resolve signed-in Ash user.")

    def rest(self, table: str, *, method: str = "GET", params: dict[str, str] | None = None, body: Any = None, prefer: str | None = None):
        r = self.client.request(method, f"{self.base}/rest/v1/{table}", params=params, headers=self.headers(prefer), json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase {table} returned HTTP {r.status_code}: {r.text[-500:]}")
        if not r.text:
            return None
        return r.json()

    def register_device(self) -> None:
        if self.device_id and self.device_secret:
            return
        rows = self.rest("jarvis_devices", params={"user_id": f"eq.{self.user_id}", "device_name": f"eq.{self.device_name}", "select": "*", "limit": "1"}) or []
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload = {
            "user_id": self.user_id,
            "device_name": self.device_name,
            "nickname": self.device_name,
            "platform": os.name,
            "app_version": "ash-desktop-worker-2",
            "is_trusted": True,
            "last_seen_at": now,
            "capabilities": self.capabilities(),
        }
        if rows:
            self.device_id = str(rows[0]["id"])
            self.rest("jarvis_devices", method="PATCH", params={"id": f"eq.{self.device_id}"}, body=payload)
        else:
            created = self.rest("jarvis_devices", method="POST", body=payload, prefer="return=representation") or []
            if not created:
                raise RuntimeError("Could not register Ash desktop worker.")
            self.device_id = str(created[0]["id"])

    def sync_preferences(self) -> None:
        if not (self.device_id and self.device_secret):
            return
        data = self.broker("preferences")
        payload = {
            "assistant_name": str(data.get("assistant_name") or "Ash"),
            "wake_word": str(data.get("wake_word") or data.get("assistant_name") or "Ash"),
            "wake_aliases": [str(x).strip() for x in (data.get("wake_aliases") or []) if str(x).strip()],
            "updated_at": data.get("updated_at"),
        }
        self.preferences_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.preferences_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.preferences_path)

    def heartbeat(self) -> None:
        if not self.device_id:
            return
        if self.device_secret:
            self.broker("heartbeat")
            try:
                self.sync_preferences()
            except Exception:
                pass
            return
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.rest("jarvis_devices", method="PATCH", params={"id": f"eq.{self.device_id}"}, body={"last_seen_at": now})

    def queued_jobs(self) -> list[dict[str, Any]]:
        if self.device_secret:
            return list(self.broker("jobs").get("jobs") or [])
        rows = self.rest("jarvis_remote_jobs", params={
            "status": "eq.queued",
            "or": f"(target_device_id.is.null,target_device_id.eq.{self.device_id})",
            "order": "created_at.asc",
            "limit": "4",
            "select": "*",
        })
        return list(rows or [])

    def claim(self, job_id: str) -> dict[str, Any] | None:
        if self.device_secret:
            return self.broker("claim_job", {"job_id": job_id}).get("job")
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rows = self.rest("jarvis_remote_jobs", method="PATCH", params={"id": f"eq.{job_id}", "status": "eq.queued"}, body={
            "status": "running",
            "claimed_at": now,
            "updated_at": now,
        }, prefer="return=representation") or []
        return rows[0] if rows else None

    def finish(self, job_id: str, *, ok: bool, result: dict[str, Any] | None = None, error: str = "") -> None:
        if self.device_secret:
            self.broker("finish_job", {"job_id": job_id, "ok": ok, "result": result or {}, "error": error[:1200]})
            return
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.rest("jarvis_remote_jobs", method="PATCH", params={"id": f"eq.{job_id}"}, body={
            "status": "completed" if ok else "failed",
            "result": result or {},
            "error": error[:1200],
            "completed_at": now,
            "updated_at": now,
        })

    def process(self, job: dict[str, Any]) -> None:
        job_id = str(job["id"])
        payload = job.get("payload") or {}
        prompt = str(payload.get("prompt") or "").strip()
        kind = str(job.get("kind") or payload.get("kind") or "mission")
        if job.get("requires_confirmation") is True:
            # Modern paired workers are held by ash-device-link before claim. This
            # protects the legacy token path too, so a confirmation-required job
            # can never execute merely because an older worker received it.
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if not self.device_secret:
                self.rest("jarvis_remote_jobs", method="PATCH", params={"id": f"eq.{job_id}"}, body={
                    "status": "waiting_for_confirmation",
                    "updated_at": now,
                })
            return
        if not prompt:
            self.finish(job_id, ok=False, error="Job contained no prompt.")
            return
        try:
            if kind in {"builder", "website", "app_builder"} or payload.get("builder") is True:
                workspace = self.workspace_root / job_id
                built = self.agent.build_fullstack(prompt, str(workspace))
                result = {
                    "summary": built.output,
                    "workspace": str(workspace),
                    "generated_files": built.details.get("generated_files", []),
                    "repaired_files": built.details.get("repaired_files", []),
                    "evidence": built.details.get("evidence", []),
                    "completed_by": self.device_name,
                    "builder": True,
                }
                self.finish(job_id, ok=built.ok, result=result, error="" if built.ok else built.output)
            elif kind in {"computer_control", "computer", "desktop_control"} or payload.get("computer_control") is True:
                controller = AshComputerController(self.agent)
                outcome = controller.run_goal(prompt)
                self.finish(
                    job_id,
                    ok=bool(outcome.get("ok")),
                    result={
                        "summary": outcome.get("summary") or "Computer-control run finished.",
                        "steps": outcome.get("steps"),
                        "trace": outcome.get("trace", []),
                        "completed_by": self.device_name,
                        "computer_control": True,
                    },
                    error="" if outcome.get("ok") else str(outcome.get("summary") or "Computer task was not completed."),
                )
            elif kind == "chat_fallback" or payload.get("rescue") is True:
                mode = str(job.get("mode") or "high")
                try:
                    answer = self.agent._local(prompt)
                    backend = "ollama"
                except Exception:
                    answer = self.agent.offline.respond(prompt, mode=mode)
                    backend = self.agent.offline.status().backend
                self.finish(job_id, ok=True, result={"summary": answer, "completed_by": self.device_name, "rescue": True, "backend": backend})
            else:
                answer = self.agent.think(prompt, str(job.get("mode") or "high"))
                self.finish(job_id, ok=True, result={"summary": answer, "completed_by": self.device_name})
        except Exception as exc:
            self.finish(job_id, ok=False, error=str(exc))

    def run_forever(self) -> None:
        self.validate()
        self.register_device()
        print(json.dumps({"type": "ready", "device_id": self.device_id, "device_name": self.device_name, "workspace_root": str(self.workspace_root), "paired": bool(self.device_secret)}), flush=True)
        last_heartbeat = 0.0
        while True:
            now = time.time()
            if now - last_heartbeat >= 30:
                self.heartbeat()
                last_heartbeat = now
            for candidate in self.queued_jobs():
                claimed = self.claim(str(candidate["id"]))
                if claimed:
                    self.process(claimed)
            time.sleep(3)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ash desktop worker")
    parser.add_argument("--pair", default="", help="One-time pairing code generated inside Ash")
    parser.add_argument("--name", default="", help="Optional device name shown in Ash")
    args = parser.parse_args()
    if args.name:
        os.environ["ASH_DEVICE_NAME"] = args.name
    AshRemoteWorker(pair_code=args.pair).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
