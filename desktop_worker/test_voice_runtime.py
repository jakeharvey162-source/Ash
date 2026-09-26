import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from voice_runtime.wake import WakeMatcher

class WakeMatcherTests(unittest.TestCase):
    def test_exact_wake_word(self):
        self.assertEqual(WakeMatcher("Ash").extract("Ash open my project"), "open my project")

    def test_alias(self):
        self.assertEqual(WakeMatcher("Ash").extract("Hey Ash, summarize this"), "summarize this")

    def test_arise_alias(self):
        self.assertEqual(WakeMatcher("Ash").extract("Arise, open my dashboard"), "open my dashboard")

    def test_short_word_does_not_fuzzy_match_cash(self):
        self.assertIsNone(WakeMatcher("Ash").extract("cash flow looks good"))

    def test_wake_word_alone(self):
        self.assertEqual(WakeMatcher("Ash").extract("Ash"), "")

    def test_synced_preferences_change_wake_word(self):
        with tempfile.TemporaryDirectory() as td:
            prefs = Path(td) / "preferences.json"
            prefs.write_text(json.dumps({
                "assistant_name": "Orion",
                "wake_word": "Nova",
                "wake_aliases": ["sentinel"]
            }), encoding="utf-8")
            old = os.environ.get("ASH_PREFERENCES_FILE")
            os.environ["ASH_PREFERENCES_FILE"] = str(prefs)
            try:
                matcher = WakeMatcher()
                self.assertEqual(matcher.extract("Nova open my project"), "open my project")
                self.assertEqual(matcher.extract("Sentinel, summarize this"), "summarize this")
                self.assertIsNone(matcher.extract("Ash open my project"))
                time.sleep(0.8)
                prefs.write_text(json.dumps({
                    "assistant_name": "Atlas",
                    "wake_word": "Atlas",
                    "wake_aliases": ["computer"]
                }), encoding="utf-8")
                self.assertEqual(matcher.extract("Atlas open settings"), "open settings")
                self.assertEqual(matcher.extract("Computer, status report"), "status report")
                self.assertIsNone(matcher.extract("Nova open settings"))
            finally:
                if old is None:
                    os.environ.pop("ASH_PREFERENCES_FILE", None)
                else:
                    os.environ["ASH_PREFERENCES_FILE"] = old

if __name__ == "__main__":
    unittest.main()
