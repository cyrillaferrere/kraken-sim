"""Moteur V1.6.2 : seuil 1 M USDC (médiane 30 j OHLC), contrôle Depth ±0,5 % x3, alerte."""
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

import v12_liquidity as L
from v12_autonomy import SPEC,min_median_volume_usdc

ROOT=Path(__file__).resolve().parents[1]

def book(bid="100",ask="100.1",bq="10",aq="10"):
    return L.book_from_snapshot({"bids":[[bid,bq]],"asks":[[ask,aq]]})

def candles(vols,close="2"):
    return [{"close":close,"volume":str(v),"imputed":False} for v in vols]

class TestThreshold(unittest.TestCase):
    def test_params_1m_and_compat(self):
        self.assertEqual(SPEC["UNIVERSE"]["min_median_daily_usdc_volume_30d"],1000000)
        self.assertNotIn("min_median_daily_usd_volume",SPEC["UNIVERSE"])
        self.assertEqual(min_median_volume_usdc(),1000000.0)
        self.assertEqual(SPEC["LIQUIDITY"]["max_spread"],0.003)
        self.assertEqual(SPEC["LIQUIDITY"]["rollback_min_median_daily_usdc_volume_30d"],5000000)
        self.assertFalse(SPEC["LIQUIDITY"]["rollback_automated"])
    def test_version(self):
        self.assertEqual((ROOT/"VERSION_ENGINE_V12").read_text().strip(),"V1.6.4")

class TestMedian(unittest.TestCase):
    def test_median_30d_uses_last_30_closed_bars_volume_x_close(self):
        vols=[10**9]*10+list(range(1,31))     # anciennes valeurs énormes hors fenêtre
        self.assertEqual(L.median_volume_usdc_30d(candles(vols)),31)  # médiane(1..30)=15.5 x 2
    def test_median_is_not_mean_spike_resistant(self):
        vols=[100000]*29+[10**12]
        self.assertEqual(L.median_volume_usdc_30d(candles(vols)),200000)
    def test_missing_data_is_null_not_zero(self):
        self.assertIsNone(L.median_volume_usdc_30d(candles([1]*29)))
        bad=candles([1]*30);bad[5]["volume"]=None
        self.assertIsNone(L.median_volume_usdc_30d(bad))
        imp=candles([1]*30);imp[-1]["imputed"]=True
        self.assertIsNone(L.median_volume_usdc_30d(imp))
        self.assertIsNone(L.median_volume_usdc_30d(None))
        s=L.book_summary(None)
        self.assertTrue(all(v is None for v in s.values()))
        m=L.monitor(None,None,"2026-10-26T00:00:00+00:00")
        for k in ("rejected_liquidity_orders","rejected_liquidity_pct","estimated_slippage_pct",
                  "median_spread_pct","rejection_reasons","orderbook_checks","eligible_pairs_count"):
            self.assertIsNone(m[k],k)

class TestDepth(unittest.TestCase):
    def test_parse_kraken_depth(self):
        res={"XBTUSDC":{"asks":[["101","1",1],["100.2","2",1]],"bids":[["99","1",1],["99.9","3",1]]}}
        b=L.parse_depth(res,"XBTUSDC")
        self.assertEqual(str(b["asks"][0][0]),"100.2");self.assertEqual(str(b["bids"][0][0]),"99.9")
        self.assertIsNone(L.parse_depth({"X":{"asks":[],"bids":[["1","1"]]}},"X"))
    def test_sufficient_depth_accepted(self):
        b=book(bq="10",aq="10")          # ~1000 USDC à chaque côté dans ±0,5 %
        r=L.check_order(b,"BUY","3")      # ~300 USDC, 3x = 900 <= 1001
        self.assertTrue(r["accepted"]);self.assertIsNone(r["reason"])
        self.assertEqual(r["slippage_pct"],0.0)
    def test_insufficient_depth_rejected(self):
        r=L.check_order(book(aq="10"),"BUY","4")   # 400 x3 = 1200 > 1001
        self.assertFalse(r["accepted"]);self.assertEqual(r["reason"],"INSUFFICIENT_DEPTH")
    def test_levels_outside_band_do_not_count(self):
        b=L.book_from_snapshot({"bids":[["100","0.1"],["90","1000"]],"asks":[["100.1","0.1"],["110","1000"]]})
        self.assertEqual(L.check_order(b,"SELL","1")["reason"],"INSUFFICIENT_DEPTH")
    def test_slippage_walks_the_book(self):
        b=L.book_from_snapshot({"bids":[["100","1"]],"asks":[["100","1"],["101","1"]]})
        r=L.check_order(b,"BUY","2")
        self.assertAlmostEqual(r["slippage_pct"],0.5)
    def test_missing_book_rejected_with_null_metrics(self):
        r=L.check_order(None,"BUY","1")
        self.assertEqual(r["reason"],"DEPTH_UNAVAILABLE");self.assertIsNone(r["slippage_pct"])

