"""Tests of the V2 plan contract. All prices and amounts are synthetic fixtures."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_contract import validate_plan, accept_or_keep, InvalidPlan, guardrails

NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)


def plan():
    return {"plan_id": "synthetic-plan", "author": "kraken-bot-crypto",
            "created_at": "2026-10-25T11:00:00Z", "expires_at": "2026-10-26T11:00:00Z",
            "regime": "neutral", "targets": {"BTC": 0.2, "USDC": 0.8},
            "buy_zones": {"BTC": ["1", "2"]}, "sell_zones": {"BTC": ["3", "4"]},
            "stop_loss_pct": {"BTC": 0.10}, "take_profit_pct": {},
            "max_orders_per_cycle": 3, "execution": {"style": "taker", "maker_timeout_min": 30},
            "ack_kill_switch": False, "rationale": "Synthetic fixture, never publish"}


class PlanTests(unittest.TestCase):
    def test_valid(self):
        self.assertFalse(validate_plan(plan(), NOW)["expired"])

    def test_expired_kept_as_expired(self):
        p = plan()
        p["expires_at"] = "2026-10-25T11:30:00Z"
        self.assertTrue(validate_plan(p, NOW)["expired"])

    def test_max_36_hours(self):
        p = plan()
        p["expires_at"] = "2026-10-27T11:00:00Z"
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)

    def test_reject_unsupported_asset(self):
        p = plan()
        p["targets"] = {"USDT": 0.5, "USDC": 0.5}
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)

    def test_reject_overweight(self):
        p = plan()
        p["targets"] = {"BTC": 0.41, "USDC": 0.59}
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)

    def test_reject_usdc_floor(self):
        p = plan()
        p["targets"] = {"BTC": 0.2, "USDC": 0.7}
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)

    def test_reject_bad_zone(self):
        p = plan()
        p["buy_zones"]["BTC"] = [3, 2]
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)

    def test_reject_missing_rationale(self):
        p = plan()
        p["rationale"] = ""
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)

    def test_invalid_keeps_previous(self):
        previous = validate_plan(plan(), NOW)
        p = plan()
        p["targets"] = {"USDT": 1}
        self.assertIs(accept_or_keep(p, previous, NOW), previous)

    def test_guardrails_loaded(self):
        self.assertEqual(guardrails()["kill_drawdown_usdc"], 300)


if __name__ == "__main__":
    unittest.main()
