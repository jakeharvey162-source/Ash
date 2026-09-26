import os
import unittest
from unittest.mock import patch

from computer_control import AshComputerController, ComputerControlUnavailable


class FakePyAutoGui:
    FAILSAFE = False
    PAUSE = 0

    def __init__(self):
        self.calls = []

    class _Size:
        width = 1920
        height = 1080

    def size(self):
        return self._Size()

    def write(self, text, interval=0):
        self.calls.append(("write", text))

    def hotkey(self, *keys):
        self.calls.append(("hotkey", keys))

    def press(self, key):
        self.calls.append(("press", key))

    def moveTo(self, x, y, duration=0):
        self.calls.append(("move", x, y))

    def click(self, x, y):
        self.calls.append(("click", x, y))

    def doubleClick(self, x, y, interval=0):
        self.calls.append(("double", x, y))

    def scroll(self, amount):
        self.calls.append(("scroll", amount))


class ComputerControlSafetyTests(unittest.TestCase):
    def test_control_is_off_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ComputerControlUnavailable):
                AshComputerController(agent=object())

    def controller(self):
        c = AshComputerController.__new__(AshComputerController)
        c.pyautogui = FakePyAutoGui()
        return c

    def test_refuses_sensitive_auth_text(self):
        c = self.controller()
        with self.assertRaises(ValueError):
            c.execute_action({"type": "type_text", "text": "OTP=123456"})

    def test_refuses_protected_system_hotkey(self):
        c = self.controller()
        with self.assertRaises(ValueError):
            c.execute_action({"type": "hotkey", "keys": ["ctrl", "alt", "delete"]})

    def test_coordinates_are_bounded(self):
        c = self.controller()
        result = c.execute_action({"type": "click", "x": 99999, "y": -20})
        self.assertEqual(result["x"], 1919)
        self.assertEqual(result["y"], 0)

    def test_sensitive_goal_is_stopped_before_control(self):
        c = self.controller()
        result = c.run_goal("Please handle a payment in the browser", max_steps=2)
        self.assertFalse(result["ok"])
        self.assertTrue(result["manual_required"])
        self.assertEqual(result["steps"], 0)

    def test_benign_goal_is_not_blocked_by_risk_gate(self):
        c = self.controller()
        self.assertEqual(c.risk_reason("Open my project dashboard and show the latest build"), "")

    def test_text_length_is_bounded(self):
        c = self.controller()
        with self.assertRaises(ValueError):
            c.execute_action({"type": "type_text", "text": "a" * 1801})


if __name__ == "__main__":
    unittest.main()
