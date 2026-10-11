import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from desktop_worker.intelligence_hub import catalog, _manager_url, read_local_export, wazuh_agents

class Response:
    def __init__(self, content):
        self.content = content
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit=None): return self.content[:limit] if limit else self.content

class IntelligenceHubTests(unittest.TestCase):
    def test_catalog_is_honest_about_scope(self):
        items = {i["id"]: i for i in catalog()}
        self.assertEqual(items["gods-eye-view"]["mode"], "link-only")
        self.assertEqual(items["shadowbroker"]["mode"], "link-only")
        self.assertEqual(items["strix"]["mode"], "local-report-only")
    def test_wazuh_requires_https_without_embedded_credentials(self):
        for bad in ("http://example.org:55000", "https://user:pass@example.org", "https://example.org/agents"):
            with self.assertRaises(ValueError): _manager_url(bad)
        self.assertEqual(_manager_url("https://example.org:55000/"), "https://example.org:55000")
        self.assertEqual(_manager_url("http://127.0.0.1:55000"), "http://127.0.0.1:55000")
    def test_wazuh_read_only_requests_never_expose_token(self):
        calls = []
        def fake_open(req, timeout):
            calls.append((req.get_method(), req.full_url, dict(req.headers)))
            if len(calls) == 1: return Response(b"TEST_JWT")
            return Response(json.dumps({"data": {"affected_items": [
                {"id": "001", "name": "Lab Laptop", "status": "active", "secret": "no"}
            ]}}).encode())
        result = wazuh_agents(opener=fake_open, environ={
            "ASH_WAZUH_URL": "https://127.0.0.1:55000", "ASH_WAZUH_USER": "tester",
            "ASH_WAZUH_PASSWORD": "private"})
        self.assertEqual(result["agents"][0]["status"], "active")
        self.assertNotIn("TEST_JWT", str(result))
        self.assertNotIn("private", str(result))
        self.assertEqual([call[0] for call in calls], ["POST", "GET"])
    def test_spiderfoot_report_is_local_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scan.json"
            path.write_text(json.dumps([{"type": "DNS_NAME", "data": "lab.example", "private": "hidden"}]))
            result = read_local_export("spiderfoot", str(path))
            self.assertEqual(result["total"], 1)
            self.assertNotIn("hidden", str(result))
            with self.assertRaises(ValueError): read_local_export("unknown", str(path))
if __name__ == "__main__":
    unittest.main()
