import unittest
from decimal import Decimal
from v12_execution import passive_crossing_qty,taker_estimate
class TestExecution(unittest.TestCase):
    def test_no_guaranteed_maker_fill(self):
        trades=[{"ts":1,"price":100,"qty":20},{"ts":3,"price":100,"qty":20}]
        self.assertEqual(passive_crossing_qty("buy",100,5,2,trades),0)
    def test_strict_crossing_and_partial(self):
        trades=[{"ts":1,"price":99,"qty":100},{"ts":3,"price":99,"qty":2}]
        self.assertEqual(passive_crossing_qty("buy",100,5,2,trades,participation="0.5"),Decimal("1.0"))
        self.assertEqual(passive_crossing_qty("sell",98,1,2,trades,participation="0.5"),Decimal("1"))
    def test_taker_buy_ask_sell_bid_with_slip_and_fee(self):
        buy=taker_estimate("buy",1,99,101,"0.008","0.001")
        sell=taker_estimate("sell",1,99,101,"0.008","0.001")
        self.assertEqual(buy["price"],Decimal("101.101"))
        self.assertEqual(sell["price"],Decimal("98.901"))
        self.assertLess(buy["cash_delta"],Decimal("-101"))
        self.assertLess(sell["cash_delta"],Decimal("99"))
    def test_gap_below_stop_executes_at_bid_not_stop(self):
        stop=Decimal("100")
        bid=Decimal("87")
        self.assertLess(bid,stop)
        sale=taker_estimate("sell",1,bid,89,"0.008","0.001")
        self.assertLess(sale["price"],stop)
if __name__=="__main__": unittest.main()
