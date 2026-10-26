#!/usr/bin/env python3
"""V1.2 PAPER trading cycle (Moteur V1.6.3) — SIMULATION ONLY.

GO explicite de Cyril (26/10/2026) pour des trades PAPER. Aucun ordre réel,
aucune clé Kraken : données PUBLIQUES uniquement, exécution par le moteur PAPER.

1. L'état existant (USDC) est OBLIGATOIRE et n'est jamais réinitialisé
   (absent ou non-USDC -> refus ; lancer d'abord --init-check).
2. Tick moteur (stops / ordres en attente), puis synthèse A/B/C/D.
3. Décisions MOTEUR déterministes (pas d'IT Grok) : pour chaque signal d'entrée
   dont le poids est validé par les règles pré-enregistrées, un BUY taker dont
   la taille est bornée par le budget crypto restant
   (RISK.max_crypto_exposure_usdc, base = coût investi frais inclus).
   Aucun signal -> une décision HOLD motivée.
4. Admission via la passerelle (mêmes garde-fous), puis tick d'exécution :
   contrôle Depth (V1.6.2), plafond 1 500 USDC re-vérifié à l'exécution.
Le travail se fait dans une copie ; l'état n'est écrit qu'en fin de cycle.
"""
import json
import shutil
import tempfile
from datetime import datetime,timezone
from decimal import Decimal,ROUND_DOWN
from pathlib import Path

from v12_accounting import d
from v12_autonomy import (SPEC,STRATEGY_ID,_bars,_candidate_buy_weight,
                          invested_cost_usdc,max_crypto_exposure_usdc,utc)
from v12_isolation import state_dir
from v12_liquidity import monitor as liquidity_monitor

QUOTE="USDC"
STATE_FILES=("paper_engine_v12.db","grok_paper_evidence_v12.db")
ROOT=Path(__file__).resolve().parent
PRIORITY=("C","A","D","B")
SIZING_MARGIN=d("1.03")  # >= réserve moteur (ask x 1,02) et >= slippage+frais max

class CycleRefused(RuntimeError):pass

def _base(engine,synth,now,asset,action,qty,candidate,reason):
    risk=engine._risk()
    slip=SPEC["COSTS"]["slippage"]["major" if asset in ("BTC","ETH") else "other"]
    return {"decision_id":f"cycle:{now}:{asset}:{action}","cycle_id":"cycle:"+now,
            "strategy_id":STRATEGY_ID,"strategy_version":"V1.2","candidate":candidate,
            "model_id":risk["authorized_model_id"],"policy_version":risk["active_policy_version"],
            "market_data_asof":synth["synthesis"]["asof"],"created_at":now,
            "asset":asset,"action":action,"quantity":str(qty),
            "order_type":"taker" if action!="HOLD" else "none",
            "max_slippage_pct":float(slip) if action!="HOLD" else 0,
            "reason":reason,"confidence":0.5 if action!="HOLD" else 0,"ttl_seconds":3600}

def exposure(portfolio,prices=None):
    cap=max_crypto_exposure_usdc()
    invested=invested_cost_usdc(portfolio)
    value=None
    if prices is not None:
        try:value=sum((p["qty"]*prices[a] for a,p in portfolio.positions.items()),d(0))
        except KeyError:value=None
    return {"max_crypto_exposure_usdc":None if cap is None else float(cap),
            "basis":SPEC["RISK"].get("crypto_exposure_basis","COST_INVESTED_INCL_FEES"),
            "invested_usdc":float(invested),
            "market_value_usdc":None if value is None else float(value),
            "budget_remaining_usdc":None if cap is None else float(max(cap-invested,d(0))),
            "usdc_remaining":float(portfolio.cash)}

