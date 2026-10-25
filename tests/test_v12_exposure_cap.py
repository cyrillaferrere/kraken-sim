"""Moteur V1.6.3 : plafond d'exposition crypto 1 500 USDC (coût investi) et cycle PAPER."""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

import v12_autonomy as au
import v12_cycle as cy
from v12_accounting import Portfolio
from v12_paper_engine import PaperEngine
import copy
from test_v12_paper_engine_30d import market_day
from test_v12_autonomy import fixture

def wide_market():
    base,_=fixture()
    m=market_day(base,0)
    for a in ("SOL","ADA","DOT","LINK"):
        m["daily_bars"][a]=copy.deepcopy(m["daily_bars"]["XRP"])
        m["quotes"][a]=dict(m["quotes"]["XRP"])
    return m

def _init_state(td):
    e=PaperEngine(td,c0="6605.10",quote_currency="USDC");e.close()

class TestCapHelpers(unittest.TestCase):
    def test_param_and_basis(self):
        self.assertEqual(au.max_crypto_exposure_usdc(),Decimal("1500"))
        self.assertEqual(au.SPEC["RISK"]["crypto_exposure_basis"],"COST_INVESTED_INCL_FEES")
    def test_invested_cost_includes_fees(self):
        p=Portfolio("6605.10");p.buy("BTC","0.01","80000","0.008")
        self.assertEqual(au.invested_cost_usdc(p),Decimal("806.40"))
    def test_exposure_report(self):
        p=Portfolio("6605.10");p.buy("BTC","0.01","80000","0.008")
        x=cy.exposure(p,{"BTC":Decimal("90000")})
        self.assertEqual(x["invested_usdc"],806.4)
        self.assertEqual(x["market_value_usdc"],900.0)
        self.assertAlmostEqual(x["budget_remaining_usdc"],693.6)
        self.assertAlmostEqual(x["usdc_remaining"],6605.10-806.4)
    def test_missing_price_is_null(self):
        p=Portfolio("100");p.buy("ETH","0.01","3000","0")
        self.assertIsNone(cy.exposure(p,{})["market_value_usdc"])

class TestCycle(unittest.TestCase):
    def _run(self,weight):
        m=wide_market()
        with tempfile.TemporaryDirectory() as td:
            _init_state(td)
            w=lambda *a,**k:weight
            with mock.patch.object(au,"_candidate_buy_weight",w),mock.patch.object(cy,"_candidate_buy_weight",w):
                r=cy.run(td,collector=lambda:m)
            return r
    def test_refuses_without_state(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(cy.CycleRefused):cy.run(str(Path(td)/"none"),collector=lambda:{})
    def test_buys_capped_at_1500_and_keeps_usdc(self):
        r=self._run(0.3)
        self.assertGreater(len(r["cycle_fills"]),0)
        x=r["exposure"]
        self.assertLessEqual(x["invested_usdc"],1500.0)
        self.assertGreater(x["invested_usdc"],1000.0)
        self.assertAlmostEqual(x["usdc_remaining"]+x["invested_usdc"],6605.10,places=4)
        self.assertEqual(r["live_orders"],0);self.assertFalse(r["api_keys_used"])
        self.assertEqual(r["mode"],"PAPER_CYCLE")
        for f in r["cycle_fills"]:
            self.assertEqual(f["side"],"BUY");self.assertTrue(f["pair"].endswith("/USDC"))
    def test_no_signal_holds(self):
        def none(*a,**k):raise ValueError("NO_SIGNAL")
        m=wide_market()
        with tempfile.TemporaryDirectory() as td:
            _init_state(td)
            with mock.patch.object(cy,"_candidate_buy_weight",none):
                r=cy.run(td,collector=lambda:m)
        self.assertEqual(r["cycle_fills"],[])
        self.assertEqual(r["decisions"][0]["action"],"HOLD")
        self.assertEqual(r["exposure"]["invested_usdc"],0.0)

class TestGateCap(unittest.TestCase):
    def test_execution_gate_rejects_above_cap(self):
        m=wide_market()
        with tempfile.TemporaryDirectory() as td:
            _init_state(td)
            e=PaperEngine(td)
            try:
                e.tick(m,m["observed_at"],slot="s")
                s=e.build_synthesis(m,m["observed_at"])
                ask=Decimal(str(m["quotes"]["BTC"]["ask"]))
                qty=(Decimal("1600")/ask).quantize(Decimal("0.00000001"))
                dec=cy._base(e,s,m["observed_at"],"BTC","BUY",qty,"C","test plafond 1500 USDC")
                with mock.patch.object(au,"_candidate_buy_weight",lambda *a,**k:0.9):
                    v=au.validate(dec,m,e.wallet(),m["observed_at"],risk_state=e._risk(m),phase="admission")
                self.assertFalse(v["accepted"]);self.assertEqual(v["reason"],"CRYPTO_EXPOSURE_CAP_USDC")
            finally:e.close()

if __name__=="__main__":unittest.main()
