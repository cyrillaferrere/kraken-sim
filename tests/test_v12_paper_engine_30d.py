"""Accelerated synthetic 30-day OFFLINE run — NOT a performance backtest."""
import copy
import tempfile
import unittest
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from test_v12_autonomy import fixture
from v12_autonomy import utc
from v12_grok_gateway import inspect_and_record
from v12_learning import open_journal,verify,summarize
from v12_paper_engine import PaperEngine

def market_day(base,day,crash=False):
    source=copy.deepcopy(base)
    t=utc(base["observed_at"])+timedelta(days=day)
    moment=t.isoformat()
    source["observed_at"]=moment
    for asset,bars in source["daily_bars"].items():
        if day:
            origin=float(base["daily_bars"][asset][-1]["close"])
            ratio=(0.43 if crash and asset in ("BTC","ETH") else 1+0.001*day)
            last=origin*ratio
            for k in range(1,day+1):
                previous=bars[-1]["close"]
                px=origin*(0.43 if crash and k==day and asset in ("BTC","ETH") else 1+0.001*k)
                bars.append({"end":(utc(base["observed_at"])+timedelta(days=k)).isoformat(),
                             "open":previous,"high":max(previous,px)*1.002,
                             "low":min(previous,px)*.998,"close":px,
                             "volume":100000,"trades":80,"imputed":False})
        last=float(bars[-1]["close"])
        source["quotes"][asset]={"bid":round(last*.999,6),
                                 "ask":round(last*1.001,6),"as_of":moment,
                                 "min_order_usd":25}
    source["usdc_usd"]={"source":"trusted-public-kraken",
       "bid":"0.9950" if day>=20 else "0.9995",
       "ask":"1.0005","as_of":moment}
    return source

def at(market,hours=0):
    snap=copy.deepcopy(market)
    t=utc(market["observed_at"])+timedelta(hours=hours)
    snap["observed_at"]=t.isoformat()
    for v in snap["quotes"].values():
        v["as_of"]=t.isoformat()
    snap["usdc_usd"]["as_of"]=t.isoformat()
    return snap

def grok_decision(template,market,identity,asset,quantity,ttl=26*3600):
    proposal=copy.deepcopy(template)
    proposal.update(decision_id=identity,asset=asset,quantity=quantity,
                    ttl_seconds=ttl,created_at=(utc(market["observed_at"])+timedelta(minutes=30)).isoformat(),
                    market_data_asof=market["observed_at"],order_type="maker",action="BUY")
    return proposal

