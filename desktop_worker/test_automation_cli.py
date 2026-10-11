import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from automation_cli import main

class AutonomyCliTests(unittest.TestCase):
    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = main(["--home", str(self.folder), *args])
        self.assertEqual(rc, 0)
        return json.loads(output.getvalue())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_create_pause_resume_cancel_without_executing(self):
        created = self.invoke("create", "--name", "Daily report",
                              "--prompt", "Summarize local project status",
                              "--every-minutes", "60")
        task_id = created["created"]["id"]
        self.assertEqual(self.invoke("list")["tasks"][0]["id"], task_id)
        self.assertTrue(self.invoke("pause", task_id)["paused"])
        self.assertFalse(self.invoke("list")["tasks"][0]["enabled"])
        self.assertTrue(self.invoke("resume", task_id)["resumed"])
        self.assertTrue(self.invoke("list")["tasks"][0]["enabled"])
        self.assertTrue(self.invoke("cancel", task_id)["cancelled"])
        self.assertEqual(self.invoke("list")["tasks"], [])

    def test_history_empty_when_no_runs(self):
        self.assertEqual(self.invoke("history"), {"runs": []})

if __name__ == "__main__":
    unittest.main()
