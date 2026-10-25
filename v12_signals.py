#!/usr/bin/env python3
"""Candidate signals from Grok Bot SPEC V1.2, on CLOSED daily candles only.
Pure functions: NO orders, NO account changes, NO forward prices.
"""
import math
import statistics
from datetime import datetime,timezone,timedelta
from v12_indicators import sma, atr, vol, ema_series, confluence_v11

EXCLUDED={"USDT","USDC","DAI","PYUSD","WBTC","TBTC","WETH","PAXG","XAUT","FDUSD","USDE","EUR","GBP","USD","USDG","EURC"}

def _as_utc(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("timestamp without timezone")
    return d.astimezone(timezone.utc)

def closed_candles(bars,as_of):
    cutoff=_as_utc(as_of)
    latest={}
    for b in bars:
        end=_as_utc(b["end"])
        if end<=cutoff:
            if not all(float(b[k])>0 for k in ("high","low","close")) or float(b["volume"])<0:
                raise ValueError("invalid historical candle")
            if end in latest: raise ValueError("duplicate candle timestamp")
            latest[end]=dict(b)
    return [latest[t] for t in sorted(latest)]

def usable_signal_window(bars, n):
    """Imputed candles cannot silently lower ATR/vol or create a signal."""
    if n <= 0 or len(bars) < n:
        return False
    return not any(b.get("imputed") for b in bars[-n:])

def point_in_time_universe(data,as_of,min_history=120,min_daily_volume=5000000,max_assets=20):
    """Strictly past-only universe. Fresh, real daily candle and 120 real bars required."""
    cutoff=_as_utc(as_of)
    found=[]
    for asset,raw in data.items():
        if asset in EXCLUDED or asset.startswith("USD") or asset.startswith("EUR"):
            continue
        bars=closed_candles(raw,as_of)
        if len(bars)<min_history or not usable_signal_window(bars,min_history):
            continue
        if cutoff-_as_utc(bars[-1]["end"])>timedelta(hours=26):
            continue
        vols=[float(b["close"])*float(b["volume"]) for b in bars[-30:]]
        med=statistics.median(vols)
        if med>=min_daily_volume:
            found.append((med,asset,bars))
    found.sort(key=lambda v:(-v[0],v[1]))
    return {asset:bars for _,asset,bars in found[:max_assets]}

def candidate_a(bars,btc,params,highest_close_since_entry=None):
    n,x,k=int(params["breakout_days"]),int(params["exit_days"]),float(params["atr_mult"])
    if not usable_signal_window(bars,max(n+1,x+1,21)) or not usable_signal_window(btc,200): return {"entry":False,"exit":False,"reason":"warmup"}
    c=float(bars[-1]["close"]); atr20=atr(bars,20)
    prev_high=max(float(b["high"]) for b in bars[-n-1:-1])
    prev_low=min(float(b["low"]) for b in bars[-x-1:-1])
    regime=float(btc[-1]["close"])>sma([b["close"] for b in btc],200)
    if highest_close_since_entry is None: stop=False
    else: stop=c<=float(highest_close_since_entry)-k*atr20
    risk_weight=float(params.get("risk_per_entry",0.005))/(k*atr20/c) if atr20 else 0
    return {"entry":regime and c>prev_high,"exit":c<prev_low or stop,
            "score":c/prev_high-1,"target_weight":min(float(params.get("max_per_asset",0.15)),risk_weight),
            "btc_regime":"on" if regime else "off","atr20":atr20}

def candidate_b(bars,btc,params):
    n=int(params["momentum_days"]); skip=int(params["skip_days"])
    need=max(n+skip+1,int(params["sma_days"]),21)
    if not usable_signal_window(bars,need) or not usable_signal_window(btc,need): return {"eligible":False,"reason":"warmup"}
    def rate(q):
        c=[float(b["close"]) for b in q]
        return c[-1-skip]/c[-1-skip-n]-1
    mom=rate(bars); btc_mom=rate(btc)
    close=float(bars[-1]["close"])
    good=mom>0 and close>sma([b["close"] for b in bars],int(params["sma_days"])) and btc_mom>0
    return {"eligible":good,"score":mom,"btc_momentum":btc_mom,"vol20":vol(bars,20)}

def candidate_c(bars,params):
    f,slow=int(params["fast_ema"]),int(params["slow_ema"])
    if not usable_signal_window(bars,slow+20): return {"entry":False,"exit":False,"reason":"warmup"}
    c=[float(b["close"]) for b in bars]
    fast=ema_series(c,f)[-1]; long=ema_series(c,slow)[-1]; price=c[-1]
    sigma=vol(bars,20)
    target=min(float(params.get("max_per_asset",0.5)),0.5*float(params["target_vol"])/sigma) if sigma else 0
    return {"entry":fast>long and price>fast, "exit":price<long or fast<long,
            "target_weight":target,"vol20":sigma}

def candidate_d(bars,btc,params):
    if not usable_signal_window(bars,61) or not usable_signal_window(btc,61): return {"entry":False,"exit":False,"reason":"warmup"}
    d=confluence_v11(bars)
    bc=confluence_v11(btc)
    at=atr(btc,20)
    close=float(btc[-1]["close"])
    e50=bc["ema50"]; k=float(params["btc_hysteresis_atr"])
    regime="on" if close>e50+k*at else ("off" if close<e50-k*at else "neutral")
    return {"entry":regime=="on" and d["trend"] and d["score"]>=4,
            "exit":regime=="off" or float(bars[-1]["close"])<d["ema50"],
            "score":d["mom"],"btc_regime":regime}
