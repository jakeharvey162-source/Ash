import unittest
from unittest.mock import Mock, patch
from companion_presence import presence_command, launch_command
from companion_overlay import AshHologramCompanion


class PresenceTests(unittest.TestCase):
    def test_animation_assets_and_package_contract(self):
        import pathlib, struct
        root = pathlib.Path(__file__).parent
        for name in ("idle", "speaking", "thinking", "wave", "dance", "walking"):
            raw = (root / "assets" / "robot" / (name + ".png")).read_bytes()
            self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II', raw[16:24]), (3072, 320))
        workflow = (root.parent / '.github/workflows/windows-desktop-release.yml').read_text()
        self.assertIn('--add-data "desktop_worker/assets;assets"', workflow)
    def test_only_explicit_presence_commands(self):
        self.assertEqual(presence_command("Ash, get out!")[0], "dismiss")
        self.assertEqual(presence_command("come back")[0], "summon")
        self.assertIsNone(presence_command("How do I hide a WinForms window?"))
        self.assertIsNone(presence_command("don't disappear"))

    def test_wake_restores_hidden_companion(self):
        companion = object.__new__(AshHologramCompanion)
        companion.presence = "hidden"
        companion._summon = Mock()
        companion._handle_event({"type": "wake"})
        companion._summon.assert_called_once()

    def test_dismiss_does_not_stop_voice_or_worker(self):
        companion = object.__new__(AshHologramCompanion)
        companion.root = Mock()
        companion._hide_temporarily()
        self.assertEqual(companion.presence, "departing")
        companion.root.withdraw.assert_not_called()

    @patch("companion_presence.subprocess.Popen")
    @patch("companion_presence.platform.system", return_value="Windows")
    def test_allowlisted_launch_has_no_shell(self, platform, popen):
        self.assertEqual(launch_command("open calculator"), "Launched calculator.")
        self.assertEqual(popen.call_args.args[0], ["calc.exe"])
        self.assertNotIn("shell", popen.call_args.kwargs)
        self.assertIsNone(launch_command("open calculator & delete files"))

    @patch("companion_presence.subprocess.Popen", side_effect=FileNotFoundError("not installed"))
    def test_unavailable_app_never_claims_success(self, popen):
        with self.assertRaises(OSError):
            launch_command("open calculator")

    def test_voice_retains_context_after_portal(self):
        from voice_runtime.lite_runtime import AshLiteVoiceRuntime
        runtime = object.__new__(AshLiteVoiceRuntime)
        runtime.agent = Mock()
        runtime.agent.think_stream.return_value = "We were building your coffee shop."
        runtime.recent_turns = []
        with patch('voice_runtime.lite_runtime.speak_windows'), patch('voice_runtime.lite_runtime.emit'):
            runtime.run_text('Build a coffee shop website')
            remembered = list(runtime.recent_turns)
            runtime.run_text('get out')
            self.assertEqual(runtime.recent_turns, remembered)
            runtime.run_text('come back')
            runtime.run_text('What were we doing?')
        self.assertIn('coffee shop', runtime.agent.think_stream.call_args.args[0])
