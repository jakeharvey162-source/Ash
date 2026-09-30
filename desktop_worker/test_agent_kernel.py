import pathlib
import tempfile
import unittest

from agent_kernel import AgentKernel


class AgentKernelTests(unittest.TestCase):
    def test_route_falls_back_and_cools_failed_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            kernel = AgentKernel(pathlib.Path(tmp))
            calls = {"cloud": 0, "local": 0}

            def cloud():
                calls["cloud"] += 1
                raise RuntimeError("offline")

            def local():
                calls["local"] += 1
                return "local answer"

            result = kernel.route(
                "private prompt",
                [("cloud", cloud, 60.0), ("local", local, 0.0)],
                mode="high",
            )
            self.assertEqual(result, "local answer")
            self.assertEqual(calls["cloud"], 1)

            result = kernel.route(
                "private prompt",
                [("cloud", cloud, 60.0), ("local", local, 0.0)],
                mode="high",
            )
            self.assertEqual(result, "local answer")
            self.assertEqual(calls["cloud"], 1)
            self.assertEqual(calls["local"], 2)

    def test_skill_context_is_relevant_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            (skills / "research.md").write_text(
                "keywords: research sources verify latest\n"
                "# Research\nUse current sources and separate facts from assumptions.",
                encoding="utf-8",
            )
            (skills / "design.md").write_text(
                "keywords: layout typography ui\n# Design\nUse deliberate spacing.",
                encoding="utf-8",
            )
            kernel = AgentKernel(root)
            prompt = kernel.prepare_prompt("Research the latest release and verify sources.")
            self.assertIn("[Skill: research]", prompt)
            self.assertNotIn("[Skill: design]", prompt)
            self.assertLess(len(prompt), 5000)

    def test_route_can_preserve_source_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            kernel = AgentKernel(pathlib.Path(tmp))
            result = kernel.route(
                "generate source",
                [("local", lambda: "export default 1;\n", 0.0)],
                action="generate",
                preserve_whitespace=True,
            )
            self.assertEqual(result, "export default 1;\n")

    def test_trace_never_stores_raw_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            kernel = AgentKernel(root)
            secret = "MY_PRIVATE_SECRET_123"
            self.assertEqual(
                kernel.route(secret, [("local", lambda: "ok", 0.0)]),
                "ok",
            )
            trace = kernel.trace_path.read_text(encoding="utf-8")
            self.assertNotIn(secret, trace)
            self.assertIn('"prompt_id"', trace)


if __name__ == "__main__":
    unittest.main()