class TestAlert(unittest.TestCase):
    def run_n(self,ok,ko,slip=0.0):
        m=L.empty_metrics()
        for _ in range(ok):m=L.record(m,{"accepted":True,"slippage_pct":slip})
        for _ in range(ko):m=L.record(m,{"accepted":False,"reason":"INSUFFICIENT_DEPTH"})
        return m
    def test_no_alert_below_20_attempts(self):
        self.assertIsNone(L.evaluate_alert(self.run_n(10,9)))
    def test_alert_rejection_rate_above_5pct(self):
        a=L.evaluate_alert(self.run_n(18,2))
        self.assertEqual(a["code"],"LIQUIDITY_REVIEW");self.assertIn("REJECTION_RATE_ABOVE_5_PCT",a["reasons"])
        self.assertIn("5 M",a["fallback"])
    def test_exactly_5pct_no_alert(self):
        self.assertIsNone(L.evaluate_alert(self.run_n(19,1)))
    def test_alert_median_slippage(self):
        a=L.evaluate_alert(self.run_n(20,0,slip=0.2))
        self.assertEqual(a["reasons"],["MEDIAN_SLIPPAGE_ABOVE_0_15_PCT"])
        self.assertIsNone(L.evaluate_alert(self.run_n(20,0,slip=0.15)))
    def test_alert_logged(self):
        with self.assertLogs("kraken_sim.v12.liquidity","WARNING"):
            L.evaluate_alert(self.run_n(0,20))
    def test_monitor_dashboard_contract(self):
        m=L.monitor(self.run_n(18,2,slip=0.05),{"BTC":L.book_summary(book())},"t",eligible_count=1)
        for k in ("as_of","min_median_daily_volume_usdc","eligible_pairs_count","rejected_liquidity_orders",
                  "rejected_liquidity_pct","orderbook_checks","median_spread_pct","estimated_slippage_pct",
                  "rejection_reasons","rollback_policy"):
            self.assertIn(k,m)
        self.assertEqual(m["rejected_liquidity_pct"],10.0)
        self.assertEqual(m["rejection_reasons"],{"INSUFFICIENT_DEPTH":2})
        self.assertEqual(m["alert"]["code"],"LIQUIDITY_REVIEW")
        json.dumps(m,allow_nan=False)

class TestEngineGate(unittest.TestCase):
    def test_engine_rejects_order_with_insufficient_depth(self):
        from v12_paper_engine import PaperEngine
        from v12_accounting import Portfolio
        with tempfile.TemporaryDirectory() as tmp:
            e=PaperEngine(tmp,c0="1000",quote_currency="USDC")
            try:
                e.current_books={"BTC":{"bids":[["100","1"]],"asks":[["100.1","1"]]}}
                p=Portfolio("1000")
                with self.assertRaises(ValueError) as cm:
                    e._execute_taker(p,"x","BTC","BUY","5",{"BTC":{"bid":L.Decimal("100"),"ask":L.Decimal("100.1")}},
                                     datetime.now(timezone.utc))
                self.assertEqual(str(cm.exception),"INSUFFICIENT_DEPTH")
                m=e.liquidity_metrics()
                self.assertEqual(m["attempts"],1);self.assertEqual(m["rejections"],{"INSUFFICIENT_DEPTH":1})
                # sortie de sécurité forcée : jamais bloquée, non comptée
                e._liquidity_gate("BTC","SELL","50",forced=True)
                self.assertEqual(e.liquidity_metrics()["attempts"],1)
            finally:
                e.close()

if __name__=="__main__":unittest.main()
