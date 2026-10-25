import unittest
from datetime import date,timedelta
from v12_liquidity_study import analyze,FIXED

def fixture(vol_btc=6000000,vol_eth=1500000,eur_rate=1.10):
    base=date(2026,8,1);rows=[]
    for i in range(32):
        day=(base+timedelta(days=i)).isoformat()
        for a,v in (("BTC",vol_btc),("ETH",vol_eth)):
            for q in ("USDC","USD","EUR"):
                rows.append({"asof":day,"asset":a,"quote":q,
                    "daily_volume_quote":v if q=="USDC" else 1000000,
                    "fx_to_usdc":eur_rate if q=="EUR" else 1,
                    "bid":100,"ask":100.1,"closed_daily_bars":250})
    return {"observations":rows}
class TestResearch(unittest.TestCase):
    def test_fixed_thresholds_do_not_mutate_strategy(self):
        r=analyze(fixture())
        self.assertEqual(r["evaluated_days"],3)
        self.assertEqual(r["mean_eligible_pairs"]["A_5m"],1)
        self.assertEqual(r["mean_eligible_pairs"]["B_2m"],1)
        self.assertEqual(r["mean_eligible_pairs"]["B_1m"],2)
        self.assertEqual(r["mean_eligible_pairs"]["C_global_5m"],1)
        self.assertFalse(r["execution_metrics_verified"])
        self.assertFalse(r["strategy_returns_verified"])
        self.assertEqual(r["decision"],"NO_SELECTION_PENDING_DEPTH_FILLS_AND_WALK_FORWARD")
        self.assertEqual(FIXED["fallback"],"A_5m")
    def test_no_future_bars_enter_historical_decision(self):
        doc=fixture()
        first=analyze(doc)["observations"][0]
        doc["observations"][-1]["daily_volume_quote"]=9999999999
        again=analyze(doc)["observations"][0]
        self.assertEqual(first,again)
    def test_c_requires_complete_cross_market_point_in_time(self):
        doc=fixture()
        doc["observations"]=[r for r in doc["observations"]
                             if not (r["asset"]=="ETH" and r["quote"]=="EUR" and r["asof"]=="2026-08-12")]
        r=analyze(doc)
        self.assertFalse(r["observations"][0]["assets"]["ETH"]["eligible"]["C_global_5m"])
        self.assertIsNone(r["observations"][0]["assets"]["ETH"]["global_median"])
    def test_spread_rejects_even_high_global_volume(self):
        doc=fixture()
        for row in doc["observations"]:
            if row["asset"]=="BTC" and row["quote"]=="USDC":
                row["ask"]=101
        r=analyze(doc)
        self.assertEqual(r["mean_eligible_pairs"]["A_5m"],0)
        self.assertEqual(r["mean_eligible_pairs"]["C_global_5m"],0)
    def test_missing_contiguous_history_not_imputed(self):
        doc=fixture()
        doc["observations"]=[r for r in doc["observations"] if r["asof"]!="2026-08-15"]
        self.assertEqual(analyze(doc)["evaluated_days"],0)
if __name__=="__main__":unittest.main()
