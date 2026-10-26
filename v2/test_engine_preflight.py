"""Synthetic PAPER engine acceptance tests. Never publish test capital as market data."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import market_snapshot, execute_plan, MarketRejected, maker_fill
from plan_contract import InvalidPlan

NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def plan():
    return {"plan_id": "synthetic", "author": "kraken-bot-crypto",
            "created_at": "2026-10-25T11:00:00Z", "expires_at": "2026-10-26T11:00:00Z",
            "regime": "neutral", "targets": {"BTC": 0.2, "USDC": 0.8},
            "buy_zones": {}, "sell_zones": {}, "stop_loss_pct": {},
            "take_profit_pct": {}, "execution": {"style": "taker", "maker_timeout_min": 30},
            "max_orders_per_cycle": 3, "ack_kill_switch": False, "rationale": "test"}


def market():
    return {"source": "kraken_public", "ts": "2026-10-25T11:59:00Z",
            "quotes": {"BTC": {"pair": "BTC/USDC", "endpoint": "https://api.kraken.com/0/public/Depth",
                               "price": "100", "spread_pct": "0.1", "depth_usdc": "10000",
                               "maker_fee_pct": "0.2", "taker_fee_pct": "0.4",
                               "min_order_usdc": "1", "median_volume_30d_usdc": "10000000",
                               "eligible_eee": True,
                               "asks": [["100.1", "100"], ["101", "100"]],
                               "bids": [["99.9", "100"], ["99", "100"]]}}}


def state():
    return {"data_source": "grokbot_verified", "initial": 6605.10, "cash": 6605.10,
            "equity": 6605.10, "positions": {}, "fees": 0, "cycles": 0,
            "peak_equity": 6605.10, "cost_basis": {}, "orders": [], "history": [],
            "processed_cycle_ids": []}


class EngineTests(unittest.TestCase):
    def test_stale_data(self):
        m = market()
        m["ts"] = "2026-10-25T11:49:00Z"
        with self.assertRaisesRegex(MarketRejected, "STALE_DATA"):
            execute_plan(plan(), state(), m, now=NOW)

    def test_non_usdc(self):
        m = market()
        m["quotes"]["BTC"]["pair"] = "BTC/USDT"
        with self.assertRaises(MarketRejected):
            market_snapshot(m, NOW)

    def test_valid_plan_executes_paper(self):
        s = execute_plan(plan(), state(), market(), now=NOW)
        self.assertEqual(len(s["orders"]), 1)
        self.assertGreater(s["positions"]["BTC"], 0)
        self.assertGreater(s["fees"], 0)
        self.assertLess(s["cash"], 6605.10)

    def test_expired_no_buys(self):
        p = plan()
        p["expires_at"] = "2026-10-25T11:30:00Z"
        s = execute_plan(p, state(), market(), now=NOW)
        self.assertEqual(len(s["orders"]), 0)

    def test_kill_switch_300(self):
        s = state()
        s["cash"] = 6305.10
        s["peak_equity"] = 6605.10
        t = execute_plan(plan(), s, market(), now=NOW)
        self.assertTrue(t["kill_switch"])
        self.assertFalse(t["orders"])

    def test_spread_excludes_pair(self):
        m = market()
        m["quotes"]["BTC"]["spread_pct"] = "0.4"
        t = execute_plan(plan(), state(), m, now=NOW)
        self.assertEqual(t["rejections"][0]["reason"], "SPREAD")

    def test_insufficient_depth(self):
        m = market()
        m["quotes"]["BTC"]["asks"] = [["100.1", "1"]]
        t = execute_plan(plan(), state(), m, now=NOW)
        self.assertEqual(t["rejections"][0]["reason"], "INSUFFICIENT_DEPTH")

    def test_idempotence(self):
        first = execute_plan(plan(), state(), market(), now=NOW)
        second = execute_plan(plan(), first, market(), now=NOW)
        self.assertEqual(first, second)

    def test_maker_crossing(self):
        from decimal import Decimal
        self.assertFalse(maker_fill({}, "BUY", Decimal("100"), ["101"]))
        self.assertTrue(maker_fill({}, "BUY", Decimal("100"), ["99"]))

    def test_reject_overweight(self):
        p = plan()
        p["targets"] = {"BTC": 0.5, "USDC": 0.5}
        with self.assertRaises(InvalidPlan):
            execute_plan(p, state(), market(), now=NOW)

    def test_no_fake_capital(self):
        with self.assertRaises(Exception):
            execute_plan(plan(), {"data_source": None}, market(), now=NOW)


if __name__ == "__main__":
    unittest.main()
