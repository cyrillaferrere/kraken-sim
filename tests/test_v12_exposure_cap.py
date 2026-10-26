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

_PATCH=None
def setUpModule():
    """Scénarios historiques V1.6.3/V1.6.4 dimensionnés pour un plafond de 1 500 USDC sans enveloppe initiale."""
    global _PATCH
    _PATCH=mock.patch.dict(au.SPEC["RISK"],{"max_crypto_exposure_usdc":1500,"initial_envelope_split":False})
    _PATCH.start()
def tearDownModule():
    _PATCH.stop()

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
        self.assertGreaterEqual(len(r["cycle_fills"]),2)  # plusieurs achats ≤ 375 USDC
        for f in r["cycle_fills"]:
            self.assertLessEqual(f["notional_usdc"]+float(f["fee_usdc"]),375.0+1e-6)
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

def widen(m,asset,pct="0.01"):
    q=m["quotes"][asset];mid=(Decimal(str(q["bid"]))+Decimal(str(q["ask"])))/2
    q["bid"]=str(mid*(1-Decimal(pct)/2));q["ask"]=str(mid*(1+Decimal(pct)/2))

class TestDiversificationV164(unittest.TestCase):
    def _validate(self,m,asset,usd,setup=None):
        with tempfile.TemporaryDirectory() as td:
            _init_state(td);e=PaperEngine(td)
            try:
                if setup:setup(e)
                e.tick(m,m["observed_at"],slot="s");s=e.build_synthesis(m,m["observed_at"])
                ask=Decimal(str(m["quotes"][asset]["ask"]))
                qty=(Decimal(usd)/ask/Decimal("1.01")).quantize(Decimal("0.00000001"))
                dec=cy._base(e,s,m["observed_at"],asset,"BUY",qty,"C","test V1.6.4")
                with mock.patch.object(au,"_candidate_buy_weight",lambda *a,**k:0.9):
                    return au.validate(dec,m,e.wallet(),m["observed_at"],risk_state=e._risk(m),phase="admission")
            finally:e.close()
    def test_params(self):
        self.assertEqual(au.SPEC["RISK"]["max_per_asset_share"],0.40)
        self.assertEqual(au.SPEC["RISK"]["max_buy_share_per_cycle"],0.25)
    def test_buy_above_375_rejected(self):
        v=self._validate(wide_market(),"ETH","400")
        self.assertEqual(v["reason"],"BUY_ABOVE_PER_CYCLE_SHARE",v)
    def test_buy_under_375_accepted(self):
        v=self._validate(wide_market(),"ETH","300")
        self.assertTrue(v["accepted"],v)
    def test_asset_share_blocks_new_buy_without_forced_sell(self):
        m=wide_market()
        p=Portfolio("6605.10");p.buy("BTC","0.0100","80000","0.008")
        self.assertGreater(au.asset_cost_usdc(p,"BTC"),Decimal("600"))
        m=wide_market()
        with tempfile.TemporaryDirectory() as td:
            _init_state(td);e=PaperEngine(td)
            try:
                e.tick(m,m["observed_at"],slot="s");s=e.build_synthesis(m,m["observed_at"])
                ask=Decimal(str(m["quotes"]["BTC"]["ask"]))
                dec=cy._base(e,s,m["observed_at"],"BTC","BUY",(Decimal("50")/ask).quantize(Decimal("0.00000001")),"C","test plafond par actif V1.6.4")
                rs=e._risk(m)
                with mock.patch.object(au,"_candidate_buy_weight",lambda *a,**k:0.9):
                    v=au.validate(dec,m,p,m["observed_at"],risk_state=rs,phase="admission")
            finally:e.close()
        self.assertEqual(v["reason"],"ASSET_SHARE_CAP",v)
        self.assertEqual(p.positions["BTC"]["qty"],Decimal("0.0100"))  # aucune vente forcée
    def test_cycle_caps_each_asset_at_600(self):
        r=TestCycle._run(self,0.5)
        by={}
        for f in r["cycle_fills"]:by[f["asset"]]=by.get(f["asset"],0)+f["notional_usdc"]+float(f["fee_usdc"])
        self.assertTrue(by)
        for v in by.values():self.assertLessEqual(v,600.0+1e-6)
    def test_wide_minor_pair_excluded_not_global(self):
        m=wide_market();widen(m,"SOL")
        self.assertIn("SOL",au.wide_spread_assets(m))
        self.assertTrue(self._validate(m,"ETH","300")["accepted"])
        self.assertEqual(self._validate(m,"SOL","100")["reason"],"PAIR_EXCLUDED_SPREAD")
    def test_wide_btc_still_blocks_globally(self):
        m=wide_market();widen(m,"BTC")
        with self.assertRaisesRegex(ValueError,"EXCESSIVE_SPREAD"):
            au._quotes(m,au.utc(m["observed_at"]),Portfolio("6605.10"),"admission")

if __name__=="__main__":unittest.main()
