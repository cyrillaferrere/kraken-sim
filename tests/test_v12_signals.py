import unittest
from datetime import datetime,timedelta,timezone
from v12_signals import point_in_time_universe,closed_candles,candidate_a,candidate_b,candidate_c,candidate_d
from v12_indicators import atr,vol
BASE=datetime(2025,1,1,tzinfo=timezone.utc)
def candles(n=300,delta=1,offset=0):
    out=[]
    for i in range(n):
        px=100+offset+i*delta
        out.append({"end":(BASE+timedelta(days=i+1)).isoformat(),"high":px+0.25,
                    "low":max(0.01,px-1),"close":px,"open":px,"volume":100000})
    return out
class TestSignals(unittest.TestCase):
    def test_universe_cannot_peek_future(self):
        t=(BASE+timedelta(days=250)).isoformat()
        btc=candles()
        a={"BTC":btc,"ADA":candles(offset=80)}
        b=point_in_time_universe(a,t)
        self.assertEqual(set(b),{"BTC","ADA"})
        self.assertEqual(b,point_in_time_universe({"BTC":btc[:250],"ADA":a["ADA"][:250]},t))
        with self.assertRaises(ValueError):
            closed_candles([btc[0],btc[0]],t)
    def test_future_surge_has_no_effect(self):
        bars=candles()
        cut=(BASE+timedelta(days=250)).isoformat()
        prior=closed_candles(bars,cut)
        x=candidate_a(prior,prior,{"breakout_days":55,"exit_days":20,"atr_mult":3})
        bars[-1]["close"]=100000
        future=closed_candles(bars,cut)
        self.assertEqual(x,candidate_a(future,future,{"breakout_days":55,"exit_days":20,"atr_mult":3}))
    def test_a_b_c_are_positive_on_long_uptrend(self):
        bars=candles()
        self.assertTrue(candidate_a(bars,bars,{"breakout_days":55,"exit_days":20,"atr_mult":3})["entry"])
        self.assertTrue(candidate_b(bars,bars,{"momentum_days":90,"skip_days":7,"sma_days":100})["eligible"])
        self.assertTrue(candidate_c(bars,{"fast_ema":50,"slow_ema":200,"target_vol":0.3})["entry"])
        self.assertIn("entry",candidate_d(bars,bars,{"btc_hysteresis_atr":0.15}))
    def test_price_history_required(self):
        self.assertEqual(candidate_c(candles(30),{"fast_ema":50,"slow_ema":200,"target_vol":0.3})["reason"],"warmup")
if __name__=="__main__": unittest.main()
