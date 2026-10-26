#!/usr/bin/env python3
"""V1.2 pre-production INIT + CHECK, HOLD only, zero order (moteur V1.6.2).

Account currency: USDC (Moteur V1.6). Cash, equity, PnL, fees, peak and
positions are in USDC; quotes come from v12_kraken_public (XXX/USDC only,
UE/MiCA guard in v12_compliance.py).
1. Initialise the PAPER state if absent (6 605,10 USDC cash, peak 6 605,10, no
   trade). An existing USDC state is NEVER overwritten.
   Migration: a legacy USD state (no quote_currency) is re-initialised in USDC
   ONLY if it has 0 order, 0 fill and 0 position; the reset is logged in
   check_report.json ("migration") and appended to migration_log.json.
   Otherwise the init-check is REFUSED (USD_STATE_WITH_ACTIVITY_REFUSED).
2. Reads Kraken PUBLIC data, computes A/B/C/D signals, builds the synthesis,
   loads the engine guard rails, submits ONE HOLD decision to the gateway.
3. Asserts orders == 0 and fills == 0, THEN copies the working state into the
   state directory and writes check_report.json.
All work happens in a scratch copy; the state directory is only written after
the zero-order assertion. No API key, no Grok call, no real or PAPER order.
"""
import json
import shutil
import tempfile
from datetime import datetime,timezone
from pathlib import Path

from v12_autonomy import SPEC,STRATEGY_ID
from v12_isolation import state_dir
from v12_liquidity import monitor as liquidity_monitor

C0="6605.10"
QUOTE="USDC"
STATE_FILES=("paper_engine_v12.db","grok_paper_evidence_v12.db")
ROOT=Path(__file__).resolve().parent

class InitCheckRefused(RuntimeError):pass

def hold_decision(engine,synthesis,now):
    risk=engine._risk()
    return {"decision_id":"init-check-hold:"+synthesis["synthesis_sha256"][:16],
            "cycle_id":"init-check:"+synthesis["synthesis"]["asof"],
            "strategy_id":STRATEGY_ID,"strategy_version":"V1.2","candidate":"C",
            "model_id":risk["authorized_model_id"],"policy_version":risk["active_policy_version"],
            "market_data_asof":synthesis["synthesis"]["asof"],"created_at":now,
            "asset":"BTC","action":"HOLD","quantity":"0","order_type":"none",
            "max_slippage_pct":0,"reason":"Pre-production init-check: HOLD only, no order.",
            "confidence":0,"ttl_seconds":3600}

def submit_hold_only(engine,batch,now):
    """Gateway submission refusing by construction anything but HOLD/qty 0."""
    for dec in batch.get("decisions",[]):
        if (not isinstance(dec,dict) or dec.get("action")!="HOLD" or
            str(dec.get("quantity"))!="0" or dec.get("order_type")!="none"):
            raise InitCheckRefused("INIT_CHECK_ONLY_HOLD_ALLOWED")
    return engine.admit_batch(batch,now)

def count_orders(engine):
    orders=engine.conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    fills=engine.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
    return orders,fills

def migrate_usd_if_empty(work,now_iso):
    """Legacy USD -> USDC reset, only when the ledger is provably empty."""
    from v12_paper_engine import PaperEngine
    old=PaperEngine(str(work))
    try:
        if old.quote_currency==QUOTE:return None
        orders,fills=count_orders(old)
        positions=old._get("wallet")["positions"]
        info={"at":now_iso,"from":old.quote_currency,"to":QUOTE,
              "previous_cash":old._get("wallet")["cash"],"orders":orders,"fills":fills,
              "positions":len(positions)}
    finally:old.close()
    if orders or fills or positions:
        raise InitCheckRefused("USD_STATE_WITH_ACTIVITY_REFUSED")
    for name in STATE_FILES:
        if (work/name).exists():(work/name).unlink()
    info["action"]="REINITIALISED_USDC_C0_"+C0
    return info

