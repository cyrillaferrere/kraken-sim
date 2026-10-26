"""Preflight tests; synthetic values, no live portfolio publication."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import market_snapshot, plan_status, MarketRejected

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def plan():
    return {"plan_id": "test-only", "created_at": "2026-10-26T11:00:00Z",
            "expires_at": "2026-10-27T11:00:00Z", "targets": {"BTC": 20, "USDC": 80},
            "buy_zones": {"BTC": [1, 2]}, "sell_zones": {"BTC": [3, 4]},
            "usdc_floor_pct": 20, "stop_loss_pct": {"BTC": 10}, "rationale": "test"}


def market():
    return {"source": "kraken_public", "ts": "2026-10-26T11:59:55Z",
            "quotes": {"BTC": {"pair": "BTC/USDC", "endpoint": "https://api.kraken.com/0/public/Ticker",
                               "price": "100", "spread_pct": "0.1", "depth_usdc": "3000",
                               "fee_rate_pct": "0.25"}}}


class EnginePreflightTests(unittest.TestCase):
    def test_reject_stale_market(self):
        x = market()
        x["ts"] = "2026-10-26T11:59:30Z"
        with self.assertRaises(MarketRejected):
            market_snapshot(x, NOW)

    def test_reject_usdt_pair(self):
        x = market()
        x["quotes"]["BTC"]["pair"] = "BTC/USDT"
        with self.assertRaises(MarketRejected):
            market_snapshot(x, NOW)

    def test_missing_initial_portfolio_is_hold(self):
        state = {"data_source": None, "initial": None}
        self.assertEqual(plan_status(plan(), state, market(), NOW)["status"], "HOLD")

    def test_ready_is_not_execution(self):
        state = {"data_source": "grokbot_verified", "initial": 1000, "cash": 1000,
                 "positions": {}, "peak_equity": 1000}
        self.assertEqual(plan_status(plan(), state, market(), NOW)["status"], "READY_FOR_REVIEW")

    def test_drawdown_guard(self):
        state = {"data_source": "grokbot_verified", "initial": 1000, "cash": 800,
                 "positions": {}, "peak_equity": 1000}
        self.assertEqual(plan_status(plan(), state, market(), NOW)["status"], "KILL")


if __name__ == "__main__":
    unittest.main()
