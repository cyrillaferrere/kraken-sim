#!/usr/bin/env python3
"""Grok V1.2 PAPER decision firewall — pure preflight, never sends any order.

Grok proposes a decision backed by one of the PRE-REGISTERED candidate
strategies A/B/C/D. The trusted market-data collector and paper portfolio
are provided by the caller, NOT Grok. This code does not invoke any model,
write a state DB, place an order, or grant permission to run a trading cycle.

Order-execution limits must be checked AGAIN atomically at paper execution.
"""
import json
import math
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from pathlib import Path
from v12_accounting import d
from v12_indicators import sma
from v12_rebalance import bounded, retained_momentum_candidates, correlation_allowed
from v12_signals import (closed_candles,point_in_time_universe,
                         candidate_a,candidate_b,candidate_c,candidate_d)

ROOT=Path(__file__).resolve().parent
SPEC=json.loads((ROOT/"strategy"/"v1_2"/"params.json").read_text(encoding="utf8"))

def min_median_volume_usdc():
    """Seuil de volume médian quotidien 30 j XXX/USDC (Moteur V1.6.2 : 1 M).
    Rétrocompatible avec l'ancienne clé min_median_daily_usd_volume."""
    u=SPEC["UNIVERSE"]
    return float(u.get("min_median_daily_usdc_volume_30d",u.get("min_median_daily_usd_volume")))
def _risk_share(key):
    v=SPEC["RISK"].get(key)
    return None if v is None else d(str(v))

def asset_cost_usdc(portfolio,asset):
    p=portfolio.positions.get(asset)
    return d(0) if not p else d(p["qty"])*d(p["avg_cost"])

def max_crypto_exposure_usdc():
    """Moteur V1.6.3 : plafond d'exposition crypto en USDC (coût investi, frais
    inclus). None = pas de plafond absolu (seuls les ratios s'appliquent)."""
    v=SPEC["RISK"].get("max_crypto_exposure_usdc")
    return None if v is None else d(str(v))

from contextlib import contextmanager
@contextmanager
def crypto_cap_disabled():
    """Réservé aux fixtures synthétiques hors ligne antérieures à V1.6.3
    (scénarios dimensionnés en % de l'equity). Jamais utilisé par --cycle."""
    old=SPEC["RISK"].get("max_crypto_exposure_usdc")
    SPEC["RISK"]["max_crypto_exposure_usdc"]=None
    try:yield
    finally:SPEC["RISK"]["max_crypto_exposure_usdc"]=old

def invested_cost_usdc(portfolio):
    """Coût investi = somme qty x coût moyen (frais d'achat inclus), en USDC."""
    return sum((p["qty"]*p["avg_cost"] for p in portfolio.positions.values()),d(0))

ACTIONS=frozenset(("BUY","SELL","HOLD","CANCEL"))
REQUIRED=frozenset(("decision_id","cycle_id","strategy_id","strategy_version",
 "candidate","model_id","policy_version","market_data_asof","created_at",
 "asset","action","quantity","order_type","max_slippage_pct","reason",
 "confidence","ttl_seconds"))
STRATEGY_ID="kraken-sim-v1.2"

def utc(value):
    if not isinstance(value,str):
        raise ValueError("UTC timestamp string required")
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return dt.astimezone(timezone.utc)

def reasoned(decision,accepted,reason,max_weight=None):
    return {"status":"PREFLIGHT_ONLY_NOT_EXECUTED","decision_id":decision.get("decision_id"),
            "candidate":decision.get("candidate"),"accepted":accepted,
            "reason":reason,"max_strategy_weight":max_weight}