def run(state,collector=None,clock=None,max_pairs=40):
    from v12_paper_engine import PaperEngine
    target=state_dir(str(state))
    target.mkdir(parents=True,exist_ok=True)
    existed=(target/STATE_FILES[0]).exists()
    if collector is None:
        from v12_kraken_public import collect
        collector=lambda:collect(max_pairs=max_pairs)
    with tempfile.TemporaryDirectory(prefix="v12initcheck") as tmp:
        work=Path(tmp)/"work"
        work.mkdir()
        for name in STATE_FILES:
            if (target/name).exists():shutil.copy2(target/name,work/name)
        migration=None
        if (work/STATE_FILES[0]).exists():
            migration=migrate_usd_if_empty(work,now_iso=datetime.now(timezone.utc).isoformat())
        engine=PaperEngine(str(work),c0=C0,quote_currency=QUOTE)  # creates wallet ONLY if absent
        if engine.quote_currency!=QUOTE:
            engine.close();raise InitCheckRefused("STATE_NOT_USDC")
        try:
            snapshot=collector()
            now=snapshot["observed_at"]
            tick=engine.tick(snapshot,now,slot="init-check:"+now)
            synth=None;decisions=[]
            if tick.get("status")=="DRY_RUN":
                synth=engine.build_synthesis(snapshot,now)
                batch={"it_id":"init-check:"+now,"synthesis_sha256":synth["synthesis_sha256"],
                       "decisions":[hold_decision(engine,synth,now)]}
                decisions=submit_hold_only(engine,batch,now)
            orders,fills=count_orders(engine)
            # HARD STOP: never persist a state that contains any order or fill.
            assert orders==0 and fills==0,"INIT_CHECK_ORDERS_MUST_BE_ZERO"
            rep=engine.report()
            sig=(synth or {}).get("synthesis",{}).get("signals",{})
            excluded=getattr(engine,"last_exclusions",{})
            wallet=rep["portfolio"]
            report={"schema_version":1,"mode":"INIT_CHECK_HOLD_ONLY",
              "engine_version":(ROOT/"VERSION_ENGINE_V12").read_text().strip(),
              "strategy_version":"V1.2","generated_at":datetime.now(timezone.utc).isoformat(),
              "state_initialized_now":(not existed) or bool(migration),
              "data":{"origin":snapshot.get("data_origin"),"observed_at":now,
                      "pairs_quoted":len(snapshot.get("quotes",{})),
                      "pairs_valid":len(snapshot.get("quotes",{}))-len(excluded),
                      "btc_daily_bars":len(snapshot.get("daily_bars",{}).get("BTC",[])),
                      "usdc_usd":snapshot.get("usdc_usd")},
              "excluded_pairs":excluded,
              "tick":{"status":tick.get("status"),"reason":tick.get("reason")},
              "signals":{k:{"evaluated":len(v),
                            "entries":[x["asset"] for x in v if x.get("entry") or x.get("eligible")]}
                         for k,v in sig.items()},
              "synthesis_sha256":(synth or {}).get("synthesis_sha256"),
              "guardrails":{"risk":SPEC["RISK"],"max_spread":str(engine.MAX_SPREAD),
                            "min_valid_pairs":engine.min_valid_pairs(len(snapshot.get("quotes",{}))),
                            "risk_lock":rep["risk_lock"],"kill_count":rep["kill_count"],
                            "engine_peak_usdc":rep["engine_peak_usd"]},
              "decisions":[{"decision_id":x.get("decision_id"),"accepted":x.get("accepted"),
                            "reason":x.get("reason")} for x in decisions],
              "orders":orders,"fills":fills,"trades":fills,
              "quote_currency":QUOTE,
              "valuation_method":snapshot.get("valuation_method"),
              "equity_usdc":tick.get("equity_usd") or wallet["cash"],
              "cash_usdc":wallet["cash"],"fees_paid_usdc":wallet["fees_paid"],
              "realized_pnl_usdc":wallet["realized_pnl"],"positions":wallet["positions"],
              "initial_capital_usdc":rep["initial_cash_usd"],
              "benchmark":{"usdc_hold_usdc":rep["initial_cash_usd"],"usdc_hold_return_pct":0},
              "migration":migration,
              "compliance":snapshot.get("compliance"),
              "liquidity_monitor":liquidity_monitor(engine.liquidity_metrics(),
                  (snapshot.get("liquidity") or {}).get("books"),now,
                  eligible_count=len((snapshot.get("compliance") or {}).get("eligible") or []) if snapshot.get("compliance") else None,
                  volumes=(snapshot.get("liquidity") or {}).get("median_volumes_usdc_30d")),
              "live_orders":0,"api_keys_used":False}
        finally:
            engine.close()
        if report["orders"]!=0 or report["fills"]!=0:
            raise InitCheckRefused("INIT_CHECK_ORDERS_MUST_BE_ZERO")
        for name in STATE_FILES:
            if (work/name).exists():shutil.copy2(work/name,target/name)
            elif migration and (target/name).exists():(target/name).unlink()
    if report.get("migration"):
        log=target/"migration_log.json"
        hist=json.loads(log.read_text(encoding="utf8")) if log.exists() else []
        hist.append(report["migration"])
        log.write_text(json.dumps(hist,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    (target/"check_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    return report
