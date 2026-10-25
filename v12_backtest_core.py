#!/usr/bin/env python3
"""Daily OFFLINE simulation — hypothesis testing, never live trading.
All signals see only closed candles. Orders execute J+1 or J+2. DATASETS MUST
be certified before results qualify as official walk-forward.
"""
import math
import statistics
from datetime import datetime
from v12_accounting import Portfolio
from v12_indicators import atr, sma
from v12_rebalance import (bounded,rebalance_actions,retained_momentum_candidates,
                           correlation_allowed)
from v12_signals import (point_in_time_universe,candidate_a,candidate_b,
                         candidate_c,candidate_d,usable_signal_window)

def calendar_days(data):
    if "BTC" not in data:
        raise ValueError("BTC/USD dataset required")
    return sorted({b["end"] for b in data["BTC"]})

def _cost(asset,costs):
    group="major" if asset in ("BTC","ETH") else "other"
    return float(costs["spread_half"][group]),float(costs["slippage"][group])

def _drawdown(series,initial):
    high=initial; mdd=0.0; duration=0;longest=0
    for equity in series:
        high=max(high,equity)
        underwater=equity<high
        duration=duration+1 if underwater else 0
        longest=max(longest,duration)
        mdd=min(mdd,equity/high-1)
    return mdd,longest

def _report(curve,events,c0,fees,costs_by_type,nonfilled,kill_count,roundtrips):
    values=[float(x["equity"]) for x in curve]
    ret=values[-1]/float(c0)-1
    mdd,dd_duration=_drawdown(values,c0)
    returns=[b/a-1 for a,b in zip([float(c0)]+values[:-1],values) if a>0]
    std=statistics.stdev(returns) if len(returns)>1 else 0.0
    mean=statistics.mean(returns) if returns else 0.0
    downside=math.sqrt(sum(min(0,x)**2 for x in returns)/len(returns)) if returns else 0.0
    n=len(values)
    cagr=(values[-1]/c0)**(365/n)-1 if values[-1]>0 else -1
    cash_days=sum(float(x["cash"])>=float(x["equity"])-0.000001 for x in curve)
    cost=sum(costs_by_type.values())+float(fees)
    gross=values[-1]-float(c0)+cost
    return dict(net_return=ret,mdd=abs(mdd),max_drawdown_signed=mdd,
                dd_duration_days=dd_duration,cagr=cagr,
                sharpe=(mean/std*math.sqrt(365)) if std else None,
                sortino=(mean/downside*math.sqrt(365)) if downside else None,
                calmar=(cagr/abs(mdd)) if mdd else None,
                cash_days=cash_days,fees_usd=float(fees),
                spread_usd=costs_by_type["spread"],slippage_usd=costs_by_type["slippage"],
                total_costs_usd=cost,gross_profit_usd=gross,
                trade_orders=len(events),closed_roundtrips=roundtrips,
                maker_nonfilled=nonfilled,kill_switch_count=kill_count)

