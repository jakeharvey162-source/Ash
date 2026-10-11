import unittest
from visual_planner import flow_diagram

class VisualPlannerTests(unittest.TestCase):
    def test_generates_valid_mermaid_source_without_claiming_rendering(self):
        result=flow_diagram("Login", [{"id":"A","label":"Enter details"},
            {"id":"B","label":"Validate"}], [{"from":"A","to":"B"}])
        self.assertIn('A["Enter details"]',result["diagram"])
        self.assertIn("A --> B",result["diagram"])
        self.assertFalse(result["rendered"])
    def test_rejects_injected_node_id_or_unknown_edge(self):
        for nodes in [[{"id":"A;evil","label":"X"}],
                      [{"id":"A","label":"X"},{"id":"A","label":"Y"}]]:
            with self.assertRaises(ValueError):flow_diagram("T",nodes,[])
        with self.assertRaises(ValueError):
            flow_diagram("T",[{"id":"A","label":"X"}],[{"from":"A","to":"B"}])

if __name__=="__main__":
    unittest.main()
