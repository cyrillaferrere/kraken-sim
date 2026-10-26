"""No look-ahead for all four candidates, including emerging/delisting assets."""
import unittest
from datetime import datetime,timedelta,timezone
from v12_backtest_core import run_experiment
from v12_signals import point_in_time_universe

def series(n=350,offset=0,start=0):
    first=datetime(2025,1,1,tzinfo=timezone.utc)
    out=[]
    for i in range(start,n):
        close=150+offset+i*0.25
        out.append({"end":(first+timedelta(days=i+1)).isoformat(),
                    "open":close,"close":close,"high":close+0.2,
                    "low":close-0.2,"volume":100000,"imputed":False})
    return out

RISK={"peak_drawdown_kill":0.25,"cooldown_days":14,
      "correlation_window_days":60,"correlation_max":0.85,"correlated_weight_max":0.4}
COSTS={"F2":{"maker":0.004,"taker":0.008},
       "spread_half":{"major":0.0002,"other":0.0008},
       "slippage":{"major":0.0005,"other":0.0015},"forced_multiplier":3}
PARAMS={
"A":{"breakout_days":55,"exit_days":20,"atr_mult":3,"atr_period":20,
     "risk_per_entry":0.005,"max_per_asset":0.15,"max_exposure":0.8,"max_positions":8},
"B":{"momentum_days":90,"skip_days":7,"sma_days":100,
     "k":4,"target_vol":0.4,"max_per_asset":0.3,"max_exposure":0.9,
     "retention_extra_ranks":2,"stop_atr_mult":4},
"C":{"fast_ema":50,"slow_ema":200,"target_vol":0.3,
     "max_per_asset":0.5,"max_exposure":1,"rebal_band":0.05},
"D":{"btc_hysteresis_atr":0.15,"top":5,"atr_mult":3,
     "max_per_asset":0.2,"max_exposure":0.8}}
class TestNoLookaheadMulti(unittest.TestCase):
    def setUp(self):
        self.base={"BTC":series(),"ETH":series(offset=20),
                   "XRP":series(offset=40),"ADA":series(offset=80)}
        self.end=self.base["BTC"][329]["end"]
        self.start=self.base["BTC"][280]["end"]
    def test_future_candle_and_listing_must_not_change_past(self):
        truncated={a:[x for x in bars if x["end"]<=self.end] for a,bars in self.base.items()}
        full=dict(self.base,FUTURE=series(n=350,start=331,offset=500))
        for name in "ABCD":
            with self.subTest(candidate=name):
                params=PARAMS[name]
                first=run_experiment(truncated,name,params,RISK,COSTS,start=self.start,end=self.end)
                later=run_experiment(full,name,params,RISK,COSTS,start=self.start,end=self.end,
                                     metadata={"FUTURE":{"status":"delisted","delisted_at":full["FUTURE"][-1]["end"]}})
                self.assertEqual(first["curve"],later["curve"])
                self.assertEqual(first["orders"],later["orders"])
        before=point_in_time_universe(truncated,self.end)
        after=point_in_time_universe(full,self.end)
        self.assertEqual(before,after)
if __name__=="__main__":unittest.main()