def run_experiment(data,label,pset,risk,costs,tier="F2",start=None,end=None,
                   c0=6605.10,metadata=None,common=None,warmup=250):
    """Isolated PAPER backtest (not official OOS until verified walk-forward).
    metadata: asset->{status:'active'|'delisted',delisted_at: UTC ISO if relevant}.
    Missing held-asset prices FAIL CLOSED, not frozen at a previous close.
    """
    if label not in ("A","B","C","D"):
        raise ValueError("unknown candidate")
    if tier not in ("F1","F2"): raise ValueError("unknown fee tier")
    if not data or "BTC" not in data: raise ValueError("BTC USD series required")
    common=common or {}
    metadata=metadata or {}
    portfolio=Portfolio(c0)
    fee=costs[tier]
    calendar=calendar_days(data)
    by_day={a:{b["end"]:b for b in bars} for a,bars in data.items()}
    history={a:[] for a in data}
    last_prices={}
    pending=[]; events=[];curve=[];entry_dates={}
    spread_cost=0.;slippage_cost=0.
    maker_missed=0;kill_count=0;roundtrips=0;notional=0.
    peak=float(c0);kill_until=-1;killed=False
    stale_days={}
    start_i=next((i for i,d in enumerate(calendar) if start is None or d>=start),len(calendar))
    end_i=next((i for i,d in enumerate(calendar) if end is not None and d>end),len(calendar))
    if start_i>=end_i:
        raise ValueError("invalid time window")
    minimum=float(common.get("min_order_usd",25))
    participation=float(common.get("maker_fill_participation_hypothesis",0.5))
    if not 0<=participation<=1:
        raise ValueError("maker participation outside [0,1]")

    def order_minimum(asset):
        # Kraken pair-specific minimum from signed instrument metadata, otherwise >=25 USD.
        extra=metadata.get(asset,{}).get("min_order_usd")
        return max(minimum,float(extra) if extra is not None else minimum)

    def execute(side,asset,qty,px,base_price,rate,day,reason,liquidity):
        nonlocal roundtrips,notional,spread_cost,slippage_cost
        qty=float(qty);px=float(px)
        if qty<=0 or px<=0: return 0.0
        current=float(portfolio.positions.get(asset,{}).get("qty",0))
        if side=="buy":
            # Reserve for Decimal(str(float)) precision, no leverage ever.
            qty=min(qty,float(portfolio.cash)/(px*(1+rate))*(1-1e-9))
        else:
            qty=min(qty,current)
        if qty<=0:return 0.0
        # Closing dust position is allowed; avoid stranded unliquidatable dust.
        if qty*px<order_minimum(asset) and not (side=="sell" and qty>=current*(1-1e-8)):
            return 0.0
        if side=="buy":
            was_held=asset in portfolio.positions
            portfolio.buy(asset,qty,px,rate)
            if not was_held:entry_dates[asset]=day
        else:
            portfolio.sell(asset,qty,px,rate)
            if asset not in portfolio.positions:
                roundtrips+=1;entry_dates.pop(asset,None)
        notional+=qty*px
        spread,_slip=_cost(asset,costs)
        # Taker fill px includes a deterministic half-spread and adverse slippage.
        # These are separated from maker/taker fee, not counted twice.
        if liquidity=="taker":
            spread_cost+=qty*float(base_price)*spread
            slippage_cost+=max(0.0,qty*(abs(px-float(base_price))-float(base_price)*spread))
        events.append({"day":day,"asset":asset,"side":side,"qty":qty,
                       "price":px,"price_without_execution_cost":float(base_price),
                       "fee_usd":qty*px*rate,"fee_rate":rate,"reason":reason,
                       "liquidity":liquidity})
        return qty

    def queue(side,asset,qty,i,reason,urgent=False):
        if qty<=0 or asset in (p["asset"] for p in pending):
            return False
        mid=last_prices.get(asset)
        if mid is None:return False
        half,_=_cost(asset,costs)
        limit=mid*(1-half if side=="buy" else 1+half)
        pending.append({"asset":asset,"side":side,"qty":float(qty),"from_i":i,
                        "urgent":urgent,"limit":limit,"reason":reason})
        return True

    for i,day in enumerate(calendar):
        if i>=end_i: break
        today={a:b[day] for a,b in by_day.items() if day in b}
        for a,b in today.items():
            history[a].append(b)
            if not b.get("imputed"):last_prices[a]=float(b["close"])

        # Explicit delisting treatment. Never infer a future delisting for past decisions.
        # A delisting value is only used on or after its public dated event.
        for asset in list(portfolio.positions):
            meta=metadata.get(asset,{})
            removed=(meta.get("status")=="delisted" and bool(meta.get("delisted_at")) and
                     datetime.fromisoformat(day.replace("Z","+00:00")) >=
                     datetime.fromisoformat(meta["delisted_at"].replace("Z","+00:00")))
            if removed:
                last=next((b for b in reversed(history.get(asset,[])) if not b.get("imputed")),None)
                if last is None:
                    raise ValueError("DELIST_NO_FINAL_PRICE: "+asset)
                pending=[x for x in pending if x["asset"]!=asset]
                mid=float(last["close"]);half,slip=_cost(asset,costs)
                px=mid*(1-half-3*slip)
                execute("sell",asset,float(portfolio.positions[asset]["qty"]),px,mid,
                        float(fee["taker"]),day,"DELIST_FORCED_LAST_PRINT","taker")

        # Execution of decisions from previous close: maker J+1, fallback taker J+2.
        waiting=[]
        for o in pending:
            a=o["asset"];bar=today.get(a)
            if bar is None or bar.get("imputed"):
                # Order only remains pending if market is temporarily unavailable;
                # equity for a held asset fails closed below, rather than being frozen.
                waiting.append(o);continue
            age=i-o["from_i"]
            if age<=0:
                waiting.append(o);continue
            side=o["side"];half,slip=_cost(a,costs)
            if o["urgent"]:
                mid=float(bar["open"])
                mult=float(costs.get("forced_multiplier",3))
                price=mid*(1+(half+slip*mult)*(1 if side=="buy" else -1))
                execute(side,a,o["qty"],price,mid,float(fee["taker"]),day,o["reason"],"taker")
            elif age==1:
                limit=o["limit"]
                crossed=(float(bar["low"])<limit) if side=="buy" else (float(bar["high"])>limit)
                # OHLC trade range doesn't establish order queue priority; apply
                # a strict participation cap, plus maker-0% stress when requested.
                allowance=float(bar["volume"])*participation if crossed else 0.
                filled=execute(side,a,min(o["qty"],allowance),limit,limit,
                               float(fee["maker"]),day,o["reason"]+" maker","maker") if allowance>0 else 0.
                leftover=o["qty"]-filled
                if leftover>1e-10:
                    maker_missed+=1
                    waiting.append(dict(o,qty=leftover))
            else:
                mid=float(bar["open"])
                price=mid*(1+(half+slip)*(1 if side=="buy" else -1))
                execute(side,a,o["qty"],price,mid,float(fee["taker"]),day,o["reason"]+" fallback","taker")
        pending=waiting

        for asset in portfolio.positions:
            bar=today.get(asset)
            if bar is None or bar.get("imputed"):
                # No phantom valuations of delisted/stale holdings.
                raise ValueError("HELD_ASSET_STALE: %s at %s — audited delist metadata or real market needed"%(asset,day))
            last_prices[asset]=float(bar["close"])
        eq=float(portfolio.equity(last_prices))
        if i>=start_i:
            peak=max(peak,eq)
            curve.append({"day":day,"equity":eq,"cash":float(portfolio.cash),
                          "exposure":1-float(portfolio.cash)/eq if eq else 0})
        if i<start_i or i<warmup or "BTC" not in today or today["BTC"].get("imputed"):
            continue
        btc=history["BTC"]
        if eq<=peak*(1-float(risk["peak_drawdown_kill"])) and not killed:
            killed=True;kill_until=i+int(risk["cooldown_days"]);kill_count+=1
            pending=[]
            for a,pos in portfolio.positions.items():
                queue("sell",a,float(pos["qty"]),i,"kill-switch",urgent=True)
            continue
        if killed:
            if (i<kill_until or len(btc)<200 or
                float(btc[-1]["close"])<=sma([b["close"] for b in btc],200)):
                continue
            killed=False;peak=eq

        monday=datetime.fromisoformat(day).weekday()==0
        universe=point_in_time_universe(history,day)
        assets={"BTC":btc,"ETH":history.get("ETH",[])} if label=="C" else universe
        exits=set();urgent=set();target={}
        # Stop checks apply DAILY, independent of weekly selection.
        for a,pos in list(portfolio.positions.items()):
            bars=history.get(a,[])
            if not bars or bars[-1].get("imputed"):
                raise ValueError("HELD_ASSET_IMPUTED_SIGNALS: "+a)
            if label=="A":
                entered=entry_dates.get(a,day)
                peak_close=max(float(b["close"]) for b in bars if b["end"]>=entered)
                sig=candidate_a(bars,btc,pset,highest_close_since_entry=peak_close)
                if sig.get("exit"):
                    exits.add(a)
                    if float(bars[-1]["close"])<=peak_close-float(pset["atr_mult"])*atr(bars,int(pset.get("atr_period",20))):
                        urgent.add(a)
            elif label=="B":
                if (len(bars)>20 and usable_signal_window(bars,21) and
                    float(bars[-1]["close"])<=float(pos["avg_cost"])-float(pset.get("stop_atr_mult",4))*atr(bars,20)):
                    exits.add(a);urgent.add(a)
            elif label=="C":
                if candidate_c(bars,pset).get("exit"):exits.add(a)
            else:
                sig=candidate_d(bars,btc,pset)
                if sig.get("exit"):exits.add(a)
                entered=entry_dates.get(a,day)
                peak_close=max(float(b["close"]) for b in bars if b["end"]>=entered)
                if (len(bars)>20 and usable_signal_window(bars,21) and
                    float(bars[-1]["close"])<peak_close-float(pset["atr_mult"])*sig["atr14"]):
                    exits.add(a);urgent.add(a)
        current={a:float(p["qty"])*last_prices[a]/eq for a,p in portfolio.positions.items()}

        if label=="A":
            scored=[]
            for a,bars in assets.items():
                if a in portfolio.positions or a in exits:continue
                sig=candidate_a(bars,btc,pset)
                if sig.get("entry"):scored.append((sig["score"],a,sig["target_weight"]))
            scored.sort(key=lambda x:(-x[0],x[1]))
            proposed=dict(current)
            free=max(0,int(pset["max_positions"])-len(current))
            for _,a,w in scored:
                if free==0:break
                w=min(float(w),float(pset["max_exposure"])-sum(proposed.values()))
                if w<=0:continue
                if not correlation_allowed(a,w,proposed,history,window=int(risk.get("correlation_window_days",60)),
                                           threshold=float(risk.get("correlation_max",0.85)),
                                           max_group=float(risk.get("correlated_weight_max",0.4))):
                    continue
                target[a]=w;proposed[a]=w;free-=1
        elif label=="B":
            # BTC absolute momentum risk-off liquidates DAILY, not only Monday.
            breg=candidate_b(btc,btc,pset)
            if breg.get("btc_momentum",0)<=0:
                exits.update(portfolio.positions)
                urgent.update(portfolio.positions)
            elif monday:
                ranked=[]
                for a,bars in assets.items():
                    sig=candidate_b(bars,btc,pset)
                    if sig.get("eligible"):ranked.append((sig["score"],a,max(sig["vol20"],1e-9)))
                ranked.sort(key=lambda x:(-x[0],x[1]))
                ranks=[a for _,a,_ in ranked]
                selected=retained_momentum_candidates(ranks,set(current),int(pset["k"]),
                                                      int(pset.get("retention_extra_ranks",2)))
                inv={a:1/next(v for _,b,v in ranked if b==a) for a in selected}
                total_inv=sum(inv.values())
                base={a:inv[a]/total_inv for a in selected} if total_inv else {}
                estvol=sum(base[a]*next(v for _,b,v in ranked if b==a) for a in base)
                scale=min(1.,float(pset["target_vol"])/estvol) if estvol else 0
                target=bounded({a:w*scale for a,w in base.items()},
                               float(pset.get("max_exposure",0.9)),float(pset["max_per_asset"]))
        elif label=="C":
            for a,bars in assets.items():
                sig=candidate_c(bars,pset)
                if sig.get("entry") and (monday or a not in current):
                    target[a]=sig.get("target_weight",0)
                elif a in current and a not in exits:
                    target[a]=current[a]
            target=bounded(target,float(pset.get("max_exposure",1)),
                           float(pset.get("max_per_asset",0.5)))
        elif label=="D" and monday:
            ranking=[]
            for a,bars in assets.items():
                sig=candidate_d(bars,btc,pset)
                if sig.get("entry"):ranking.append((sig["score"],a))
            ranking.sort(key=lambda x:(-x[0],x[1]))
            selected=[a for _,a in ranking[:int(pset["top"])]]
            target=bounded({a:float(pset["max_per_asset"]) for a in selected},
                           float(pset.get("max_exposure",0.8)),float(pset["max_per_asset"]))

        if label in ("B","D") and monday:
            exits.update(a for a in current if a not in target)
        # Correlated group gating for new exposures under A/B/D. Existing holdings
        # may be reduced on rebalancing, but not silently liquidated by the gate.
        if label in ("A","B","D"):
            proposed={a:current[a] for a in current if a not in exits}
            for a,w in sorted(target.items(),key=lambda x:x[0]):
                new=max(0.,w-current.get(a,0))
                if new>0 and not correlation_allowed(a,new,proposed,history,
                                                     window=int(risk.get("correlation_window_days",60)),
                                                     threshold=float(risk.get("correlation_max",0.85)),
                                                     max_group=float(risk.get("correlated_weight_max",0.4))):
                    target[a]=current.get(a,0)
                else:
                    proposed[a]=w
        # Cancel conflicting orders on an exit, queue risk exits first.
        pending_assets={o["asset"] for o in pending}
        for a in sorted(exits):
            if a in pending_assets or a not in portfolio.positions:continue
            queue("sell",a,float(portfolio.positions[a]["qty"]),i,
                  "risk exit" if a in urgent else "signal exit",urgent=a in urgent)
            pending_assets.add(a)
        if label=="A":
            actions=[(a,"buy",w) for a,w in target.items()]
        elif label in ("B","D") and not monday:
            actions=[]
        else:
            actions=rebalance_actions(current,target,float(pset.get("rebal_band",0.02)))
        for a,side,delta in actions:
            if a in pending_assets or a in exits or a not in last_prices:continue
            if a not in today or today[a].get("imputed"):continue
            qty=delta*eq/last_prices[a]
            if qty*last_prices[a]<order_minimum(a):
                continue
            if queue(side,a,qty,i,"rebalance" if a in current else "entry"):
                pending_assets.add(a)

    if not curve: raise ValueError("no sampled equity")
    report=_report(curve,events,float(c0),portfolio.fees_paid,
                   {"spread":spread_cost,"slippage":slippage_cost},
                   maker_missed,kill_count,roundtrips)
    report.update({"candidate":label,"fee_scenario":tier,
                   "status":"EXPERIMENTAL_NOT_OOS_VALIDATED",
                   "start":curve[0]["day"],"end":curve[-1]["day"],
                   "days":len(curve),"curve":curve,"orders":events,
                   "turnover_usd":notional})
    return report
