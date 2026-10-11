import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from design_systems import DESIGN_PRESETS
from remote_worker import AshRemoteWorker
from agent_runtime import AshAgentRuntime
from test_agent_runtime import FakeAgent

class PremiumBuilderIntegrationTests(unittest.TestCase):
    def test_selected_premium_direction_is_in_actual_builder_prompt(self):
        worker=AshRemoteWorker.__new__(AshRemoteWorker)
        for name in DESIGN_PRESETS:
            prompt, meta=worker._builder_prompt("Make a real storefront",{"design_preset":name})
            self.assertIn("PREMIUM PRODUCT DESIGN BRIEF",prompt)
            self.assertEqual(meta["design_preset"],name)
            self.assertFalse(meta["component_libraries_installed"])
        with self.assertRaises(ValueError):
            worker._builder_prompt("Make a site",{"design_preset":"not-listed"})

    def test_plugin_tools_exposed_with_bounded_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent=FakeAgent()
            agent.plan={"steps":[{"tool":"plugins.catalog","args":{}}],
                        "answer_instruction":"show actual tools"}
            runtime=AshAgentRuntime(agent,pathlib.Path(tmp))
            result=runtime.run("list available plugins")
            self.assertTrue(result.ok)
            names=[p["name"] for p in result.evidence[0]["result"]["plugins"]]
            self.assertIn("world.usgs.earthquakes",names)
            self.assertIn("plugins.github.repository",names)

    def test_visio_style_diagram_is_bounded_mermaid_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=AshAgentRuntime(FakeAgent(),pathlib.Path(tmp))
            d=runtime._tool_diagram({"title":"Demo","nodes":[{"id":"Start","label":"Begin"},
                      {"id":"Finish","label":"Done"}],
                      "edges":[{"from":"Start","to":"Finish"}]})
            self.assertIn("Start --> Finish",d["diagram"])
            self.assertEqual(d["format"],"mermaid")
            self.assertFalse(d["rendered"])

if __name__=="__main__":
    unittest.main()
