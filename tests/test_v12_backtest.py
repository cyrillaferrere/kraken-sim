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
    def test_stale_held_asset_fails_closed_instead_of_frozen_mark(self):
        data={"BTC":candles(),"ETH":candles(offset=25)[:302]}
        with self.assertRaisesRegex(ValueError,"HELD_ASSET_STALE"):
            run_experiment(data,"C",C,RISK,FEES,
                           start=data["BTC"][270]["end"],end=data["BTC"][310]["end"])
    def test_delisted_asset_forced_exit_with_slippage_penalty(self):
        data={"BTC":candles(),"ETH":candles(offset=25)[:302]}
        meta={"ETH":{"status":"delisted","delisted_at":data["BTC"][302]["end"]}}
        result=run_experiment(data,"C",C,RISK,FEES,metadata=meta,
                              start=data["BTC"][270]["end"],end=data["BTC"][310]["end"])
        self.assertTrue(any(x["reason"]=="DELIST_FORCED_LAST_PRINT" for x in result["orders"]))
        self.assertGreaterEqual(result["total_costs_usd"],result["fees_usd"])
        self.assertGreater(result["slippage_usd"],0)
    def test_maker_partial_and_next_day_taker(self):
        data={"BTC":candles(),"ETH":candles(offset=25)}
        for bars in data.values():
            for b in bars:
                b["low"]=b["close"]-3
                b["volume"]=1.0
        result=run_experiment(data,"C",C,RISK,FEES,
                              common={"maker_fill_participation_hypothesis":0.5},
                              start=data["BTC"][270]["end"],end=data["BTC"][300]["end"])
        kinds=[o["liquidity"] for o in result["orders"]]
        self.assertIn("maker",kinds)
        self.assertIn("taker",kinds)
        self.assertGreater(result["maker_nonfilled"],0)
        self.assertGreaterEqual(min(row["cash"] for row in result["curve"]),0)
    def test_requires_btc(self):
        with self.assertRaises(ValueError):
            run_experiment({"ETH":candles()},"C",C,RISK,FEES)
if __name__=="__main__":unittest.main()
