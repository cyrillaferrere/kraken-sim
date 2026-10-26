"""Unit tests use synthetic fixtures ONLY. Never publish these numbers as portfolio data."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paper_executor import apply_cycle, RejectedCycle


def cycle(cid="cycle-a", ts="2026-10-25T12:00:00Z", decisions=None):
    return {"data_source": "grokbot_verified", "cycle_id": cid, "ts": ts,
            "initial_usdc": "1000", "prices": {"BTC": "100"}, "decisions": decisions if decisions is not None else []}


PENDING = {"data_source": None, "initial": None, "engine": "V2.0.0", "ux": "V2.0.0"}


class PaperExecutorTests(unittest.TestCase):
    def test_first_hold(self):
        s = apply_cycle(PENDING, cycle())
        self.assertEqual(s["equity"], 1000)
        self.assertEqual(s["cash"], 1000)
        self.assertEqual(s["cycles"], 1)
        self.assertEqual(s["orders"], [])

    def test_buy_sell_fees_and_mark_to_market(self):
        buy = cycle(decisions=[{"asset": "BTC", "side": "BUY", "qty": "2", "price": "100", "fee": "1"}])
        s = apply_cycle(PENDING, buy)
        self.assertEqual(s["cash"], 799)
        self.assertEqual(s["equity"], 999)
        self.assertEqual(s["fees"], 1)
        sell = cycle("cycle-b", "2026-10-25T13:00:00Z",
                     [{"asset": "BTC", "side": "SELL", "qty": "1", "price": "110", "fee": "2"}])
        sell["prices"] = {"BTC": "110"}
        t = apply_cycle(s, sell)
        self.assertEqual(t["cash"], 907)
        self.assertEqual(t["equity"], 1017)
        self.assertEqual(t["fees"], 3)
        self.assertEqual(t["positions"]["BTC"], 1)
        self.assertEqual(len(t["orders"]), 2)

    def test_reject_duplicate_cycle(self):
        s = apply_cycle(PENDING, cycle())
        with self.assertRaises(RejectedCycle):
            apply_cycle(s, cycle())

    def test_reject_replayed_older_cycle_id(self):
        a = apply_cycle(PENDING, cycle())
        b = apply_cycle(a, cycle("cycle-b", "2026-10-25T13:00:00Z"))
        with self.assertRaises(RejectedCycle):
            apply_cycle(b, cycle("cycle-a", "2026-10-25T14:00:00Z"))

    def test_reject_changed_initial(self):
        a = apply_cycle(PENDING, cycle())
        x = cycle("cycle-b", "2026-10-25T13:00:00Z")
        x["initial_usdc"] = "1001"
        with self.assertRaises(RejectedCycle):
            apply_cycle(a, x)

    def test_exact_internal_ledger(self):
        x = cycle(decisions=[{"asset": "BTC", "side": "BUY", "qty": "0.1", "price": "100", "fee": "0.01"}])
        a = apply_cycle(PENDING, x)
        self.assertEqual(a["_ledger"]["cash"], "989.99")
        self.assertEqual(a["_ledger"]["positions"]["BTC"], "0.1")

    def test_reject_out_of_order(self):
        s = apply_cycle(PENDING, cycle())
        with self.assertRaises(RejectedCycle):
            apply_cycle(s, cycle("cycle-b", "2026-10-25T11:00:00Z"))

    def test_reject_unverified(self):
        x = cycle()
        x["data_source"] = "test"
        with self.assertRaises(RejectedCycle):
            apply_cycle(PENDING, x)

    def test_reject_missing_capital(self):
        x = cycle()
        del x["initial_usdc"]
        with self.assertRaises(RejectedCycle):
            apply_cycle(PENDING, x)

    def test_reject_negative_cash(self):
        x = cycle(decisions=[{"asset": "BTC", "side": "BUY", "qty": "11", "price": "100", "fee": "1"}])
        with self.assertRaises(RejectedCycle):
            apply_cycle(PENDING, x)

    def test_reject_short_sale(self):
        x = cycle(decisions=[{"asset": "BTC", "side": "SELL", "qty": "1", "price": "100", "fee": "1"}])
        with self.assertRaises(RejectedCycle):
            apply_cycle(PENDING, x)

    def test_reject_missing_mark_price(self):
        s = apply_cycle(PENDING, cycle(decisions=[{"asset": "BTC", "side": "BUY", "qty": "1", "price": "100", "fee": "1"}]))
        x = cycle("cycle-b", "2026-10-25T13:00:00Z")
        x["prices"] = {"ETH": "10"}
        with self.assertRaises(RejectedCycle):
            apply_cycle(s, x)

    def test_reject_bad_summary(self):
        x = cycle()
        x["closed_trades_summary"] = {"source": "other", "net_wins": 1, "net_losses": 0, "net_flats": 0}
        with self.assertRaises(RejectedCycle):
            apply_cycle(PENDING, x)

    def test_reject_nan_and_negative_fee(self):
        for fee in ("NaN", "-1"):
            with self.subTest(fee=fee):
                x = cycle(decisions=[{"asset": "BTC", "side": "BUY", "qty": "1", "price": "100", "fee": fee}])
                with self.assertRaises(RejectedCycle):
                    apply_cycle(PENDING, x)


if __name__ == "__main__":
    unittest.main()
