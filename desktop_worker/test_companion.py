import os
import unittest
from unittest.mock import patch

from companion_overlay import AshHologramCompanion

class CompanionContractTests(unittest.TestCase):
    def test_release_version_comparison_is_semantic(self):
        self.assertEqual(AshHologramCompanion._version_tuple("v0.3.12"), (0, 3, 12))
        self.assertGreater(AshHologramCompanion._version_tuple("1.0.0"), AshHologramCompanion._version_tuple("0.99.99"))
        self.assertEqual(AshHologramCompanion._version_tuple("dev"), (0, 0, 0))

    def test_companion_source_keeps_permissioned_control_separate(self):
        path=os.path.join(os.path.dirname(__file__),"companion_overlay.py")
        text=open(path,encoding="utf-8").read()
        self.assertIn("voice_runtime.runtime",text)
        self.assertNotIn("pyautogui",text)
        self.assertIn("ASH_COMPANION_VOICE",text)
        self.assertIn("-topmost",text)
        self.assertIn("AshHologramCompanion",text)
        self.assertIn("_draw_hologram",text)
        self.assertIn("voice_runtime.runtime",text)
        self.assertIn("remote_worker.py",text)
        self.assertIn("_poll_global_hotkey",text)
        self.assertIn("GetAsyncKeyState",text)
        self.assertIn("AshScreenAura",text)
        self.assertIn("WS_EX_TRANSPARENT",text)
        self.assertIn("_draw_telemetry",text)
        self.assertIn("_first_run_setup",text)
        self.assertIn("_link_computer",text)
        self.assertIn("AshWorker.exe",text)
        self.assertIn("AshVoice.exe",text)
        self.assertIn("simpledialog.askstring",text)

if __name__=="__main__":
    unittest.main()
