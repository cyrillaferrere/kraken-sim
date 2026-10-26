"""Offline tests for Kraken sourced-report indicators and liquidity."""
import unittest
from collect_market_report import ASSETS, ema, rsi, atr, liquidity, indicators, candles


class MarketReportTests(unittest.TestCase):
    def test_only_four_assets(self):
        self.assertEqual(set(ASSETS), {"BTC", "ETH", "SOL", "XRP"})

    def test_ema_constant(self):
        self.assertAlmostEqual(ema([10.0] * 55, 20), 10)
        self.assertAlmostEqual(ema([10.0] * 55, 50), 10)

    def test_rsi_constant(self):
        self.assertEqual(rsi([10.0] * 60), 50)

    def test_rsi_rising(self):
        self.assertEqual(rsi([float(x) for x in range(1, 61)]), 100)

    def test_atr_constant(self):
        rows = [[i, 10, 11, 9, 10] for i in range(60)]
        self.assertAlmostEqual(atr(rows), 2)

    def test_last_unclosed_candle_excluded(self):
        rows = [[i, 10, 11, 9, 10] for i in range(55)]
        rows[-1][4] = 10000
        p = {"raw": {"result": {"PAIR": rows, "last": 1234}}}
        self.assertEqual(candles(p)[-1][4], 10)

    def test_depth_and_spread(self):
        p = {"raw": {"result": {"PAIR": {
            "asks": [["100.1", "10", "1"], ["101", "1", "1"]],
            "bids": [["99.9", "10", "1"], ["99", "1", "1"]]}}}}
        l = liquidity(p)
        self.assertAlmostEqual(l["spread_pct"], 0.2)
        self.assertAlmostEqual(l["ask_depth_usdc_within_0_5pct"], 1001)
        self.assertAlmostEqual(l["bid_depth_usdc_within_0_5pct"], 999)

    def test_high_low_last_30(self):
        rows = [[i, 10, 11+i, 9-i/10, 10] for i in range(60)]
        v = indicators(rows)
        self.assertEqual(v["high30"], 70)
        self.assertAlmostEqual(v["low30"], 3.1)


if __name__ == "__main__":
    unittest.main()
