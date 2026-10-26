import unittest
from datetime import datetime,timedelta,timezone
from v12_baselines import baselines
FEES={"maker":0.004,"taker":0.008}
COSTS={"spread_half":{"major":0.0002,"other":0.0008},
       "slippage":{"major":0.0005,"other":0.0015}}
class TestBaselines(unittest.TestCase):
    def test_reference_cash_btc_and_rebalance_with_fees(self):
        first=datetime(2025,1,1,tzinfo=timezone.utc)
        data={}
        for a,off in (("BTC",0),("ETH",50),("XRP",20)):
            data[a]=[]
            for n in range(70):
                v=100+off+n*0.5
                data[a].append({"end":(first+timedelta(days=n)).isoformat(),
                                "open":v,"high":v+2,"low":v-2,"close":v,"volume":20000})
        period=data["BTC"][0]["end"],data["BTC"][-1]["end"]
        r=baselines(data,period,FEES,COSTS)
        self.assertEqual(r["CASH"]["net_return"],0)
        self.assertGreater(r["BTC"]["fees_usd"],0)
        self.assertGreater(len(r["EQUAL_BTC_ETH_XRP"]["orders"]),3)
        self.assertTrue(all(x["equity"]>0 for x in r["BTC"]["curve"]))
    def test_missing_pair_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"BASELINE_MISSING"):
            baselines({"BTC":[]},("2025-01-01","2025-02-01"),FEES,COSTS)
if __name__=="__main__":unittest.main()