def _schema(decision,now,snapshot,risk_state,phase):
    if not isinstance(decision,dict) or set(decision)!=REQUIRED:
        raise ValueError("INVALID_DECISION_FIELDS")
    if any(not isinstance(decision[k],str) or not decision[k].strip() or len(decision[k])>256
           for k in ("decision_id","cycle_id","strategy_id","strategy_version",
                     "candidate","model_id","policy_version","market_data_asof",
                     "created_at","asset")):
        raise ValueError("INVALID_DECISION_IDENTIFIERS")
    if decision["strategy_id"]!=STRATEGY_ID or decision["strategy_version"]!="V1.2":
        raise ValueError("FOREIGN_STRATEGY")
    if (decision["policy_version"]!=risk_state.get("active_policy_version") or
        decision["model_id"]!=risk_state.get("authorized_model_id")):
        raise ValueError("UNAPPROVED_POLICY_OR_MODEL")
    if decision["candidate"] not in SPEC["CANDIDATES"]:
        raise ValueError("CANDIDATE_NOT_IN_FROZEN_V12")
    if decision["action"] not in ACTIONS:
        raise ValueError("UNKNOWN_ACTION")
    if decision["order_type"] not in ("maker","taker","none"):
        raise ValueError("ORDER_TYPE_NOT_SUPPORTED")
    if not isinstance(decision["reason"],str) or not 8<=len(decision["reason"])<=2000:
        raise ValueError("MISSING_REASON")
    if not isinstance(decision["ttl_seconds"],int) or isinstance(decision["ttl_seconds"],bool):
        raise ValueError("INVALID_TTL")
    limit=7*86400 if decision["candidate"]=="B" else 26*3600
    if not 1<=decision["ttl_seconds"]<=limit:
        raise ValueError("INVALID_TTL")
    for k,hi in (("confidence",1),("max_slippage_pct",0.01)):
        v=decision[k]
        if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) or not 0<=v<=hi:
            raise ValueError("INVALID_"+k.upper())
    qty=d(decision["quantity"])
    if qty<0:raise ValueError("NEGATIVE_QUANTITY")
    if decision["action"] in ("HOLD","CANCEL") and (qty!=0 or decision["order_type"]!="none"):
        raise ValueError("NONZERO_NONTRADE")
    if decision["action"] in ("BUY","SELL") and (qty<=0 or decision["order_type"]=="none"):
        raise ValueError("INVALID_TRADE_QUANTITY")
    created=utc(decision["created_at"])
    asof=utc(decision["market_data_asof"])
    observed=utc(snapshot["observed_at"] if phase=="admission" else snapshot.get("signal_asof",snapshot["observed_at"]))
    if created>now+timedelta(seconds=2):
        raise ValueError("FUTURE_DECISION")
    if now-created>timedelta(seconds=decision["ttl_seconds"]):
        raise ValueError("EXPIRED_DECISION")
    if asof!=observed or asof>created or observed>now+timedelta(seconds=2):
        raise ValueError("UNTRUSTED_MARKET_SNAPSHOT")
    return qty

SPREAD_GLOBAL_ASSETS=("BTC","ETH")

def wide_spread_assets(snapshot):
    """Moteur V1.6.4 : paires au spread > 0,3 % (exclues individuellement)."""
    out=set()
    for a,q in (snapshot.get("quotes") or {}).items():
        try:
            bid,ask=d(q["bid"]),d(q["ask"])
            if bid>0 and ask>=bid and (ask-bid)/((ask+bid)/2)>d("0.003"):out.add(a)
        except (KeyError,TypeError,ArithmeticError):pass
    return out

