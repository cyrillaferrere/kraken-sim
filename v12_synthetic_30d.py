#!/usr/bin/env python3
"""Self-contained OFFLINE 30-calendar-day V1.2 simulation fixture.

SYNTHETIC markets, fixture Grok decisions, no API keys, no network, no cron,
no live market claims. All writes are confined to an external output folder.
"""
import copy
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path

from v12_autonomy import utc
from v12_grok_gateway import inspect_and_record
from v12_isolation import state_dir
from v12_learning import open_journal,verify,summarize
from v12_paper_engine import PaperEngine,canonical

START=datetime(2025,11,22,tzinfo=timezone.utc)

def start_market():
    data={}
    for asset,offset in (("BTC",0),("ETH",40),("XRP",75)):
        bars=[]
        for i in range(325):
            close=110+offset+0.55*i
            end=START-timedelta(days=324-i)
            bars.append({"end":end.isoformat(),"open":close-.2,"high":close+.7,
                         "low":close-.7,"close":close,"volume":100000,
                         "trades":50,"imputed":False})
        data[asset]=bars
    return {"status":"PAPER","source":"trusted-public-kraken",
            "observed_at":START.isoformat(),"daily_bars":data}

def market_at(base,day,hours=0):
    """A genuine point-in-time synthetic path; past bars never change."""
    result=copy.deepcopy(base)
    moment=START+timedelta(days=day,hours=hours)
    result["observed_at"]=moment.isoformat()
    for asset,bars in result["daily_bars"].items():
        origin=float(base["daily_bars"][asset][-1]["close"])
        for step in range(1,day+1):
            price=(origin*(1+.001*step) if step<15 or asset=="XRP"
                   else origin*.43*(1+.001*(step-15)))
            previous=float(bars[-1]["close"])
            bars.append({"end":(START+timedelta(days=step)).isoformat(),
                         "open":previous,"high":max(price,previous)*1.002,
                         "low":min(price,previous)*.998,"close":price,
                         "volume":100000,"trades":80,"imputed":False})
        close=float(bars[-1]["close"])
        result.setdefault("quotes",{})[asset]={
            "bid":round(close*.999,6),"ask":round(close*1.001,6),
            "as_of":moment.isoformat(),"min_order_usd":25}
    bid,ask=("0.9950","0.9970") if day>=20 else ("0.9995","1.0005")
    result["usdc_usd"]={"source":"trusted-public-kraken",
                        "bid":bid,"ask":ask,"as_of":moment.isoformat()}
    result["trades"]={}
    result["compliance"]={"regime":"UE/MiCA","quote":"USDC","spot_long_only":True,
                          "eligible":sorted(result["quotes"]),"insufficient_history":[]}
    return result

def proposal(market,identity,asset,qty,ttl=26*3600):
    created=utc(market["observed_at"])+timedelta(minutes=30)
    return {"decision_id":identity,"cycle_id":market["observed_at"],
            "strategy_id":"kraken-sim-v1.2","strategy_version":"V1.2",
            "candidate":"C","model_id":"grok-bot-proposal",
            "policy_version":"paper-policy-0",
            "market_data_asof":market["observed_at"],
            "created_at":created.isoformat(),"asset":asset,"action":"BUY",
            "quantity":qty,"order_type":"maker","max_slippage_pct":0.001,
            "reason":"Simulation fictive de la tendance EMA BTC et ETH de la strategie C",
            "confidence":0.70,"ttl_seconds":ttl}

def _run_30day_fixture(out):
    root=state_dir(out)
    if (root/"paper_engine_v12.db").exists() or (root/"dry_run_30d.json").exists():
        raise ValueError("DRY_RUN_OUTPUT_ALREADY_EXISTS: use a fresh external directory")
    root.mkdir(parents=True,exist_ok=True)
    e=PaperEngine(str(root))
    try:
        seed=start_market()
        first=market_at(seed,0)
        e.tick(first,first["observed_at"],slot="INITIAL")
        synthesis=e.build_synthesis(first,first["observed_at"])
        (root/"synthesis.json").write_text(canonical(synthesis)+"\n",encoding="utf8")
        moves=[proposal(first,"fixture-BTC-entry","BTC",9),
               proposal(first,"fixture-ETH-entry","ETH",8)]
        batch={"it_id":"it-synthetic-0","synthesis_sha256":synthesis["synthesis_sha256"],
               "decisions":moves}
        (root/"decision_fixture.json").write_text(canonical(batch)+"\n",encoding="utf8")
        accepted=e.admit_batch(batch,moves[0]["created_at"])
        if not all(x.get("accepted") for x in accepted):
            raise AssertionError("fixture failed admission "+str(accepted))
        duplicate=e.admit_batch(batch,moves[0]["created_at"])
        if not all(x.get("duplicate") for x in duplicate):
            raise AssertionError("duplicate synthetic IT was not idempotent")
        maker=market_at(seed,0,3)
        e.tick(maker,maker["observed_at"],slot="MAKER_FIRST")
        fallback=market_at(seed,0,5)
        e.tick(fallback,fallback["observed_at"],slot="FALLBACK_NEXT")
        unavailable_its=[]
        for day in range(1,31):
            daily=market_at(seed,day)
            if day in (4,7,18):
                absent=inspect_and_record(None,daily,e.wallet(),str(root),
                                          (utc(daily["observed_at"])+timedelta(minutes=30)).isoformat(),
                                          risk_state=e._risk(daily),phase="admission")
                unavailable_its.append({"day":day,"reason":absent["decision"]["reason"]})
            if day==9:
                syn=e.build_synthesis(daily,daily["observed_at"])
                short=proposal(daily,"fixture-expired","BTC",.1,ttl=60)
                verdict=e.admit_batch({"it_id":"it-short-expiry",
                    "synthesis_sha256":syn["synthesis_sha256"],"decisions":[short]},
                    short["created_at"])
                if not verdict[0].get("accepted"):
                    raise AssertionError("expiry fixture was not admitted "+str(verdict))
            tick=market_at(seed,day,3)
            e.tick(tick,tick["observed_at"],slot="SYNTHETIC_DAY_%02d"%day)
        report=e.report()
        log=open_journal(str(root))
        try:
            report["evidence"]=verify(log)
            report["evidence_counts"]=summarize(log)
        finally:log.close()
        report["synthetic_elapsed_days"]=30
        report["grok_it_absences"]=unavailable_its
        report["trade_api_used"]=False
        report["real_market_data_used"]=False
        report["provider_grok_called"]=False
        report["scope"]="DRY_RUN_ONLY_NOT_OFFICIAL_PERFORMANCE"
        if not (report["kill_count"]==1 and report["risk_lock"] and
                report["orders_by_status"].get("FILLED")==2 and
                report["orders_by_status"].get("EXPIRED")==1 and
                report["marks"]==33):
            raise AssertionError("30-day fixture coverage failed: "+str(report))
        (root/"dry_run_30d.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
        return report
    finally:e.close()


def run_30day_fixture(*args,**kwargs):
    """Fixture pré-V1.6.3 : plafond absolu 1 500 USDC désactivé (ratios conservés)."""
    from v12_autonomy import crypto_cap_disabled
    with crypto_cap_disabled():
        return _run_30day_fixture(*args,**kwargs)
