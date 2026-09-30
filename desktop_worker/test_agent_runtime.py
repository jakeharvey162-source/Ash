import pathlib
import tempfile
import unittest
from unittest.mock import Mock

from agent_runtime import AshAgentRuntime


class FakeMemory:
    def __init__(self):
        self.items = []
    def search(self, query, limit=5):
        return [x for x in self.items if query.lower() in x.lower()][:limit]
    def add(self, content, kind="conversation"):
        self.items.append(content)


class FakeOffline:
    class Status:
        mode = "offline"
        backend = "test"
        model_path = None
        memory_path = "memory.sqlite3"
        generative_ready = False
        __dict__ = {"mode": "offline", "backend": "test", "generative_ready": False}
    def __init__(self):
        self.memory = FakeMemory()
    def status(self):
        return self.Status()


class FakeKernel:
    def health_snapshot(self):
        return {"cloud": {"successes": 1}}
    def skill_context(self, _prompt):
        return "skill"


class FakeOpenJarvis:
    available = True
    def __init__(self):
        self.calls = []
    def status(self):
        return {"available": True}
    def ask(self, task, profile="orchestrator", allow_side_effects=False):
        self.calls.append((task, profile, allow_side_effects))
        return f"{profile}:{task}"
    def memory_search(self, query, top_k=5):
        return [{"content": query, "score": 1.0}]
    def memory_index(self, path):
        return {"path": path, "chunks": 1}


class FakeAgent:
    def __init__(self):
        self.offline = FakeOffline()
        self.kernel = FakeKernel()
        self.openjarvis = FakeOpenJarvis()
        self.plan = {"steps": [], "answer_instruction": "answer"}
        self.answers = []
    def think_json(self, _prompt, attempts=2):
        return self.plan
    def think(self, prompt, mode="high", action="chat"):
        self.answers.append(prompt)
        return "final answer"
    def _cloud(self, prompt, mode="high", action="chat"):
        return "research:" + prompt


class AgentRuntimeTests(unittest.TestCase):
    def test_confirmation_gate_blocks_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = FakeAgent()
            agent.plan = {
                "steps": [{"tool": "files.write", "args": {"path": "x.txt", "content": "hello"}}],
                "answer_instruction": "save it",
            }
            runtime = AshAgentRuntime(agent, pathlib.Path(tmp))
            result = runtime.run("save hello")
            self.assertTrue(result.requires_confirmation)
            self.assertFalse((pathlib.Path(tmp) / "x.txt").exists())

    def test_confirmed_write_stays_in_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = FakeAgent()
            agent.plan = {
                "steps": [{"tool": "files.write", "args": {"path": "notes/x.txt", "content": "hello"}}],
                "answer_instruction": "confirm saved",
            }
            runtime = AshAgentRuntime(agent, pathlib.Path(tmp))
            result = runtime.run("save hello", allow_side_effects=True)
            self.assertTrue(result.ok)
            self.assertEqual((pathlib.Path(tmp) / "notes" / "x.txt").read_text(), "hello")
            self.assertEqual(result.tools_used, ["files.write"])

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = AshAgentRuntime(FakeAgent(), pathlib.Path(tmp))
            with self.assertRaises(ValueError):
                runtime._safe_path("../escape.txt")

    def test_openjarvis_research_profile_is_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = FakeAgent()
            agent.plan = {
                "steps": [{"tool": "specialist.openjarvis.research", "args": {"task": "compare sources"}}],
                "answer_instruction": "summarize",
            }
            result = AshAgentRuntime(agent, pathlib.Path(tmp)).run("research this")
            self.assertTrue(result.ok)
            self.assertIn("specialist.openjarvis.research", result.tools_used)
            self.assertEqual(agent.openjarvis.calls[0][1], "research")

    def test_openjarvis_code_profile_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = FakeAgent()
            agent.plan = {
                "steps": [{"tool": "specialist.openjarvis.code", "args": {"task": "run code"}}],
                "answer_instruction": "do it",
            }
            runtime = AshAgentRuntime(agent, pathlib.Path(tmp))
            blocked = runtime.run("execute this code")
            self.assertTrue(blocked.requires_confirmation)
            self.assertFalse(agent.openjarvis.calls)
            allowed = runtime.run("execute this code", allow_side_effects=True)
            self.assertTrue(allowed.ok)
            self.assertEqual(agent.openjarvis.calls[0][1], "code")
            self.assertTrue(agent.openjarvis.calls[0][2])

    def test_research_evidence_is_passed_to_final_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = FakeAgent()
            agent.plan = {
                "steps": [{"tool": "research.live", "args": {"query": "latest release"}}],
                "answer_instruction": "summarize",
            }
            result = AshAgentRuntime(agent, pathlib.Path(tmp)).run("what is latest?")
            self.assertTrue(result.ok)
            self.assertIn("research.live", result.tools_used)
            self.assertIn("VERIFIED TOOL EVIDENCE", agent.answers[-1])


if __name__ == "__main__":
    unittest.main()
