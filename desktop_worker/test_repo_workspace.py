import pathlib
import tempfile
import unittest
from repo_workspace import parse_public_repo, import_public_repo
from agent_runtime import AshAgentRuntime
from test_agent_runtime import FakeAgent


class Result:
    returncode = 0


class RepositoryImportTests(unittest.TestCase):
    def test_only_plain_public_github_https_urls(self):
        self.assertEqual(parse_public_repo("https://github.com/openai/openai-python"),("openai","openai-python"))
        self.assertEqual(parse_public_repo("https://github.com/openai/openai-python.git"),("openai","openai-python"))
        for url in ["https://github.com@evil.test/a/b","https://evil.test/a/b","git@github.com:a/b",
                    "https://github.com/a/b?token=secret","https://github.com/a/../bad",
                    "file:///etc/passwd"]:
            with self.assertRaises(ValueError): parse_public_repo(url)

    def test_clone_places_source_in_workspace_and_does_not_run_code(self):
        with tempfile.TemporaryDirectory() as directory:
            commands=[]
            def runner(cmd, **kwargs):
                commands.append(cmd)
                if "clone" in cmd:
                    dest=pathlib.Path(cmd[-1])
                    (dest/".git").mkdir()
                    (dest/"README.md").write_text("Read me")
                return Result()
            r=import_public_repo("https://github.com/example/demo",directory,runner=runner)
            self.assertTrue(r["imported"])
            self.assertFalse(r["executed_untrusted_code"])
            self.assertTrue(r["review_required"])
            self.assertTrue((pathlib.Path(directory)/"repositories/example--demo/README.md").exists())
            self.assertEqual(len(commands),2)
            self.assertFalse(any("npm" in part or "pip" in part for cmd in commands for part in cmd))
            with self.assertRaises(FileExistsError):
                import_public_repo("https://github.com/example/demo",directory,runner=runner)

    def test_symlink_code_in_import_is_rejected_and_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            def runner(cmd, **kwargs):
                if "clone" in cmd:
                    dest=pathlib.Path(cmd[-1]);(dest/".git").mkdir()
                    (dest/"link").symlink_to("/etc/passwd")
                return Result()
            with self.assertRaises(ValueError):
                import_public_repo("https://github.com/example/demo",directory,runner=runner)
            self.assertFalse((pathlib.Path(directory)/"repositories/example--demo").exists())

    def test_import_is_confirmation_gated_for_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            agent=FakeAgent()
            agent.plan={"steps":[{"tool":"repo.public.import","args":{"url":"https://github.com/example/demo"}}]}
            result=AshAgentRuntime(agent,pathlib.Path(directory)).run("clone this repository")
            self.assertTrue(result.requires_confirmation)
            self.assertFalse((pathlib.Path(directory)/"repositories").exists())
