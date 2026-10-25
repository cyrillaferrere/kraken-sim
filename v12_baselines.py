#!/usr/bin/env python3
"""Spot-only V1.2 reference baselines on exactly the same historical daily dates.
CASH, BTC buy/hold and equal BTC/ETH/XRP monthly rebalancing, with full taker
fee, half spread and adverse slippage paid on each execution.
"""
from datetime import datetime
from v12_accounting import Portfolio
from v12_backtest_core import _drawdown,_cost

def baselines(data,period,fee_rates,costs,c0=6605.1):
    if any(a not in data for a in ("BTC","ETH","XRP")):
        raise ValueError("BASELINE_MISSING_BTC_ETH_XRP")
    start,end=period
    by_day={a:{b["end"]:b for b in bars} for a,bars in data.items()}
    days=[d for d in sorted(by_day["BTC"]) if start<=d[:10]<=end]
    if not days:raise ValueError("empty benchmark window")
    output={}
    output["CASH"]={"net_return":0.,"max_drawdown_signed":0.,"fees_usd":0.,
                    "curve":[{"day":d,"equity":c0} for d in days],"orders":[]}
    for label,assets in (("BTC",["BTC"]),("EQUAL_BTC_ETH_XRP",["BTC","ETH","XRP"])):
        p=Portfolio(c0);series=[];ops=[];last={};last_month=None
        for j,day in enumerate(days):
            for a in assets:
                bar=by_day[a].get(day)
                if bar is None or bar.get("imputed"):
                    raise ValueError("BASELINE_STALE_OR_IMPUTED: %s %s"%(a,day))
                last[a]=float(bar["close"])
            month=day[:7]
            rebalance=(j==0 or (label=="EQUAL_BTC_ETH_XRP" and month!=last_month))
            if rebalance:
                eq=float(p.equity(last))
                w=1/len(assets)
                target={a:eq*w for a in assets}
                # Sell first to release cash; buy afterward.
                def order(a,side,desired):
                    half,slip=_cost(a,costs)
                    mid=float(by_day[a][day]["open"])
                    price=mid*(1+(half+slip)*(1 if side=="buy" else -1))
                    rate=float(fee_rates["taker"])
                    if side=="buy":
                        qty=max(0,desired/price)
                        qty=min(qty,float(p.cash)/(price*(1+rate))*(1-1e-9))
                        if qty*price<0.01:return
                        p.buy(a,qty,price,rate)
                    else:
                        holding=p.positions.get(a)
                        if holding is None:return
                        qty=min(float(holding["qty"]),max(0,desired)/price)
                        if qty*price<0.01:return
                        p.sell(a,qty,price,rate)
                    ops.append({"day":day,"side":side,"asset":a,"price":price,"qty":qty,"fee":qty*price*rate})
                if j>0:
                    for a in assets:
                        current=float(p.positions.get(a,{}).get("qty",0))*float(by_day[a][day]["open"])
                        if current>target[a]:
                            order(a,"sell",current-target[a])
                for a in assets:
                    held=float(p.positions.get(a,{}).get("qty",0))*float(by_day[a][day]["open"])
                    if target[a]>held:
                        order(a,"buy",target[a]-held)
            series.append({"day":day,"equity":float(p.equity(last))})
            last_month=month
        final=series[-1]["equity"];mdd,_=_drawdown([x["equity"] for x in series],c0)
        output[label]={"net_return":final/c0-1,"max_drawdown_signed":mdd,
                       "fees_usd":float(p.fees_paid),"curve":series,"orders":ops}
    return output
