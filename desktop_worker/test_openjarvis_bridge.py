import unittest

from openjarvis_bridge import OpenJarvisBackend


class OpenJarvisBridgeTests(unittest.TestCase):
    def test_profile_aliases_resolve_to_safe_profiles(self):
        self.assertEqual(OpenJarvisBackend.profile("deep_research").name, "research")
        self.assertEqual(OpenJarvisBackend.profile("native_react").name, "react")
        self.assertEqual(OpenJarvisBackend.profile("rlm").name, "long_context")
        self.assertEqual(OpenJarvisBackend.profile("unknown").name, "orchestrator")

    def test_only_code_profile_is_marked_side_effecting(self):
        self.assertTrue(OpenJarvisBackend.profile("code").side_effects)
        for name in ("orchestrator", "research", "react", "long_context", "simple"):
            self.assertFalse(OpenJarvisBackend.profile(name).side_effects)


if __name__ == "__main__":
    unittest.main()
