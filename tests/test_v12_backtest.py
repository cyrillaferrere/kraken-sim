import unittest
from datetime import datetime,timedelta,timezone
from v12_backtest_core import run_experiment

def candles(n=330,offset=0):
    base=datetime(2025,1,1,tzinfo=timezone.utc)
    out=[]
    for i in range(n):
        close=100+offset+0.2*i
        out.append({"end":(base+timedelta(days=i+1)).isoformat(),
                    "open":close,"high":close+0.1,"low":close-0.1,
                    "close":close,"volume":100000,"imputed":False})
    return out
FEES={"F1":{"maker":0.0025,"taker":0.004},
      "F2":{"maker":0.004,"taker":0.008},
      "spread_half":{"major":0.0002,"other":0.0008},
      "slippage":{"major":0.0005,"other":0.0015}}
RISK={"peak_drawdown_kill":0.25,"cooldown_days":14}
C={"fast_ema":50,"slow_ema":200,"target_vol":0.3,"max_per_asset":0.5,"max_exposure":1,"rebal_band":0.05}
class TestExploratoryBacktest(unittest.TestCase):
    def test_c_uses_cash_and_is_reproducible_without_future(self):
        data={"BTC":candles(),"ETH":candles(offset=25)}
        cutoff=data["BTC"][310]["end"]
        start=data["BTC"][270]["end"]
        a=run_experiment(data,"C",C,RISK,FEES,start=start,end=cutoff)
        b=run_experiment({"BTC":data["BTC"][:311],"ETH":data["ETH"][:311]},
                         "C",C,RISK,FEES,start=start,end=cutoff)
        self.assertEqual(a["curve"],b["curve"])
        self.assertGreaterEqual(a["trade_orders"],1)
        self.assertLessEqual(min(v["cash"] for v in a["curve"]),6605.1)
        self.assertGreaterEqual(min(v["cash"] for v in a["curve"]),0)
        self.assertEqual(a["status"],"EXPERIMENTAL_NOT_OOS_VALIDATED")
    def test_requires_btc(self):
        with self.assertRaises(ValueError):
            run_experiment({"ETH":candles()},"C",C,RISK,FEES)
if __name__=="__main__":unittest.main()
