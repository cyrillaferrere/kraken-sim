"""V2 plan-contract tests. Synthetic data only, never production values."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_contract import validate_plan, accept_or_keep, InvalidPlan


NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def plan():
    return {"plan_id": "synthetic-plan", "created_at": "2026-10-26T11:00:00Z",
            "expires_at": "2026-10-27T11:00:00Z",
            "targets": {"BTC": 20, "USDC": 80},
            "buy_zones": {"BTC": ["1", "2"]},
            "sell_zones": {"BTC": ["3", "4"]},
            "usdc_floor_pct": 20, "stop_loss_pct": {"BTC": 10},
            "rationale": "Synthetic fixture, never publish"}


class PlanTests(unittest.TestCase):
    def test_valid(self):
        self.assertFalse(validate_plan(plan(), NOW)["expired"])

    def test_expired_kept_as_expired(self):
        p = plan()
        p["expires_at"] = "2026-10-26T11:30:00Z"
        self.assertTrue(validate_plan(p, NOW)["expired"])

    def test_max_36_hours(self):
        p = plan()
        p["expires_at"] = "2026-10-28T11:00:00Z"
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)

    def test_reject_unsupported_asset(self):
        p = plan()
        p["targets"] = {"USDT": 50}
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)

    def test_reject_overweight(self):
        p = plan()
        p["targets"] = {"BTC": 41, "USDC": 59}
        with self.assertRaises(InvalidPlan):
            validate_plan(p, NOW)

    def test_reject_usdc_floor(self):
        p = plan()
        p["usdc_floor_pct"] = 90
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
        p["targets"] = {"USDT": 100}
        self.assertIs(accept_or_keep(p, previous, NOW), previous)


if __name__ == "__main__":
    unittest.main()
