"""V1.4 engine: per-pair exclusion and HOLD-only --init-check (zero order)."""
import copy
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from test_v12_paper_engine_30d import market_day
from test_v12_autonomy import fixture
from v12_paper_engine import PaperEngine
import v12_init_check as ic

def wide_market(extra=("SOL","ADA","DOT","LINK","CAP","APR")):
    base,_=fixture()
    m=market_day(base,0)
    for a in extra:
        m["daily_bars"][a]=copy.deepcopy(m["daily_bars"]["XRP"])
        m["quotes"][a]=dict(m["quotes"]["XRP"])
    q=m["quotes"]["CAP"];mid=float(q["bid"])
    q["bid"]=round(mid*0.998,6);q["ask"]=round(mid*1.0021,6)   # ~0.41 %
    q=m["quotes"]["APR"];q["bid"]=round(mid*0.996,6);q["ask"]=round(mid*1.0038,6)  # ~0.78 %
    return m

class TestPairExclusion(unittest.TestCase):
    def test_wide_spread_pair_excluded_without_global_pause(self):
        m=wide_market()
        with tempfile.TemporaryDirectory() as td:
            e=PaperEngine(td)
            try:
                r=e.tick(m,m["observed_at"],slot="X")
                self.assertEqual(r["status"],"DRY_RUN")
                ex=[ev for ev in r["events"] if ev["action"]=="PAIRS_EXCLUDED_THIS_TICK"][0]["pairs"]
                self.assertEqual(set(ex),{"CAP","APR"})
                self.assertEqual(ex["CAP"]["reason"],"SPREAD_TOO_WIDE")
                s=e.build_synthesis(m,m["observed_at"])["synthesis"]
                self.assertIn("APR",s["excluded_pairs"])
                for k in ("A","B","D"):
                    self.assertNotIn("CAP",[x["asset"] for x in s["signals"][k]])
            finally:e.close()
    def test_btc_invalid_pauses(self):
        m=wide_market()
        m["quotes"]["BTC"]["ask"]=float(m["quotes"]["BTC"]["bid"])*1.01
        with tempfile.TemporaryDirectory() as td:
            e=PaperEngine(td)
            try:self.assertEqual(e.tick(m,m["observed_at"],slot="X")["status"],"PAUSED_MISSING_MARKET")
            finally:e.close()
    def test_too_few_valid_pairs_pauses(self):
        m=wide_market()
        for a in ("SOL","ADA","DOT","LINK","XRP"):
            m["quotes"][a]["bid"]=0
        with tempfile.TemporaryDirectory() as td:
            e=PaperEngine(td)
            try:
                r=e.tick(m,m["observed_at"],slot="X")
                self.assertEqual(r["status"],"PAUSED_MISSING_MARKET")
                self.assertIn("TOO_FEW_VALID_PAIRS",r["reason"])
            finally:e.close()
    def test_min_valid_pairs_documented(self):
        self.assertEqual(PaperEngine.min_valid_pairs(40),10)
        self.assertEqual(PaperEngine.min_valid_pairs(3),2)
    def test_held_pair_invalid_kept_and_logged(self):
        m=wide_market()
        with tempfile.TemporaryDirectory() as td:
            e=PaperEngine(td)
            try:
                w=e._get("wallet");w["positions"]={"CAP":{"qty":"1","avg_cost":"1"}}
                w["cash"]=str(float(w["cash"])-1)
                with e.transaction():e._put("wallet",w)
                r=e.tick(m,m["observed_at"],slot="X")
                self.assertEqual(r["status"],"DRY_RUN")
                self.assertIn("CAP",e.wallet().positions)
                ex=[ev for ev in r["events"] if ev["action"]=="PAIRS_EXCLUDED_THIS_TICK"][0]["pairs"]
                self.assertTrue(ex["CAP"]["held"])
            finally:e.close()

class TestInitCheck(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory();self.dir=Path(self.td.name)/"st"
        self.m=wide_market()
    def tearDown(self):self.td.cleanup()
    def run_check(self):
        return ic.run(str(self.dir),collector=lambda:copy.deepcopy(self.m))
    def test_init_check_zero_order_and_c0(self):
        r=self.run_check()
        self.assertEqual((r["orders"],r["fills"],r["trades"]),(0,0,0))
        self.assertTrue(r["state_initialized_now"])
        self.assertEqual(r["cash_usd"],"6605.10")
        self.assertEqual(r["guardrails"]["engine_peak_usd"],"6605.10")
        self.assertEqual(r["decisions"][0]["reason"],"HOLD_LOGGED_NO_ORDER")
        self.assertIn("CAP",r["excluded_pairs"])
        on_disk=json.loads((self.dir/"check_report.json").read_text())
        self.assertEqual(on_disk["orders"],0)
        self.assertTrue((self.dir/"paper_engine_v12.db").exists())
    def test_init_never_overwrites_existing_state(self):
        e=PaperEngine(str(self.dir),c0="6605.10")
        with e.transaction():e._put("wallet",dict(e._get("wallet"),cash="1234.5"))
        e.close()
        r=self.run_check()
        self.assertFalse(r["state_initialized_now"])
        self.assertEqual(r["cash_usd"],"1234.5")
    def test_only_hold_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            e=PaperEngine(td)
            try:
                for bad in ({"action":"BUY","quantity":"1","order_type":"taker"},
                            {"action":"SELL","quantity":"1","order_type":"maker"},
                            {"action":"HOLD","quantity":"1","order_type":"none"}):
                    with self.assertRaises(ic.InitCheckRefused):
                        ic.submit_hold_only(e,{"decisions":[bad]},self.m["observed_at"])
            finally:e.close()
    def test_assertion_blocks_state_write_if_order(self):
        orig=ic.count_orders
        ic.count_orders=lambda e:(1,0)
        try:
            with self.assertRaises(AssertionError):self.run_check()
        finally:ic.count_orders=orig
        self.assertFalse((self.dir/"check_report.json").exists())
        self.assertFalse((self.dir/"paper_engine_v12.db").exists())

if __name__=="__main__":unittest.main()
