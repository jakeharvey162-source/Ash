import pathlib
import tempfile
import unittest
from build_quality import assess_build

class WebsiteQualityReportTests(unittest.TestCase):
    def make_workspace(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root=pathlib.Path(temp.name)
        (root/"src").mkdir()
        return root

    def test_complete_report_is_honest_about_missing_browser_testing(self):
        root=self.make_workspace()
        (root/"src"/"App.jsx").write_text(
            '<main><nav>Links</nav><button onClick={()=>{}}>Go</button></main>',encoding="utf-8")
        (root/"src"/"styles.css").write_text(
            "@media(max-width:500px){main{display:grid}}"
            "button:focus-visible{outline:2px solid;}"
            "@media(prefers-reduced-motion:reduce){*{transition:none}}",encoding="utf-8")
        result=assess_build(root,{"verification":{"build_passed":True},
                                  "generation_mode":"planned_renderer","degraded":False})
        self.assertTrue(result["verified_build"])
        self.assertFalse(result["production_ready"])
        self.assertFalse(result["browser_tested"])
        self.assertFalse(result["user_feedback_collected"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["warnings"],[])

    def test_fallback_is_not_called_a_verified_complete_app(self):
        root=self.make_workspace()
        (root/"index.html").write_text("<h1>Lorem ipsum</h1>",encoding="utf-8")
        result=assess_build(root,{"verification":{"build_passed":True},
                                  "generation_mode":"fallback_scaffold","degraded":True})
        self.assertFalse(result["checks"]["placeholder_copy_absent"])
        self.assertTrue(result["degraded"])
        self.assertIn("generation", " ".join(result["warnings"]).lower())

    def test_unbuilt_project_reports_failed_build(self):
        root=self.make_workspace()
        report=assess_build(root,{"verification":{"build_passed":False}})
        self.assertFalse(report["verified_build"])
        self.assertFalse(report["production_ready"])

    def test_ignores_dist_node_modules_and_symlink_escape(self):
        root=self.make_workspace()
        (root/"node_modules").mkdir()
        (root/"node_modules"/"unsafe.js").write_text("lorem ipsum",encoding="utf-8")
        outside=self.make_workspace()
        (outside/"secret.js").write_text("lorem ipsum",encoding="utf-8")
        link=root/"src"/"linked.js"
        try:
            link.symlink_to(outside/"secret.js")
        except OSError:
            pass
        (root/"src"/"safe.js").write_text("export const ok=true;",encoding="utf-8")
        result=assess_build(root,{})
        self.assertEqual(result["source_files_inspected"],1)
        self.assertTrue(result["checks"]["placeholder_copy_absent"])

if __name__=="__main__":
    unittest.main()
