import pathlib
import tempfile
import unittest

from ash_agent import AshPythonAgent


class BuilderSafetyTests(unittest.TestCase):
    def setUp(self):
        self.agent = AshPythonAgent()

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


if __name__ == '__main__':
    unittest.main()
