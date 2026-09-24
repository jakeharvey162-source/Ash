import unittest
from voice_runtime.wake import WakeMatcher

class WakeMatcherTests(unittest.TestCase):
    def test_exact_wake_word(self):
        self.assertEqual(WakeMatcher("Ash").extract("Ash open my project"), "open my project")

    def test_alias(self):
        self.assertEqual(WakeMatcher("Ash").extract("Hey Ash, summarize this"), "summarize this")

    def test_arise_alias(self):\n        self.assertEqual(WakeMatcher("Ash").extract("Arise, open my dashboard"), "open my dashboard")\n\n    def test_short_word_does_not_fuzzy_match_cash(self):
        self.assertIsNone(WakeMatcher("Ash").extract("cash flow looks good"))

    def test_wake_word_alone(self):
        self.assertEqual(WakeMatcher("Ash").extract("Ash"), "")

if __name__ == "__main__":
    unittest.main()