class TestPaperEngine30Days(unittest.TestCase):
    def test_complete_accelerated_30day_simulation_with_missing_its_duplicate_and_kill(self):
        base,model=fixture()
        with tempfile.TemporaryDirectory() as td:
            engine=PaperEngine(td)
            try:
                start=market_day(base,0)
                # Engine computes its own marks, independent of any Grok input.
                engine.tick(start,start["observed_at"],slot="START")
                syn=engine.build_synthesis(start,start["observed_at"])
                decisions=[
                    grok_decision(model,start,"it0-BTC","BTC",9),
                    grok_decision(model,start,"it0-ETH","ETH",8)]
                it={"it_id":"it-2025-11-22","synthesis_sha256":syn["synthesis_sha256"],
                    "decisions":decisions}
                decision_time=(utc(start["observed_at"])+timedelta(minutes=30)).isoformat()
                admission=engine.admit_batch(it,decision_time)
                self.assertEqual([x["accepted"] for x in admission],[True,True],admission)
                duplicate=engine.admit_batch(it,decision_time)
                self.assertTrue(all(x["duplicate"] for x in duplicate))
                first=engine.tick(at(start,3),(utc(start["observed_at"])+timedelta(hours=3)).isoformat(),
                                  slot="DAY00")
                self.assertEqual(sum(e["action"]=="MAKER_POSTED" for e in first["events"]),2)
                self.assertEqual(len(engine.wallet().positions),0)  # maker not magically filled
                # 30 historical calendar days are advanced in seconds on SYNTHETIC OHLC.
                for day in range(1,31):
                    m=market_day(base,day,crash=day>=15)
                    if day in (4,7,18):
                        # Missing Grok IT is recorded but cannot open any position.
                        inspect_and_record(None,m,engine.wallet(),td,
                                           (utc(m["observed_at"])+timedelta(minutes=30)).isoformat(),
                                           risk_state=engine._risk(m),phase="admission")
                    if day==9:
                        # Day 9 is a Monday; short TTL deliberately expires before cron.
                        syn=engine.build_synthesis(m,m["observed_at"])
                        exp=grok_decision(model,m,"short-ttl-BTC","BTC",0.1,ttl=60)
                        accepted=engine.admit_batch(
                            {"it_id":"it-short-ttl","synthesis_sha256":syn["synthesis_sha256"],
                             "decisions":[exp]},
                            exp["created_at"])
                        self.assertTrue(accepted[0]["accepted"],accepted)
                    snapshot=at(m,3)
                    now=snapshot["observed_at"]
                    report=engine.tick(snapshot,now,slot="DAY%02d"%day)
                    self.assertEqual(report["status"],"DRY_RUN")
                    same=engine.tick(snapshot,now,slot="DAY%02d"%day)
                    self.assertTrue(same["duplicate"])
                    self.assertEqual(same["status"],"DRY_RUN")
                report=engine.report()
                self.assertEqual(report["kind"],"SYNTHETIC_OFFLINE_PAPER_ONLY")
                self.assertEqual(report["marks"],32)
                self.assertTrue(report["risk_lock"])
                self.assertEqual(report["kill_count"],1)
                self.assertEqual(report["portfolio"]["positions"],{})
                self.assertEqual(report["orders_by_status"]["EXPIRED"],1)
                self.assertEqual(report["orders_by_status"]["FILLED"],2)
                self.assertGreaterEqual(report["fills_by_liquidity"]["taker"],4)
                self.assertEqual(Decimal(report["portfolio"]["cash"])>=0,True)
                self.assertNotEqual(report["last_mark"][2],None)
                db=open_journal(td)
                try:
                    self.assertTrue(verify(db)["verified"])
                    counts=summarize(db)
                    self.assertGreaterEqual(counts["outcomes"],4)
                    self.assertGreaterEqual(counts["rejected"],3)
                finally:db.close()
            finally:engine.close()
    def test_invalid_or_stale_quote_fails_closed(self):
        base,model=fixture()
        with tempfile.TemporaryDirectory() as td:
            engine=PaperEngine(td)
            try:
                m=market_day(base,0)
                s=at(m,3)
                s["quotes"]["BTC"]["as_of"]=m["observed_at"]
                response=engine.tick(s,s["observed_at"],slot="STALE")
                self.assertEqual(response["status"],"PAUSED_MISSING_MARKET")
                self.assertEqual(engine.report()["fills_by_liquidity"],{})
            finally:engine.close()
    def test_market_snapshot_cannot_disable_engine_kill_switch(self):
        base,_=fixture()
        with tempfile.TemporaryDirectory() as td:
            engine=PaperEngine(td)
            try:
                m=market_day(base,0)
                engine.tick(m,m["observed_at"],slot="START")
                with engine.transaction():
                    engine._put("equity_peak_usd","12000")
                m["risk_lock"]=False
                m["equity_peak_usd"]=0
                m["paused"]=False
                result=engine.tick(at(m,2),(utc(m["observed_at"])+timedelta(hours=2)).isoformat(),slot="RISK")
                self.assertTrue(result["risk_locked"])
                self.assertEqual(engine._get("kill_count"),1)
            finally:engine.close()
    def test_no_authority_to_replace_initial_usdc_benchmark(self):
        base,_=fixture()
        with tempfile.TemporaryDirectory() as td:
            engine=PaperEngine(td)
            try:
                m=market_day(base,0)
                engine.tick(m,m["observed_at"],slot="FIRST")
                locked=engine._get("usdc_initial_units")
                self.assertIsNotNone(locked)
                later=market_day(base,1)
                later["usdc_usd"]["bid"]="0.95"
                later["usdc_usd"]["ask"]="0.96"
                engine.tick(at(later,2),(utc(later["observed_at"])+timedelta(hours=2)).isoformat(),slot="NEXT")
                self.assertEqual(engine._get("usdc_initial_units"),locked)
            finally:engine.close()
if __name__=="__main__":
    unittest.main()
