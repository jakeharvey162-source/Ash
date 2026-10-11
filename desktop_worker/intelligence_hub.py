"""Read-only intelligence connectors for the locally installed Ash desktop worker.

This does not execute security scanners, launch remote shells, discover third-party
credentials, or offer a hosted attack interface. Network access is only to the
operator-configured Wazuh manager. Other tools require explicit report exports.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

CATALOG = (
    {"id": "gods-eye-view", "kind": "external-visualization", "url": "https://github.com/bilawalsidhu/gods-eye-view", "mode": "link-only"},
    {"id": "shadowbroker", "kind": "external-osint", "url": "https://github.com/BigBodyCobain/Shadowbroker", "mode": "link-only"},
    {"id": "spiderfoot", "kind": "authorized-osint", "url": "https://github.com/smicallef/spiderfoot", "mode": "local-export"},
    {"id": "wazuh", "kind": "defensive-monitoring", "url": "https://github.com/wazuh/wazuh", "mode": "read-only-api"},
    {"id": "strix", "kind": "authorized-security-testing", "url": "https://github.com/usestrix/strix", "mode": "local-report-only"},
    {"id": "superpowers", "kind": "development-methodology", "url": "https://github.com/obra/superpowers", "mode": "reference-only"},
)
MAX_REPORT_BYTES = 2_000_000

def catalog():
    """These statuses describe adapters, not proof an external system is running."""
    return [{**item, "configured": (
        bool(os.getenv("ASH_WAZUH_URL") and os.getenv("ASH_WAZUH_USER") and os.getenv("ASH_WAZUH_PASSWORD"))
        if item["id"] == "wazuh" else False
    )} for item in CATALOG]

def _manager_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Wazuh manager URL must not contain credentials, query or fragment")
    if parsed.path not in ("", "/"):
        raise ValueError("Configure only the Wazuh API root, not a path")
    local = parsed.hostname in ("127.0.0.1", "localhost", "::1")
    if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
        raise ValueError("Wazuh requires HTTPS outside localhost")
    if not parsed.hostname:
        raise ValueError("Missing Wazuh hostname")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")

def _open_json(request, *, opener=None):
    # Verification always remains enabled; never use an unverified SSL context.
    transport = opener or urllib.request.urlopen
    with transport(request, timeout=8) as response:
        raw = response.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError("Wazuh response exceeds allowed size")
    return json.loads(raw.decode("utf-8"))

def wazuh_agents(*, opener=None, environ=None):
    """Authenticate against an explicitly configured manager; list agents only."""
    env = os.environ if environ is None else environ
    base = _manager_url(env.get("ASH_WAZUH_URL", ""))
    user, password = env.get("ASH_WAZUH_USER"), env.get("ASH_WAZUH_PASSWORD")
    if not user or not password:
        raise ValueError("Set Ash Wazuh credentials in local environment variables")
    basic = base64.b64encode((user + ":" + password).encode()).decode()
    req = urllib.request.Request(
        base + "/security/user/authenticate?raw=true",
        method="POST", headers={"Authorization": "Basic " + basic, "Accept": "text/plain"},
    )
    transport = opener or urllib.request.urlopen
    with transport(req, timeout=8) as response:
        token = response.read(8192).decode("utf-8").strip()
    if not token or len(token) > 8191:
        raise ValueError("Manager returned no usable Wazuh session token")
    request = urllib.request.Request(
        base + "/agents?limit=50&select=id,name,status",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        method="GET",
    )
    result = _open_json(request, opener=opener)
    agents = result.get("data", {}).get("affected_items", [])
    if not isinstance(agents, list):
        raise ValueError("Unexpected Wazuh agent response")
    # Never return auth headers or a token to the UI.
    return {"source": "wazuh", "mode": "read-only", "agents": [
        {key: str(row.get(key, ""))[:120] for key in ("id", "name", "status")}
        for row in agents[:50] if isinstance(row, dict)
    ], "count": len(agents)}

def read_local_export(kind: str, path: str):
    """Import an existing report, never start a security scan from Ash."""
    if kind not in ("spiderfoot", "strix"):
        raise ValueError("Only exported SpiderFoot or Strix reports are supported")
    source = Path(path).expanduser().resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".json":
        raise ValueError("Choose a local JSON report file")
    if source.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("Report is too large (2 MB limit)")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, (list, dict)):
        raise ValueError("Invalid report JSON")
    records = data if isinstance(data, list) else next(
        (data[key] for key in ("findings", "results", "events", "data") if isinstance(data.get(key), list)), []
    )
    # Minimal, safe preview. Do not execute scripts from data or expose raw exports by default.
    return {"source": kind, "mode": "local-export", "path": str(source), "total": len(records),
            "preview": [{key: str(row.get(key, ""))[:200] for key in
                        ("type", "title", "severity", "risk", "data") if key in row}
                        for row in records[:20] if isinstance(row, dict)]}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("catalog", "wazuh-agents", "report"))
    p.add_argument("--kind", choices=("spiderfoot", "strix"))
    p.add_argument("--file")
    args = p.parse_args(argv)
    if args.action == "report" and (not args.kind or not args.file):
        p.error("--kind and --file are required for report")
    try:
        result = catalog() if args.action == "catalog" else (
            wazuh_agents() if args.action == "wazuh-agents" else read_local_export(args.kind, args.file)
        )
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Don't leak tokens/credentials returned by HTTP exceptions.
        print(json.dumps({"ok": False, "error_type": type(exc).__name__,
                          "message": "Connector failed. Check local configuration, service and report format."}), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