def _quotes(snapshot,now,portfolio,phase):
    if snapshot.get("status")!="PAPER" or snapshot.get("source")!="trusted-public-kraken":
        raise ValueError("UNTRUSTED_OR_LIVE_MARKET_SNAPSHOT")
    quotes=snapshot.get("quotes")
    if not isinstance(quotes,dict):
        raise ValueError("NO_TRUSTED_QUOTES")
    holdings=set(portfolio.positions)
    for asset in holdings:
        if asset not in quotes:
            raise ValueError("HELD_ASSET_PRICE_UNAVAILABLE")
    for a,q in quotes.items():
        if not isinstance(q,dict):
            raise ValueError("MALFORMED_QUOTES")
        quote_reference=utc(snapshot["observed_at"]) if phase=="admission" else now
        if quote_reference-utc(q["as_of"])>timedelta(minutes=5) or utc(q["as_of"])>quote_reference+timedelta(seconds=2):
            raise ValueError("STALE_QUOTES")
        bid,ask=d(q["bid"]),d(q["ask"])
        if bid<=0 or ask<bid:
            raise ValueError("BROKEN_BID_ASK")
        # V1.6.4 : seul un spread large sur BTC/ETH bloque globalement ; les
        # autres paires larges sont exclues individuellement (voir validate).
        if (ask-bid)/((ask+bid)/2)>d("0.003") and a in SPREAD_GLOBAL_ASSETS:
            raise ValueError("EXCESSIVE_SPREAD")
    return {a:d(q["bid"]) for a,q in quotes.items()}

def _bars(snapshot,asof):
    values=snapshot.get("daily_bars")
    if not isinstance(values,dict) or "BTC" not in values:
        raise ValueError("NO_KRAKEN_DAILY_BARS")
    result={}
    for asset,bars in values.items():
        if not isinstance(bars,list):
            raise ValueError("INVALID_BARS")
        arr=closed_candles(bars,asof)
        if arr:
            last=utc(arr[-1]["end"])
            if utc(asof)-last>timedelta(hours=26):
                raise ValueError("DAILY_CANDLE_TOO_OLD")
        result[asset]=arr
    if not result["BTC"]:
        raise ValueError("NO_CLOSED_BTC_BAR")
    return result

def _candidate_buy_weight(label,asset,market,portfolio,snapshot,asof):
    """Return allowed target weight, NOT a market order or a live forecast."""
    ps=SPEC["CANDIDATES"][label]
    btc=market["BTC"]
    holding=set(portfolio.positions)
    weekday=utc(asof).weekday()
    if label in ("B","D") and weekday!=0:
        raise ValueError("WEEKLY_ROTATION_ONLY_MONDAY_UTC")
    if label=="C":
        if asset not in ("BTC","ETH"):
            raise ValueError("C_BTC_ETH_ONLY")
        bars=market.get(asset,[])
        signal=candidate_c(bars,ps)
        if not signal.get("entry") or signal.get("exit"):
            raise ValueError("C_NO_ACTIVE_ENTRY_SIGNAL")
        if asset in holding and weekday!=0:
            raise ValueError("C_REBALANCE_ONLY_MONDAY")
        return float(signal["target_weight"])
    universe=point_in_time_universe(
        market,asof,
        min_history=int(SPEC["UNIVERSE"]["min_history_daily"]),
        min_daily_volume=min_median_volume_usdc(),
        max_assets=int(SPEC["UNIVERSE"]["max_assets"]))
    if asset not in universe:
        raise ValueError("OUTSIDE_POINT_IN_TIME_UNIVERSE")
    if label=="A":
        if asset in holding:
            raise ValueError("A_NO_REBALANCE_EXISTING_POSITIONS")
        signal=candidate_a(universe[asset],btc,ps)
        if not signal.get("entry"):
            raise ValueError("A_NO_DONCHIAN_ENTRY")
        if len(holding)>=int(ps["max_positions"]):
            raise ValueError("A_MAX_POSITIONS")
        return min(float(signal["target_weight"]),float(ps["max_per_asset"]))
    if label=="B":
        reg=candidate_b(btc,btc,ps)
        if reg.get("btc_momentum",0)<=0:
            raise ValueError("B_BTC_RISK_OFF")
        ranking=[]
        for a,bars in universe.items():
            sig=candidate_b(bars,btc,ps)
            if sig.get("eligible"):
                ranking.append((float(sig["score"]),a,float(sig["vol20"])))
        ranking.sort(key=lambda x:(-x[0],x[1]))
        names=retained_momentum_candidates([a for _,a,_ in ranking],holding,int(ps["k"]),int(ps["retention_extra_ranks"]))
        if asset not in names:
            raise ValueError("B_NOT_SELECTED_TOP_K_PLUS_TWO")
        if not names:
            raise ValueError("B_NO_ELIGIBLE_ASSETS")
        inverse={a:1/max(v,1e-9) for _,a,v in ranking if a in names}
        total=sum(inverse.values())
        weights={a:inverse[a]/total for a in names}
        sigma=sum(weights[a]*next(v for _,b,v in ranking if b==a) for a in names)
        scale=min(1.0,float(ps["target_vol"])/sigma) if sigma>0 else 0.0
        return float(bounded({a:weight*scale for a,weight in weights.items()},
                             float(ps["max_exposure"]),float(ps["max_per_asset"])).get(asset,0))
    # D uses the original V1.1 confluence indicators, scored point in time.
    ranked=[]
    for a,bars in universe.items():
        sig=candidate_d(bars,btc,ps)
        if sig.get("entry"):
            ranked.append((float(sig["score"]),a))
    ranked.sort(key=lambda x:(-x[0],x[1]))
    if asset not in [a for _,a in ranked[:int(ps["top"])]]:
        raise ValueError("D_NOT_IN_TOP_CONFIRMED")
    return float(ps["max_per_asset"])

