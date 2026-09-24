from __future__ import annotations

import json
import os
import pathlib
import socket
import time
from typing import Any

import httpx

from ash_agent import AshPythonAgent


class AshRemoteWorker:
    def __init__(self) -> None:
        self.base = os.environ.get('ASH_SUPABASE_URL', '').rstrip('/')
        self.key = os.environ.get('ASH_SUPABASE_PUBLISHABLE_KEY', '')
        self.token = os.environ.get('ASH_ACCESS_TOKEN', '')
        self.device_name = os.environ.get('ASH_DEVICE_NAME', socket.gethostname() or 'Ash Desktop')
        self.workspace_root = pathlib.Path(os.environ.get('ASH_WORKSPACE_ROOT', str(pathlib.Path.home() / 'AshWorkspaces'))).expanduser().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(timeout=httpx.Timeout(45.0, connect=8.0))
        self.agent = AshPythonAgent()
        self.user_id = ''
        self.device_id = ''

    def headers(self, prefer: str | None = None) -> dict[str, str]:
        h = {'apikey': self.key, 'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
        if prefer:
            h['Prefer'] = prefer
        return h

    def validate(self) -> None:
        if not self.base or not self.key or not self.token:
            raise RuntimeError('ASH_SUPABASE_URL, ASH_SUPABASE_PUBLISHABLE_KEY and ASH_ACCESS_TOKEN are required.')
        r = self.client.get(f'{self.base}/auth/v1/user', headers=self.headers())
        r.raise_for_status()
        self.user_id = str(r.json().get('id') or '')
        if not self.user_id:
            raise RuntimeError('Could not resolve signed-in Ash user.')

    def rest(self, table: str, *, method: str = 'GET', params: dict[str, str] | None = None, body: Any = None, prefer: str | None = None):
        r = self.client.request(method, f'{self.base}/rest/v1/{table}', params=params, headers=self.headers(prefer), json=body)
        if r.status_code >= 400:
            raise RuntimeError(f'Supabase {table} returned HTTP {r.status_code}: {r.text[-500:]}')
        if not r.text:
            return None
        return r.json()

    def register_device(self) -> None:
        rows = self.rest('jarvis_devices', params={'user_id': f'eq.{self.user_id}', 'device_name': f'eq.{self.device_name}', 'select': '*', 'limit': '1'}) or []
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        payload = {
            'user_id': self.user_id,
            'device_name': self.device_name,
            'nickname': self.device_name,
            'platform': os.name,
            'app_version': 'ash-desktop-worker-2',
            'is_trusted': True,
            'last_seen_at': now,
            'capabilities': {'builder': True, 'local_ai': True, 'verified_builds': True, 'auto_repair': True},
        }
        if rows:
            self.device_id = str(rows[0]['id'])
            self.rest('jarvis_devices', method='PATCH', params={'id': f'eq.{self.device_id}'}, body=payload)
        else:
            created = self.rest('jarvis_devices', method='POST', body=payload, prefer='return=representation') or []
            if not created:
                raise RuntimeError('Could not register Ash desktop worker.')
            self.device_id = str(created[0]['id'])

    def heartbeat(self) -> None:
        if not self.device_id:
            return
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        self.rest('jarvis_devices', method='PATCH', params={'id': f'eq.{self.device_id}'}, body={'last_seen_at': now})

    def queued_jobs(self) -> list[dict[str, Any]]:
        rows = self.rest('jarvis_remote_jobs', params={
            'status': 'eq.queued',
            'or': f'(target_device_id.is.null,target_device_id.eq.{self.device_id})',
            'order': 'created_at.asc',
            'limit': '4',
            'select': '*',
        })
        return list(rows or [])

    def claim(self, job_id: str) -> dict[str, Any] | None:
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        rows = self.rest('jarvis_remote_jobs', method='PATCH', params={'id': f'eq.{job_id}', 'status': 'eq.queued'}, body={
            'status': 'running',
            'claimed_at': now,
            'updated_at': now,
        }, prefer='return=representation') or []
        return rows[0] if rows else None

    def finish(self, job_id: str, *, ok: bool, result: dict[str, Any] | None = None, error: str = '') -> None:
        now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        self.rest('jarvis_remote_jobs', method='PATCH', params={'id': f'eq.{job_id}'}, body={
            'status': 'completed' if ok else 'failed',
            'result': result or {},
            'error': error[:1200],
            'completed_at': now,
            'updated_at': now,
        })

    def process(self, job: dict[str, Any]) -> None:
        job_id = str(job['id'])
        payload = job.get('payload') or {}
        prompt = str(payload.get('prompt') or '').strip()
        kind = str(job.get('kind') or payload.get('kind') or 'mission')
        if not prompt:
            self.finish(job_id, ok=False, error='Job contained no prompt.')
            return

        try:
            if kind in {'builder', 'website', 'app_builder'} or payload.get('builder') is True:
                workspace = self.workspace_root / job_id
                built = self.agent.build_fullstack(prompt, str(workspace))
                result = {
                    'summary': built.output,
                    'workspace': str(workspace),
                    'generated_files': built.details.get('generated_files', []),
                    'repaired_files': built.details.get('repaired_files', []),
                    'evidence': built.details.get('evidence', []),
                    'completed_by': self.device_name,
                    'builder': True,
                }
                self.finish(job_id, ok=built.ok, result=result, error='' if built.ok else built.output)
            else:
                answer = self.agent.think(prompt, str(job.get('mode') or 'high'))
                self.finish(job_id, ok=True, result={'summary': answer, 'completed_by': self.device_name})
        except Exception as exc:
            self.finish(job_id, ok=False, error=str(exc))

    def run_forever(self) -> None:
        self.validate()
        self.register_device()
        print(json.dumps({'type': 'ready', 'device_id': self.device_id, 'device_name': self.device_name, 'workspace_root': str(self.workspace_root)}), flush=True)
        last_heartbeat = 0.0
        while True:
            now = time.time()
            if now - last_heartbeat >= 30:
                self.heartbeat()
                last_heartbeat = now
            for candidate in self.queued_jobs():
                claimed = self.claim(str(candidate['id']))
                if claimed:
                    self.process(claimed)
            time.sleep(3)


if __name__ == '__main__':
    AshRemoteWorker().run_forever()
