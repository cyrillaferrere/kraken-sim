"""UI-only check: dashboard consumes provenance-safe engine liquidity stats."""
import unittest
from pathlib import Path
T=(Path(__file__).resolve().parents[1]/"dashboard_v12_cockpit_template.html").read_text()
class TestLiquidityUX(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(T.count("const D = __DATA__;"),1)
        self.assertIn('const VERSION_UX = "V1.2.3";',T)
        for id in ("liquidityMonitor","lqThreshold","lqEligible","lqRejected","lqDepth","lqSpread","lqSlippage","lqBookChecks","lqRejectionReasons","lqRollback"):
            self.assertIn('id="'+id+'"',T)
        self.assertIn("const m=obj(d.liquidity_monitor);",T)
        self.assertIn("m.orderbook_checks==null?",T)
        self.assertIn("renderLiquidity(d);",T)
    def test_no_engine_or_trading_action(self):
        self.assertNotIn("api.kraken.com/0/private/",T)
        self.assertNotIn("placeOrder(",T)
        self.assertIn("Pas de statistiques de refus publiées",T)
if __name__=="__main__":unittest.main()
