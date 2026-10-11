import pathlib
import tempfile
import unittest
from ash_agent import AshPythonAgent
from design_systems import DESIGN_PRESETS, fallback_css_for_request

class FallbackDesignTests(unittest.TestCase):
    def test_renderer_generates_distinct_css_without_external_dependencies(self):
        agent=AshPythonAgent.__new__(AshPythonAgent)
        found=set()
        for preset in DESIGN_PRESETS.values():
            with tempfile.TemporaryDirectory() as folder:
                root=pathlib.Path(folder).resolve()
                files=agent._write_verified_fallback_site(root,"Build premium website. Preset: "+preset["label"])
                self.assertIn("src/styles.css",files)
                css=(root/"src/styles.css").read_text()
                self.assertIn("Ash Studio original fallback palette",css)
                self.assertIn("prefers-reduced-motion",css)
                found.add(css)
        self.assertEqual(len(found),4)

    def test_no_preset_keeps_legacy_default(self):
        self.assertEqual(fallback_css_for_request("Build a website"),"")

if __name__=="__main__":
    unittest.main()
