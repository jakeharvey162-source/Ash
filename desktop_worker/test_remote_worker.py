import unittest

from remote_worker import AshRemoteWorker


class FakeOffline:
    class Status:
        backend = "python_micro_core"

    def status(self):
        return self.Status()

    def respond(self, prompt, mode="high"):
        return "offline:" + prompt


class FakeAgent:
    def __init__(self, local_ok=True):
        self.local_ok = local_ok
        self.offline = FakeOffline()

    def _local(self, prompt):
        if not self.local_ok:
            raise RuntimeError("ollama unavailable")
        return "ollama:" + prompt


class RescueWorkerTests(unittest.TestCase):
    def make_worker(self, local_ok=True):
        worker = AshRemoteWorker.__new__(AshRemoteWorker)
        worker.agent = FakeAgent(local_ok)
        worker.device_name = "Test Desktop"
        worker.finished = None

        def finish(job_id, *, ok, result=None, error=""):
            worker.finished = {
                "job_id": job_id,
                "ok": ok,
                "result": result or {},
                "error": error,
            }

        worker.finish = finish
        return worker

    def test_rescue_prefers_ollama(self):
        worker = self.make_worker(True)
        worker.process({
            "id": "job-1",
            "kind": "chat_fallback",
            "mode": "high",
            "payload": {"prompt": "hello", "rescue": True},
        })
        self.assertTrue(worker.finished["ok"])
        self.assertEqual(worker.finished["result"]["summary"], "ollama:hello")
        self.assertEqual(worker.finished["result"]["backend"], "ollama")
        self.assertTrue(worker.finished["result"]["rescue"])

    def test_rescue_falls_back_to_offline_brain(self):
        worker = self.make_worker(False)
        worker.process({
            "id": "job-2",
            "kind": "chat_fallback",
            "mode": "high",
            "payload": {"prompt": "hello", "rescue": True},
        })
        self.assertTrue(worker.finished["ok"])
        self.assertEqual(worker.finished["result"]["summary"], "offline:hello")
        self.assertEqual(worker.finished["result"]["backend"], "python_micro_core")


if __name__ == "__main__":
    unittest.main()
