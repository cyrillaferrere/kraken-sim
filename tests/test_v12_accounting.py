import unittest
from decimal import Decimal
from v12_accounting import Portfolio
class TestAccounting(unittest.TestCase):
    def test_buy_sell_pnl_and_fees(self):
        p=Portfolio("6605.10")
        self.assertEqual(p.buy("BTC","1","100","0.004"),Decimal("0.400"))
        self.assertEqual(p.cash,Decimal("6504.700"))
        self.assertEqual(p.equity({"BTC":"100"}),Decimal("6604.700"))
        realized=p.sell("BTC","1","110","0.008")
        self.assertEqual(realized,Decimal("8.720"))
        self.assertEqual(p.cash,Decimal("6613.820"))
        self.assertEqual(p.fees_paid,Decimal("1.280"))
    def test_no_leverage_or_short(self):
        p=Portfolio("10")
        with self.assertRaises(ValueError): p.buy("BTC",1,100,0.008)
        with self.assertRaises(ValueError): p.sell("BTC",1,100,0.008)
    def test_fractional_position(self):
        p=Portfolio("1000")
        p.buy("ETH","2","100","0")
        p.sell("ETH","0.5","120","0")
        self.assertEqual(p.positions["ETH"]["qty"],Decimal("1.5"))
        self.assertEqual(p.equity({"ETH":"120"}),Decimal("1040.0"))
    def test_missing_bid_is_not_zero(self):
        p=Portfolio(100); p.buy("BTC",1,10,0)
        with self.assertRaises(ValueError): p.equity({})
if __name__=="__main__": unittest.main()
