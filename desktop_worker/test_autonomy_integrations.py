import json
import pathlib
import tempfile
import unittest

from agent_runtime import AshAgentRuntime
from local_scheduler import LocalScheduler
from test_agent_runtime import FakeAgent


class SafeAutonomyTests(unittest.TestCase):
    def test_claim_persists_lease_and_skips_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            schedule = LocalScheduler(pathlib.Path(tmp))
            task = schedule.create("Status check", "Summarize project status", 1)
            now = task["next_run"] + 1
            claims = schedule.claim_due(now=now)
            self.assertEqual(len(claims), 1)
            self.assertTrue(claims[0]["lease_id"])
            self.assertEqual(schedule.claim_due(now=now + 30), [])
            restarted = LocalScheduler(pathlib.Path(tmp))
            self.assertEqual(restarted.claim_due(now=now + 30), [])
            self.assertEqual(len(restarted.claim_due(now=now + 3601)), 1)

    def test_confirmation_pauses_automation_until_resumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            schedule = LocalScheduler(pathlib.Path(tmp))
            task = schedule.create("Test", "Draft note", 1)
            lease = schedule.claim_due(now=task["next_run"] + 1)[0]
            schedule.complete(task["id"], ok=False, needs_confirmation=True,
                              lease_id=lease["lease_id"], error="needs approval")
            self.assertFalse(schedule.list()[0]["enabled"])
            self.assertEqual(schedule.claim_due(now=task["next_run"] + 7200), [])
            self.assertTrue(schedule.resume(task["id"]))
            self.assertTrue(schedule.list()[0]["enabled"])

    def test_stale_worker_completion_cannot_override_new_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            schedule = LocalScheduler(pathlib.Path(tmp))
            task = schedule.create("Test", "Summarize", 1)
            old = schedule.claim_due(now=task["next_run"] + 1)[0]
            fresh = schedule.claim_due(now=task["next_run"] + 3700)[0]
            schedule.complete(task["id"], ok=True, lease_id=old["lease_id"], summary="stale")
            self.assertEqual(schedule.list()[0]["lease_id"], fresh["lease_id"])

    def test_reject_more_than_100_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            schedule = LocalScheduler(pathlib.Path(tmp))
            for i in range(100):
                schedule.create("check", "summarize", 1)
            with self.assertRaises(ValueError):
                schedule.create("extra", "summarize", 1)

    def test_failed_tool_returns_failure_not_fake_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeAgent()
            fake.plan = {"steps": [{"tool": "files.read", "args": {"path": "missing.txt"}}],
                         "answer_instruction": "say succeeded"}
            runtime = AshAgentRuntime(fake, pathlib.Path(tmp))
            result = runtime.run("read the missing file")
            self.assertFalse(result.ok)
            self.assertFalse(result.requires_confirmation)
            self.assertEqual(result.evidence[0]["ok"], False)
            self.assertNotIn("final answer", result.output)

    def test_intelligence_catalog_is_usable_without_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeAgent()
            fake.plan = {"steps": [{"tool": "intelligence.catalog", "args": {}}],
                         "answer_instruction": "show honest state"}
            runtime = AshAgentRuntime(fake, pathlib.Path(tmp))
            result = runtime.run("show available intelligence integrations")
            self.assertTrue(result.ok)
            self.assertEqual(result.evidence[0]["tool"], "intelligence.catalog")
            self.assertIn("gods-eye-view", json.dumps(result.evidence[0]["result"]))

    def test_local_security_reports_must_stay_in_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeAgent()
            runtime = AshAgentRuntime(fake, pathlib.Path(tmp))
            with self.assertRaises(ValueError):
                runtime._tool_intelligence_report({"kind": "strix", "path": "../secret.json"})
            report = pathlib.Path(tmp) / "assessment.json"
            report.write_text(json.dumps({"findings": [{"title": "Test finding", "severity": "low"}]}))
            output = runtime._tool_intelligence_report({"kind": "strix", "path": "assessment.json"})
            self.assertEqual(output["total"], 1)


if __name__ == "__main__":
    unittest.main()
