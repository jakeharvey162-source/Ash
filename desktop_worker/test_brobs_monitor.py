import pathlib
import tempfile
import unittest
from brobs_monitor import analyze_statement
from agent_runtime import AshAgentRuntime
from test_agent_runtime import FakeAgent


class BrobsStatementTests(unittest.TestCase):
    def test_closed_trade_math_and_open_position_count(self):
        with tempfile.TemporaryDirectory() as directory:
            p=pathlib.Path(directory)/"trades.csv"
            p.write_text("symbol,side,status,realized_pnl\nEURUSD,buy,closed,20.50\nXAUUSD,sell,closed,-10\nEURUSD,buy,closed,0\nGBPUSD,sell,open,\n",encoding="utf-8")
            r=analyze_statement(p)
            self.assertEqual(r["closed_count"],3)
            self.assertEqual(r["open_count"],1)
            self.assertEqual(r["wins"],1)
            self.assertEqual(r["losses"],1)
            self.assertEqual(r["win_rate_percent"],33.33)
            self.assertEqual(r["net_realized_pnl"],"10.50")
            self.assertEqual(r["profit_factor"],2.05)
            self.assertIn("not_live_broker",r["source_type"])
            self.assertIn("No live prices",r["warning"])

    def test_rejects_missing_fields_and_nan(self):
        with tempfile.TemporaryDirectory() as directory:
            p=pathlib.Path(directory)/"trades.csv"
            p.write_text("symbol,status\nEURUSD,closed\n")
            with self.assertRaises(ValueError): analyze_statement(p)
            p.write_text("symbol,side,status,realized_pnl\nEURUSD,buy,closed,nan\n")
            with self.assertRaises(ValueError): analyze_statement(p)

    def test_agent_tool_cannot_read_outside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)/"workspace"
            root.mkdir()
            p=pathlib.Path(directory)/"other.csv"
            p.write_text("symbol,side,status,realized_pnl\nEURUSD,buy,closed,1\n")
            runtime=AshAgentRuntime(FakeAgent(),root)
            with self.assertRaises(ValueError):
                runtime._tool_brobs_journal({"path":"../other.csv"})

    def test_brobs_agent_read_only_tool_present(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime=AshAgentRuntime(FakeAgent(),pathlib.Path(directory))
            tool=runtime.tools.get("brobs.journal.review")
            self.assertFalse(tool.confirmation_required)
            self.assertNotIn("trade.execute",runtime.tools._tools)