def plan(engine,snapshot,synth,now):
    """Decisions engine-owned, sized on the remaining crypto budget."""
    p=engine.wallet()
    asof=synth["synthesis"]["asof"]
    quotes=snapshot["quotes"]
    prices={a:d(q["bid"]) for a,q in quotes.items()}
    equity=p.equity(prices)
    cap=max_crypto_exposure_usdc()
    remaining=(cap-invested_cost_usdc(p)) if cap is not None else equity
    bars=_bars(snapshot,asof)
    sig=synth["synthesis"]["signals"]
    fee=d(SPEC["COSTS"]["F2"]["taker"]);mn=d(SPEC["COMMON"]["min_order_usd"])
    decisions=[];skipped=[];seen=set(p.positions)
    for label in PRIORITY:
        for s in sig.get(label,[]):
            asset=s["asset"]
            if asset in seen or not (s.get("entry") or s.get("eligible")) or s.get("exit"):continue
            try:weight=d(str(_candidate_buy_weight(label,asset,bars,p,snapshot,asof)))
            except (ValueError,KeyError,TypeError) as exc:
                skipped.append({"candidate":label,"asset":asset,"reason":str(exc)});continue
            if asset not in quotes or weight<=0:continue
            ask=d(quotes[asset]["ask"])
            slip=d(SPEC["COSTS"]["slippage"]["major" if asset in ("BTC","ETH") else "other"])
            budget=min(weight*equity,remaining)
            factor=max(SIZING_MARGIN,(1+slip)*(1+fee))
            qty=(budget/(ask*factor)).quantize(Decimal("0.00000001"),rounding=ROUND_DOWN)
            if qty<=0 or qty*ask*(1+slip)*(1+fee)<mn:
                skipped.append({"candidate":label,"asset":asset,"reason":"BUDGET_BELOW_MIN_ORDER",
                                "budget_usdc":float(budget)});continue
            decisions.append(_base(engine,synth,now,asset,"BUY",qty,label,
                f"Moteur V1.6.3 : signal {label} {asset}, poids {float(weight):.4f}, "
                f"budget {float(budget):.2f} USDC (plafond crypto {cap} USDC, coût investi)."))
            remaining-=qty*ask*factor;seen.add(asset)
            if remaining<mn:break
        if len(decisions)>=10 or remaining<mn:break
    if not decisions:
        why="aucun signal d'entrée validé" if remaining>=mn else "budget crypto épuisé"
        decisions.append(_base(engine,synth,now,"BTC","HOLD",0,"C",
            f"Moteur V1.6.3 : HOLD, {why} ({len(skipped)} candidat(s) écarté(s))."))
    return decisions,skipped

