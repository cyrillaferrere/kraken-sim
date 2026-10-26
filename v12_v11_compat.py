#!/usr/bin/env python3
"""V1.1 indicator parity: reuse the original V1.1 backtest indicator function.
No V1.1 files are changed and importing backtest.py does NOT fetch exchange data.
Does NOT assert parity of execution cadence, maker fills or original seeded core.
"""
from datetime import datetime,timezone
from backtest import ind

def indicator(bars):
    if len(bars)<61 or bars[-1].get("imputed"):
        raise ValueError("insufficient or imputed V1.1 indicator history")
    if any(b.get("imputed") for b in bars[-61:]):
        raise ValueError("imputed data would bias historical indicators")
    series={}
    for b in bars:
        t=int(datetime.fromisoformat(b["end"].replace("Z","+00:00")).timestamp())
        series[t]=(float(b["high"]),float(b["low"]),float(b["close"]),float(b["volume"]))
    values=ind(series)
    return values[max(values)]

def entry_score(bars):
    x=indicator(bars)
    flags=[x["c"]>x["e50"] and x["e20"]>x["e50"],x["macd"],
           50<x["rsi"]<75,x["adx"]>20 and x["pdi"]>x["mdi"],x["volup"]]
    return {"trend":flags[0],"score":sum(flags),"mom":x["mom"],
            "ema50":x["e50"],"atr14":x["atr"],"close":x["c"],"raw":x}
