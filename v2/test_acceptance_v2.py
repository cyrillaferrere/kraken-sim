"""Twelve CDC §10 acceptance scenarios. Fixtures are synthetic, never published."""
import copy
import os
import unittest
os.environ["V2_GUARDRAILS_PATH"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_guardrails_fixture.json")
from decimal import Decimal
from datetime import datetime, timezone

from engine import execute_plan, market_snapshot, MarketRejected, maker_fill
from plan_contract import validate_plan, accept_or_keep, InvalidPlan
from test_engine_preflight import plan, market, state, NOW


class AcceptanceCDC(unittest.TestCase):
    def test_01_valid_plan_orders_and_accounting(self):
        s = execute_plan(plan(), state(), market(), now=NOW)
        self.assertEqual(len(s["orders"]), 1)
        self.assertEqual(s["orders"][0]["side"], "BUY")
        self.assertAlmostEqual(s["cash"] + sum(s["position_values"].values()), s["equity"], places=2)
        self.assertGreater(s["fees"], 0)

    def test_02_invalid_weights_keeps_old_plan(self):
        previous = validate_plan(plan(), NOW)
        for targets in ({"BTC": 0.41, "USDC": 0.59}, {"BTC": 0.2, "USDC": 0.7}):
            candidate = plan()
            candidate["targets"] = targets
            self.assertIs(accept_or_keep(candidate, previous, NOW), previous)

    def test_03_expired_plan_no_buy_stop_still_sells(self):
        p = plan()
        p["expires_at"] = "2026-10-25T11:30:00Z"
        p["stop_loss_pct"] = {"BTC": 0.10}
        m = market()
        m["quotes"]["BTC"].update({"price": "80", "asks": [["80.1", "100"]],
                                    "bids": [["79.9", "100"]]})
        s = state()
        s.update({"cash": 6505.10, "positions": {"BTC": 1}, "cost_basis": {"BTC": "100"}})
        out = execute_plan(p, s, m, now=NOW)
        self.assertEqual([x["side"] for x in out["orders"]], ["SELL"])

    def test_04_cap_2000(self):
        s = state()
        s.update({"cash": 4615.10, "positions": {"BTC": 19.9},
                  "cost_basis": {"BTC": "1990"}, "peak_equity": 4814.10})
        m = market()
        m["quotes"]["BTC"].update({"price": "10", "asks": [["10.01", "1000"]],
                                    "bids": [["9.99", "1000"]]})
        out = execute_plan(plan(), s, m, now=NOW)
        self.assertIn("CAP_2000", [r["reason"] for r in out["rejections"]])

    def test_05_depth_and_spread_exclude_pair(self):
        m = market()
        m["quotes"]["BTC"]["asks"] = [["100.1", "1"]]
        self.assertIn("INSUFFICIENT_DEPTH", [r["reason"] for r in execute_plan(plan(), state(), m, now=NOW)["rejections"]])
        m = market()
        m["quotes"]["BTC"]["spread_pct"] = "0.31"
        self.assertIn("SPREAD", [r["reason"] for r in execute_plan(plan(), state(), m, now=NOW)["rejections"]])

    def test_06_kill_switch_300(self):
        s = state()
        s["cash"] = 6305.10
        out = execute_plan(plan(), s, market(), now=NOW)
        self.assertTrue(out["kill_switch"])
        self.assertEqual(out["orders"], [])

    def test_07_stale_over_ten_minutes(self):
        m = market()
        m["ts"] = "2026-10-25T11:49:00Z"
        with self.assertRaisesRegex(MarketRejected, "STALE_DATA"):
            execute_plan(plan(), state(), m, now=NOW)

    def test_08_replayed_cycle_is_idempotent(self):
        first = execute_plan(plan(), state(), market(), now=NOW)
        self.assertEqual(execute_plan(plan(), first, market(), now=NOW), first)

    def test_09_exception_preserves_input_state(self):
        previous = state()
        original = copy.deepcopy(previous)
        m = market()
        m["quotes"]["BTC"]["taker_fee_pct"] = None
        with self.assertRaises(MarketRejected):
            execute_plan(plan(), previous, m, now=NOW)
        self.assertEqual(previous, original)

    def test_10_usdt_non_usdc_and_eee_excluded(self):
        p = plan()
        p["targets"] = {"USDT": 0.2, "USDC": 0.8}
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)
        m = market()
        m["quotes"]["BTC"]["pair"] = "BTC/USDT"
        with self.assertRaises(MarketRejected):
            market_snapshot(m, NOW)
        m = market()
        m["quotes"]["BTC"]["eligible_eee"] = False
        self.assertIn("INELIGIBLE", [r["reason"] for r in execute_plan(plan(), state(), m, now=NOW)["rejections"]])

    def test_11_maker_crosses_only_inside_timeout(self):
        placed = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
        self.assertFalse(maker_fill({}, "BUY", Decimal("100"), [{"ts": "2026-10-25T12:31:00Z", "price": "99"}], placed_at=placed))
        self.assertFalse(maker_fill({}, "BUY", Decimal("100"), [{"ts": "2026-10-25T12:01:00Z", "price": "101"}], placed_at=placed))
        self.assertTrue(maker_fill({}, "BUY", Decimal("100"), [{"ts": "2026-10-25T12:01:00Z", "price": "99"}], placed_at=placed))

    def test_12_nonzero_fees_and_taker_slippage(self):
        out = execute_plan(plan(), state(), market(), now=NOW)
        self.assertGreater(out["orders"][0]["fee"], 0)
        self.assertGreater(out["orders"][0]["price"], 100)
        self.assertGreater(out["fees"], 0)


if __name__ == "__main__":
    unittest.main()
