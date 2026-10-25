import json, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import render_v12_page as r

REPORT = {"schema_version": 1, "mode": "INIT_CHECK_HOLD_ONLY", "engine_version": "V1.4",
  "strategy_version": "V1.2", "generated_at": "2026-10-25T21:57:34.557948+00:00",
  "data": {"pairs_quoted": 40, "pairs_valid": 38, "usdc_usd": {"bid": "0.9997", "ask": "0.9998"}},
  "excluded_pairs": {"CAP": {"reason": "SPREAD_TOO_WIDE", "spread": "0.00434"}},
  "signals": {"A": {"evaluated": 13, "entries": []}, "B": {"evaluated": 13, "entries": ["BTC", "ETH"]}},
  "guardrails": {"risk": {"max_exposure": 0.9}, "risk_lock": False, "engine_peak_usdc": "6605.10"},
  "decisions": [{"decision_id": "init-check-hold:abc", "accepted": True, "reason": "HOLD_LOGGED_NO_ORDER"}],
  "orders": 0, "fills": 0, "trades": 0, "quote_currency": "USDC", "equity_usdc": "6605.10", "cash_usdc": "6605.10",
  "positions": {}, "initial_capital_usdc": "6605.10",
  "benchmark": {"usdc_hold_usdc": "6605.10", "usdc_hold_return_pct": 0}, "api_keys_used": False}

class PageRender(unittest.TestCase):
    def test_state_real_values_and_nulls(self):
        s = r.build_state(json.loads(json.dumps(REPORT)))
        self.assertEqual(s["strategy_id"], "kraken-sim-v1.2"); self.assertEqual(s["environment"], "preprod")
        self.assertEqual(s["equity"], 6605.10); self.assertEqual(s["cash"], 6605.10)
        self.assertEqual(s["orders"], []); self.assertEqual(s["decisions"][0]["action"], "HOLD")
        self.assertIsNone(s["candidate_signals"]["C"]); self.assertIsNone(s["fees_paid_usdc"])
        self.assertIsNone(s["btc_hold_usdc"]); self.assertEqual(s["quote_currency"], "USDC")
        self.assertEqual(s["usdc_hold_usdc"], 6605.10); self.assertEqual(s["usdc_hold_return_pct"], 0)
        self.assertFalse([k for k in s if k.endswith("_usd")]); self.assertIn("BTC, ETH", s["candidate_signals"]["B"])
        self.assertEqual(s["cur_dd_pct"], 0.0)

    def test_rejects_other_modes(self):
        bad = dict(REPORT, mode="CYCLE")
        with self.assertRaises(ValueError): r.build_state(bad)
        with self.assertRaises(ValueError): r.build_state(dict(REPORT, strategy_version="V1.1"))
        with self.assertRaises(ValueError): r.build_state(dict(REPORT, quote_currency="USD"))

    def test_no_dollar_or_usd_label_for_portfolio_amounts(self):
        import re
        html = r.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('+" USDC"', html)
        # No "$" currency suffix/prefix next to amounts, no "USD" amount label.
        self.assertIsNone(re.search(r'" \$"|\$ ?\d|\d ?\$|en USD\b', html))
        for m in re.finditer(r'USD(?!C)', html):
            ctx = html[max(0, m.start() - 5):m.end() + 1]
            self.assertIn("USDC/USD", ctx, ctx)  # only the USDC/USD info rate

    def test_render_html(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cr.json"; p.write_text(json.dumps(REPORT))
            r.main(["--report", str(p), "--out", str(Path(d) / "v12")])
            html = (Path(d) / "v12" / "index.html").read_text()
            self.assertIn("PREPROD V1.2 PAPER", html); self.assertNotIn("__DATA__", html)
            self.assertNotIn("__STATE_SOURCE__", html); self.assertIn('"equity": 6605.1', html)
            self.assertTrue((Path(d) / "v12" / "public_state_v12.json").is_file())

if __name__ == "__main__":
    unittest.main()
