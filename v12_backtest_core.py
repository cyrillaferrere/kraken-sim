#!/usr/bin/env python3
"""V1.2 exploratory DAILY backtest engine for the frozen CSV dataset.
This is NOT the official walk-forward and MUST NOT be used for strategy approval.
Orders are PAPER only, with next-day maker and following-day taker fallback.
"""
import math
import statistics
from datetime import datetime
from decimal import Decimal
from v12_accounting import Portfolio
from v12_execution import taker_estimate
from v12_signals import (point_in_time_universe, candidate_a,
                         candidate_b, candidate_c, candidate_d)
from v12_indicators import atr, correlation_return, sma

def calendar_days(data):
    if "BTC" not in data: raise ValueError("BTC/USD dataset required")
    return sorted({b["end"] for b in data["BTC"]})

def _mark(portfolio, today, fallback):
    for asset, bar in today.items():
        fallback[asset]=float(bar["close"])
    return float(portfolio.equity(fallback))

def _cost(asset, costs):
    group="major" if asset in ("BTC","ETH") else "other"
    return float(costs["spread_half"][group]),float(costs["slippage"][group])

def run_experiment(data, label, pset, risk, costs, tier="F2", start=None, end=None, c0=6605.10):
    if label not in ("A","B","C","D"): raise ValueError("unknown candidate")
    fees=costs[tier]
    portfolio=Portfolio(c0); calendar=calendar_days(data)
    by_day={asset:{b["end"]:b for b in bars} for asset,bars in data.items()}
    last_bids={}; pending=[]; events=[]; curve=[]; entry_dates={}; history={a:[] for a in data}
    peak=float(c0); killed_until=-1; killed=False
    missed_makers=0; amount_traded=0.; roundtrips=0; buycount=0
    start_i=next((i for i,x in enumerate(calendar) if start is None or x>=start),len(calendar))
    end_i=next((i for i,x in enumerate(calendar) if end is not None and x>end),len(calendar))
    if start_i>=end_i: raise ValueError("backtest period has no daily candles")

    def trade(side, asset, qty, price, rate, when, reason, spread_slip=0):
        nonlocal amount_traded,roundtrips,buycount
        px=float(price); qty=float(qty)
        if qty<=0 or px<=0 or qty*px<25: return False
        if side=="buy":
            affordable=float(portfolio.cash)/(px*(1+float(rate)))
            qty=min(qty,affordable)
            if qty*px<25: return False
            was_held=asset in portfolio.positions
            portfolio.buy(asset,qty,px,rate); buycount+=1
            if not was_held:entry_dates[asset]=when
        else:
            position=portfolio.positions.get(asset)
            if position is None:return False
            qty=min(qty,float(position["qty"]))
            if qty*px<25 and qty < float(position["qty"]):return False
            portfolio.sell(asset,qty,px,rate)
            if asset not in portfolio.positions:
                roundtrips+=1
                entry_dates.pop(asset,None)
        amount_traded+=qty*px
        events.append({"day":when,"asset":asset,"side":side,"qty":qty,"price":px,
                       "fee_rate":float(rate),"reason":reason,"cost_model":spread_slip})
        return True

    for i,day in enumerate(calendar):
        if i>=end_i:break
        today={asset:bars[day] for asset,bars in by_day.items() if day in bars}
        for asset,bar in today.items(): history[asset].append(bar)
        # Decisions were made only at a PREVIOUS daily close.
        new_pending=[]
        for order in pending:
            asset=order["asset"]; bar=today.get(asset)
            if bar is None or bar.get("imputed"): # no actual market: no fill
                new_pending.append(order);continue
            age=i-order["from_i"]
            if age<1:
                new_pending.append(order);continue
            spread,slip=_cost(asset,costs)
            if order["urgent"]:
                px=float(bar["open"])*(1+(spread+slip*3)*(1 if order["side"]=="buy" else -1))
                trade(order["side"],asset,order["qty"],px,fees["taker"],day,order["reason"],spread+slip*3)
            elif age==1:
                limit=order["limit"]
                crossed=(float(bar["low"])<limit) if order["side"]=="buy" else (float(bar["high"])>limit)
                if crossed and bar["volume"]>0:
                    trade(order["side"],asset,order["qty"],limit,fees["maker"],day,order["reason"]+" maker")
                else:
                    missed_makers+=1
                    new_pending.append(order)
            else:
                px=float(bar["open"])*(1+(spread+slip)*(1 if order["side"]=="buy" else -1))
                trade(order["side"],asset,order["qty"],px,fees["taker"],day,order["reason"]+" fallback",spread+slip)
        pending=new_pending
        eq=_mark(portfolio,today,last_bids)
        if i>=start_i:
            peak=max(peak,eq)
            curve.append({"day":day,"equity":eq,"cash":float(portfolio.cash),
                          "exposure":1-float(portfolio.cash)/eq if eq else 0})
        if i<start_i or i<250 or "BTC" not in today or today["BTC"].get("imputed"):
            continue
        # Forbid any look-ahead: every indicator receives only bars with end <= day.
        btc=history["BTC"]
        # Peak-to-trough kill-switch: no minimum hold restriction, gaps may exceed threshold.
        if eq<=peak*(1-float(risk["peak_drawdown_kill"])) and not killed:
            killed=True;killed_until=i+int(risk["cooldown_days"])
            pending=[p for p in pending if p["side"]=="sell" and p["urgent"]]
            for asset,p in portfolio.positions.items():
                if asset not in [o["asset"] for o in pending]:
                    pending.append({"asset":asset,"side":"sell","qty":float(p["qty"]),
                                    "from_i":i,"urgent":True,"limit":0,"reason":"kill-switch"})
            continue
        if killed:
            if i<killed_until or len(btc)<200 or float(btc[-1]["close"])<=sma([b["close"] for b in btc],200):
                continue
            killed=False;peak=eq
        is_monday=datetime.fromisoformat(day).weekday()==0
        universe=point_in_time_universe(history,day)
        assets={"BTC":btc,"ETH":history.get("ETH",[])} if label=="C" else universe
        target={}; emergencies=set(); exits=set()
        for asset,position in portfolio.positions.items():
            bars=history.get(asset,[])
            if not bars:continue
            if label=="A":
                entered=entry_dates.get(asset,day)
                highest=max(float(b["close"]) for b in bars if b["end"]>=entered)
                signal=candidate_a(bars,btc,pset,highest_close_since_entry=highest)
                if signal.get("exit"):
                    exits.add(asset)
                    if float(bars[-1]["close"])<=highest-float(pset["atr_mult"])*atr(bars,20):emergencies.add(asset)
            elif label=="B":
                if len(bars)>20 and float(bars[-1]["close"])<=float(position["avg_cost"])-4*atr(bars,20):
                    exits.add(asset);emergencies.add(asset)
            elif label=="C":
                if candidate_c(bars,pset).get("exit"):exits.add(asset)
            else:
                sig=candidate_d(bars,btc,pset)
                if sig.get("exit"):exits.add(asset)
                entered=entry_dates.get(asset,day)
                high_close=max(float(b["close"]) for b in bars if b["end"]>=entered)
                if len(bars)>20 and float(bars[-1]["close"])<high_close-float(pset["atr_mult"])*atr(bars,20):
                    exits.add(asset);emergencies.add(asset)
        if label=="A":
            eligible=[]
            for a,bars in assets.items():
                if a in portfolio.positions or a in exits:continue
                sig=candidate_a(bars,btc,pset)
                if sig.get("entry"):eligible.append((sig["score"],a,sig["target_weight"]))
            eligible.sort(reverse=True)
            remaining=max(0,int(pset["max_positions"])-len(portfolio.positions))
            max_weight=float(pset["max_exposure"])
            present=sum(float(p["qty"])*last_bids[a]/eq for a,p in portfolio.positions.items())
            for _,a,w in eligible[:remaining]:
                new=min(w,max(0,max_weight-present))
                if new>0:target[a]=new;present+=new
        elif label=="B" and is_monday:
            eligible=[]
            for a,bars in assets.items():
                sig=candidate_b(bars,btc,pset)
                if sig.get("eligible"):eligible.append((sig["score"],a,max(sig["vol20"],1e-9)))
            eligible.sort(reverse=True)
            chosen=eligible[:int(pset["k"])]
            if chosen:
                inv={a:1/sigma for _,a,sigma in chosen}
                norm=sum(inv.values())
                weights={a:inv[a]/norm for a in inv}
                portfolio_vol=sum(weights[a]*sigma for _,a,sigma in chosen)
                scale=min(1,float(pset["target_vol"])/portfolio_vol) if portfolio_vol else 0
                target={a:min(float(pset["max_per_asset"]),weights[a]*scale) for a in weights}
        elif label=="C":
            for a,bars in assets.items():
                sig=candidate_c(bars,pset)
                if sig.get("entry") and (is_monday or a not in portfolio.positions):
                    target[a]=sig.get("target_weight",0)
                elif a in portfolio.positions and not sig.get("exit"):
                    target[a]=float(portfolio.positions[a]["qty"])*last_bids[a]/eq
        elif label=="D" and is_monday:
            ranked=[]
            for a,bars in assets.items():
                sig=candidate_d(bars,btc,pset)
                if sig.get("entry"):ranked.append((sig["score"],a))
            ranked.sort(reverse=True)
            for _,a in ranked[:int(pset["top"])]:
                if len(target)*float(pset["max_per_asset"])>=float(pset["max_exposure"])-1e-9:break
                target[a]=float(pset["max_per_asset"])
        # Existing positions never need a forced weekly rebalance for A.
        if label in ("B","D") and is_monday:
            exits.update(a for a in portfolio.positions if a not in target)
        pending_assets={p["asset"] for p in pending}
        for asset in exits:
            if asset in pending_assets or asset not in portfolio.positions:continue
            h=portfolio.positions[asset];half,_=_cost(asset,costs)
            pending.append({"asset":asset,"side":"sell","qty":float(h["qty"]),"from_i":i,
                            "urgent":asset in emergencies,"limit":last_bids[asset]*(1+half),
                            "reason":"stop" if asset in emergencies else "signal exit"})
            pending_assets.add(asset)
        for asset,weight in target.items():
            if asset in pending_assets or asset not in last_bids:continue
            current=(float(portfolio.positions[asset]["qty"])*last_bids[asset]/eq) if asset in portfolio.positions else 0.
            if weight-current<=max(float(pset.get("rebal_band",0.02)),0.02):continue
            qty=(weight-current)*eq/last_bids[asset]
            if qty*last_bids[asset]<25:continue
            spread,_=_cost(asset,costs)
            pending.append({"asset":asset,"side":"buy","qty":qty,"from_i":i,
                            "urgent":False,"limit":last_bids[asset]*(1-spread),
                            "reason":"signal entry"})
            pending_assets.add(asset)
    if not curve: raise ValueError("no valid sampled daily equity")
    vals=[x["equity"] for x in curve]
    first=float(c0);peakdd=first;mdd=0.;rets=[]
    for v in vals:
        peakdd=max(peakdd,v);mdd=max(mdd,1-v/peakdd)
    for a,b in zip(vals,vals[1:]):
        rets.append(b/a-1 if a else 0)
    sd=statistics.stdev(rets) if len(rets)>1 else 0
    sharpe=statistics.mean(rets)/sd*math.sqrt(365) if sd else None
    years=len(vals)/365
    endv=vals[-1]
    return {
        "candidate":label,"fee_scenario":tier,"status":"EXPERIMENTAL_NOT_OOS_VALIDATED",
        "start":curve[0]["day"],"end":curve[-1]["day"],"days":len(vals),
        "net_return":endv/first-1,"mdd":mdd,
        "cagr":(endv/first)**(1/years)-1 if years>=1 and endv>0 else None,
        "sharpe":sharpe,"fees_usd":float(portfolio.fees_paid),
        "trade_orders":len(events),"closed_roundtrips":roundtrips,
        "maker_nonfilled":missed_makers,"turnover_usd":amount_traded,
        "curve":curve,"orders":events,
    }