def validate(decision,snapshot,portfolio,now=None,risk_state=None,phase="execution"):
    """Pure risk preflight. Engine owns risk_state; admission may use older quotes,
    execution MUST provide fresh quotes and repeat all applicable checks.
    No order or ledger is changed; direct caller is not a trusted engine.
    """
    now=utc(now) if isinstance(now,str) else (now or datetime.now(timezone.utc))
    if now.tzinfo is None:
        raise ValueError("timezone required")
    now=now.astimezone(timezone.utc)
    try:
        if phase not in ("admission","execution"):
            raise ValueError("INVALID_GATE_PHASE")
        if not isinstance(risk_state,dict) or risk_state.get("engine_controlled") is not True:
            raise ValueError("TRUSTED_ENGINE_RISK_STATE_REQUIRED")
        quantity=_schema(decision,now,snapshot,risk_state,phase)
        if risk_state.get("paused") is True and decision["action"]=="BUY":
            raise ValueError("MANUAL_PAUSE")
        if decision["action"]=="CANCEL":
            raise ValueError("CANCEL_REQUIRES_PENDING_ENGINE")
        # HOLD logs can be valid without market data, and should still be attributed.
        if decision["action"]=="HOLD":
            return reasoned(decision,True,"HOLD_LOGGED_NO_ORDER")
        prices=_quotes(snapshot,now,portfolio,phase)
        asset=decision["asset"]
        if asset not in snapshot["quotes"] or asset not in snapshot.get("daily_bars",{}):
            raise ValueError("ASSET_QUOTE_OR_HISTORY_MISSING")
        quote=snapshot["quotes"][asset]
        equity=portfolio.equity(prices)
        if equity<=0:raise ValueError("ZERO_EQUITY")
        current=portfolio.positions.get(asset)
        if decision["action"]=="SELL":
            reserved=d(risk_state.get("reserved_sell_quantities",{}).get(asset,0))
            if current is None or quantity+reserved>current["qty"]:
                raise ValueError("NO_SHORT_SELLING_OR_RESERVED")
            return reasoned(decision,True,"RISK_REDUCTION_PERMITTED")
        if asset in wide_spread_assets(snapshot):
            raise ValueError("PAIR_EXCLUDED_SPREAD")
        if risk_state.get("risk_lock") is True or now<utc(risk_state.get("cooldown_until","1970-01-01T00:00:00Z")):
            raise ValueError("RISK_LOCK_OR_COOLDOWN")
        peak=d(risk_state["equity_peak_usd"])
        if peak<equity:
            peak=equity
        if equity<=peak*(1-d(SPEC["RISK"]["peak_drawdown_kill"])):
            raise ValueError("KILL_SWITCH")
        bars=_bars(snapshot,decision["market_data_asof"])
        weight=_candidate_buy_weight(decision["candidate"],asset,bars,portfolio,snapshot,decision["market_data_asof"])
        if weight<=0:
            raise ValueError("STRATEGY_ZERO_TARGET_WEIGHT")
        ask=d(quote["ask"])
        base_slip=SPEC["COSTS"]["slippage"]["major" if asset in ("BTC","ETH") else "other"]
        slip=max(d(decision["max_slippage_pct"]),d(base_slip))
        fee=d(SPEC["COSTS"]["F2"]["taker"])
        # Risk checks assume worst allowed price and highest pre-registered fee.
        estimated=quantity*ask*(1+slip)*(1+fee)
        if estimated<max(d(SPEC["COMMON"]["min_order_usd"]),d(quote.get("min_order_usd",0))):
            raise ValueError("BELOW_MIN_NOTIONAL")
        if estimated>d(portfolio.cash)-d(risk_state.get("reserved_buy_usd",0)):
            raise ValueError("INSUFFICIENT_CASH_NO_LEVERAGE")
        now_value=(current["qty"]*prices[asset] if current else d(0))
        if (now_value+estimated)/equity>d(str(weight))+d("0.00000001"):
            raise ValueError("ABOVE_CANDIDATE_TARGET_WEIGHT")
        exposure=sum(p["qty"]*prices[a] for a,p in portfolio.positions.items())
        ceiling=min(d(SPEC["RISK"]["max_exposure"]),
                    d(SPEC["CANDIDATES"][decision["candidate"]]["max_exposure"]))
        if (exposure+estimated+d(risk_state.get("pending_exposure_usd",0)))/equity>ceiling+d("0.00000001"):
            raise ValueError("EXPOSURE_CAP")
        cap=max_crypto_exposure_usdc()
        if cap is not None and (invested_cost_usdc(portfolio)+estimated+
                d(risk_state.get("pending_exposure_usd",0)))>cap+d("0.00000001"):
            raise ValueError("CRYPTO_EXPOSURE_CAP_USDC")
        if cap is not None:
            buy_share=_risk_share("max_buy_share_per_cycle")
            if buy_share is not None and estimated>cap*buy_share+d("0.00000001"):
                raise ValueError("BUY_ABOVE_PER_CYCLE_SHARE")
            asset_share=_risk_share("max_per_asset_share")
            pend_asset=d(risk_state.get("pending_buy_usd_by_asset",{}).get(asset,0))
            if asset_share is not None and asset_cost_usdc(portfolio,asset)+pend_asset+estimated>cap*asset_share+d("0.00000001"):
                raise ValueError("ASSET_SHARE_CAP")
        # Candidate C intentionally excludes the cross-asset correlation veto (§6).
        if decision["candidate"]!="C":
            current_weights={a:float(p["qty"]*prices[a]/equity)
                             for a,p in portfolio.positions.items() if a!=asset}
            if not correlation_allowed(asset,float(estimated/equity),current_weights,bars,
                         window=int(SPEC["RISK"]["correlation_window_days"]),
                         threshold=float(SPEC["RISK"]["correlation_max"]),
                         max_group=float(SPEC["RISK"]["correlated_weight_max"])):
                raise ValueError("CORRELATED_GROUP_EXPOSURE_CAP")
        return reasoned(decision,True,"V12_STRATEGY_AND_RISK_PASSED",weight)
    except (ValueError,TypeError,KeyError,OverflowError,ArithmeticError,IndexError,AttributeError) as exc:
        return reasoned(decision if isinstance(decision,dict) else {},False,str(exc))
