import os
import unittest
from unittest.mock import patch

class CompanionContractTests(unittest.TestCase):
    def test_companion_source_keeps_permissioned_control_separate(self):
        path=os.path.join(os.path.dirname(__file__),"companion_overlay.py")
        text=open(path,encoding="utf-8").read()
        self.assertIn("voice_runtime.runtime",text)
        self.assertNotIn("pyautogui",text)
        self.assertIn("ASH_COMPANION_VOICE",text)
        self.assertIn("-topmost",text)

if __name__=="__main__":
    unittest.main()
