import pathlib
import tempfile
import unittest

from local_scheduler import LocalScheduler


class LocalSchedulerTests(unittest.TestCase):
    def test_create_due_complete_and_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = LocalScheduler(pathlib.Path(tmp))
            task = scheduler.create("Check project", "summarize status", 1)
            self.assertEqual(len(scheduler.list()), 1)
            self.assertEqual(scheduler.due(now=task["next_run"] - 1), [])
            due = scheduler.due(now=task["next_run"] + 1)
            self.assertEqual(due[0]["id"], task["id"])
            scheduler.complete(task["id"], ok=True, summary="done")
            refreshed = scheduler.list()[0]
            self.assertIsNotNone(refreshed["last_run"])
            self.assertGreater(refreshed["next_run"], task["next_run"])
            self.assertTrue(scheduler.cancel(task["id"]))
            self.assertEqual(scheduler.list(), [])

    def test_interval_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = LocalScheduler(pathlib.Path(tmp))
            with self.assertRaises(ValueError):
                scheduler.create("bad", "x", 0)


if __name__ == "__main__":
    unittest.main()