def run(state,collector=None,max_pairs=40):
    from v12_paper_engine import PaperEngine
    target=state_dir(str(state))
    if not (target/STATE_FILES[0]).exists():
        raise CycleRefused("STATE_MISSING_RUN_INIT_CHECK_FIRST")
    if collector is None:
        from v12_kraken_public import collect
        collector=lambda:collect(max_pairs=max_pairs)
    with tempfile.TemporaryDirectory(prefix="v12cycle") as tmp:
        work=Path(tmp)/"work";work.mkdir()
        for name in STATE_FILES:
            if (target/name).exists():shutil.copy2(target/name,work/name)
        engine=PaperEngine(str(work),quote_currency=QUOTE)
        try:
            if engine.quote_currency!=QUOTE:raise CycleRefused("STATE_NOT_USDC")
            before=engine.conn.execute("SELECT COALESCE(MAX(id),0) FROM fills").fetchone()[0]
            c_before=engine._get("wallet")["cash"]
            snapshot=collector()
            now=snapshot["observed_at"]
            engine.gate_log=[]
            tick=engine.tick(snapshot,now,slot="cycle:"+now)
            synth=None;decisions=[];verdicts=[];skipped=[];exec_tick=None
            if tick.get("status")=="DRY_RUN":
                synth=engine.build_synthesis(snapshot,now)
                decisions,skipped=plan(engine,snapshot,synth,now)
                verdicts=engine.admit_batch({"it_id":"cycle:"+now,
                    "synthesis_sha256":synth["synthesis_sha256"],"decisions":decisions},now)
                exec_tick=engine.tick(snapshot,now,slot="cycle-exec:"+now)
            rows=engine.conn.execute("""SELECT decision_id,asset,side,qty,price,fee,liquidity,ts
                                        FROM fills WHERE id>? ORDER BY id""",(before,)).fetchall()
            gates={(g["asset"],g["side"]):g for g in engine.gate_log}
            fills=[]
            for did,asset,side,qty,price,fee,liq,ts in rows:
                g=gates.get((asset,side),{})
                fills.append({"decision_id":did,"asset":asset,"pair":asset+"/USDC","side":side,
                    "qty":qty,"price_usdc":price,"notional_usdc":float(d(qty)*d(price)),
                    "fee_usdc":fee,"liquidity":liq,"ts":ts,
                    "book_slippage_pct":g.get("slippage_pct"),
                    "depth_usdc_0_5pct":g.get("depth_usdc")})
            p=engine.wallet()
            prices={a:d(q["bid"]) for a,q in snapshot.get("quotes",{}).items()}
            expo=exposure(p,prices)
            cap=max_crypto_exposure_usdc()
            assert cap is None or d(str(expo["invested_usdc"]))<=cap+d("0.01"),"CRYPTO_CAP_BREACHED"
            fills_log=[{"asset":a,"side":s,"qty":q,"price_usdc":px,"fee_usdc":f,"liquidity":l,
                         "ts":ts,"status":"FILLED","decision_id":did}
                        for did,a,s,q,px,f,l,ts in engine.conn.execute(
                            """SELECT decision_id,asset,side,qty,price,fee,liquidity,ts
                               FROM fills ORDER BY id DESC LIMIT 200""").fetchall()][::-1]
            orders=engine.conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            allfills=engine.conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
            rep=engine.report()
            wallet=rep["portfolio"]
            positions={a:dict(v,value_usdc=str(d(v["qty"])*prices[a]) if a in prices else None)
                       for a,v in wallet["positions"].items()}
            sig=(synth or {}).get("synthesis",{}).get("signals",{})
            excluded=getattr(engine,"last_exclusions",{})
            equity=(exec_tick or tick).get("equity_usd") or wallet["cash"]
            report={"schema_version":1,"mode":"PAPER_CYCLE",
              "engine_version":(ROOT/"VERSION_ENGINE_V12").read_text().strip(),
              "strategy_version":"V1.2","generated_at":datetime.now(timezone.utc).isoformat(),
              "state_initialized_now":False,"cash_before_usdc":c_before,
              "data":{"origin":snapshot.get("data_origin"),"observed_at":now,
                      "pairs_quoted":len(snapshot.get("quotes",{})),
                      "pairs_valid":len(snapshot.get("quotes",{}))-len(excluded),
                      "btc_daily_bars":len(snapshot.get("daily_bars",{}).get("BTC",[])),
                      "usdc_usd":snapshot.get("usdc_usd")},
              "excluded_pairs":excluded,
              "tick":{"status":tick.get("status"),"reason":tick.get("reason"),
                      "events":tick.get("events")},
              "exec_tick":None if exec_tick is None else {"status":exec_tick.get("status"),
                      "events":exec_tick.get("events")},
              "signals":{k:{"evaluated":len(v),
                            "entries":[x["asset"] for x in v if x.get("entry") or x.get("eligible")]}
                         for k,v in sig.items()},
              "skipped_candidates":skipped,
              "synthesis_sha256":(synth or {}).get("synthesis_sha256"),
              "guardrails":{"risk":SPEC["RISK"],"max_spread":str(engine.MAX_SPREAD),
                            "min_valid_pairs":engine.min_valid_pairs(len(snapshot.get("quotes",{}))),
                            "risk_lock":rep["risk_lock"],"kill_count":rep["kill_count"],
                            "engine_peak_usdc":rep["engine_peak_usd"]},
              "decisions":[{"decision_id":x.get("decision_id"),"accepted":x.get("accepted"),
                            "reason":x.get("reason"),
                            "action":next((y["action"] for y in decisions if y["decision_id"]==x.get("decision_id")),None),
                            "asset":next((y["asset"] for y in decisions if y["decision_id"]==x.get("decision_id")),None),
                            "quantity":next((y["quantity"] for y in decisions if y["decision_id"]==x.get("decision_id")),None),
                            "explanation":next((y["reason"] for y in decisions if y["decision_id"]==x.get("decision_id")),None)}
                           for x in verdicts],
              "orders":orders,"fills":allfills,"trades":allfills,
              "cycle_fills":fills,"fills_log":fills_log,"cycle_orders":len(fills),
              "orders_by_status":rep["orders_by_status"],
              "quote_currency":QUOTE,"valuation_method":snapshot.get("valuation_method"),
              "equity_usdc":equity,"cash_usdc":wallet["cash"],
              "fees_paid_usdc":wallet["fees_paid"],"realized_pnl_usdc":wallet["realized_pnl"],
              "positions":positions,"exposure":expo,
              "initial_capital_usdc":rep["initial_cash_usd"],
              "benchmark":{"usdc_hold_usdc":rep["initial_cash_usd"],"usdc_hold_return_pct":0},
              "migration":None,"compliance":snapshot.get("compliance"),
              "liquidity_monitor":liquidity_monitor(engine.liquidity_metrics(),
                  (snapshot.get("liquidity") or {}).get("books"),now,
                  eligible_count=len((snapshot.get("compliance") or {}).get("eligible") or []) if snapshot.get("compliance") else None,
                  volumes=(snapshot.get("liquidity") or {}).get("median_volumes_usdc_30d")),
              "live_orders":0,"api_keys_used":False}
        finally:
            engine.close()
        for name in STATE_FILES:
            if (work/name).exists():shutil.copy2(work/name,target/name)
    (target/"check_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    return report
