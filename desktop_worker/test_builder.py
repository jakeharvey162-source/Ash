import pathlib
import tempfile
import unittest
import subprocess
from unittest.mock import patch

from ash_agent import AshPythonAgent


class BuilderSafetyTests(unittest.TestCase):
    def setUp(self):
        self.agent = AshPythonAgent()

    def test_source_generation_never_uses_offline_chat_as_code(self):
        with patch.object(self.agent, "_cloud", side_effect=RuntimeError("unavailable")), patch.object(self.agent, "_local", side_effect=RuntimeError("not installed")), patch.object(self.agent.offline, "respond", side_effect=AssertionError("offline prose is not source")):
            with self.assertRaisesRegex(RuntimeError, "Source generation unavailable"):
                self.agent._generate_source("Generate file")

    def test_source_generation_uses_real_local_code_when_cloud_fails(self):
        with patch.object(self.agent, "_cloud", side_effect=RuntimeError("unavailable")), patch.object(self.agent, "_local", return_value="```js\nexport default 1;\n```"):
            self.assertEqual(self.agent._generate_source("Generate file"), "export default 1;\n")

    def test_computer_plan_normalizes_1000_space_to_screen_pixels(self):
        mapped = self.agent._map_plan_coordinates({
            "done": False,
            "coordinate_space": "normalized_1000",
            "actions": [{"type": "click", "x": 500, "y": 450}],
        }, 800, 600)
        action = mapped["actions"][0]
        self.assertEqual(action["x"], 400)
        self.assertTrue(268 <= action["y"] <= 270)
        self.assertEqual(mapped["coordinate_space"], "screen_pixels")

    def test_safe_write_stays_inside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp).resolve()
            target = self.agent._safe_write(root, 'src/app.js', "console.log('ok')")
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding='utf-8'), "console.log('ok')")

    def test_safe_write_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp).resolve()
            with self.assertRaises(ValueError):
                self.agent._safe_write(root, '../escape.txt', 'nope')

    def test_run_rejects_unapproved_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp).resolve()
            with self.assertRaises(ValueError):
                self.agent._run(root, ['bash', '-lc', 'echo nope'])

    def test_extract_json_from_fenced_output(self):
        text = '```json\n{"name":"demo","files":[{"path":"index.html","purpose":"entry"}]}\n```'
        data = self.agent._extract_json(text)
        self.assertEqual(data['name'], 'demo')
        self.assertEqual(data['files'][0]['path'], 'index.html')

    def test_extract_json_ignores_trailing_commentary(self):
        text = 'Result: {"ok":true,"files":[]} trailing words that are not JSON'
        data = self.agent._extract_json(text)
        self.assertTrue(data['ok'])
        self.assertEqual(data['files'], [])


    def run_build_case(self, codes, repair_patch=None, planning_fails=False):
        agent = self.agent
        plan = {"name": "Test app", "files": [{"path": "package.json", "purpose": "build"}]}
        responses = [RuntimeError("planner offline") if planning_fails else plan]
        if repair_patch is not None:
            responses.append(repair_patch)
        def run(root, command, timeout):
            code = next(codes)
            return subprocess.CompletedProcess(command, code, "build output", "syntax error" if code else "")
        def renderer(root, request, plan=None):
            (root / "package.json").write_text('{"scripts":{"build":"vite build"}}')
            return ["package.json"]
        with tempfile.TemporaryDirectory() as tmp, patch.object(agent, "think_json", side_effect=responses), patch.object(agent, "think", side_effect=AssertionError("QA must not depend on a model")), patch.object(agent, "_run", side_effect=run), patch.object(agent, "_write_verified_fallback_site", side_effect=renderer):
            return agent.build_fullstack("Build a task management app", tmp)

    def test_success_reports_only_verified_build(self):
        result = self.run_build_case(iter([0, 0]))
        self.assertTrue(result.ok)
        self.assertFalse(result.details["degraded"])
        self.assertFalse(result.details["verification"]["requirements_verified"])
        self.assertFalse(result.details["verification"]["browser_verified"])

    def test_failed_build_is_repaired_before_fallback(self):
        result = self.run_build_case(iter([0, 1, 0]), {"files": [{"path": "src/app.js", "content": "export default 1;"}]})
        self.assertTrue(result.ok)
        self.assertEqual(result.details["repaired_files"], ["src/app.js"])
        self.assertEqual(result.details["generation_mode"], "generated_source")
        self.assertFalse(result.details["degraded"])
        self.assertEqual(result.details["evidence"][-1]["command"], "npm run build (repair 1)")

    def test_failed_repair_is_explicitly_degraded(self):
        result = self.run_build_case(iter([0, 1, 0, 0]), {"files": []})
        self.assertTrue(result.ok)
        self.assertTrue(result.details["degraded"])
        self.assertEqual(result.details["generation_mode"], "recovery_renderer")
        self.assertIn("not verified", result.output)

    def test_install_failure_is_not_success(self):
        result = self.run_build_case(iter([1]))
        self.assertFalse(result.ok)
        self.assertFalse(result.details["verification"]["build_passed"])


if __name__ == '__main__':
    unittest.main()
