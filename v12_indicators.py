#!/usr/bin/env python3
"""Pure daily indicators, no market calls. Inputs are already CLOSED candles."""
import math
import statistics

def ema_series(xs, n):
    if n < 2 or not xs: raise ValueError("insufficient EMA input")
    k=2/(n+1)
    out=[float(xs[0])]
    for x in xs[1:]: out.append(out[-1] + k*(float(x)-out[-1]))
    return out

def sma(xs,n):
    if len(xs)<n or n<=0: raise ValueError("insufficient SMA history")
    return sum(float(x) for x in xs[-n:])/n

def atr(bars,n=20):
    if len(bars)<n+1: raise ValueError("insufficient ATR history")
    trs=[]
    for i,b in enumerate(bars):
        h,l=float(b["high"]),float(b["low"])
        prev=float(bars[i-1]["close"]) if i else float(b["close"])
        trs.append(max(h-l,abs(h-prev),abs(l-prev)))
    out=sum(trs[1:n+1])/n
    for t in trs[n+1:]: out=(out*(n-1)+t)/n
    return out

def vol(bars,n=20):
    if len(bars)<n+1: raise ValueError("insufficient vol history")
    closes=[float(b["close"]) for b in bars[-n-1:]]
    if any(v<=0 for v in closes): raise ValueError("invalid close")
    returns=[math.log(closes[i]/closes[i-1]) for i in range(1,len(closes))]
    return statistics.stdev(returns)*math.sqrt(365)

def correlation_return(bars_a,bars_b,n=60):
    if len(bars_a)<n+1 or len(bars_b)<n+1: raise ValueError("insufficient correlation")
    def ret(bars):
        closes=[float(b["close"]) for b in bars[-n-1:]]
        return [math.log(closes[i]/closes[i-1]) for i in range(1,len(closes))]
    a,b=ret(bars_a),ret(bars_b)
    avg1,avg2=sum(a)/n,sum(b)/n
    num=sum((x-avg1)*(y-avg2) for x,y in zip(a,b))
    den=math.sqrt(sum((x-avg1)**2 for x in a)*sum((y-avg2)**2 for y in b))
    return num/den if den else 0.0

def confluence_v11(bars):
    """Approximation structurelle D du score V1.1; signal exact à valider par replay."""
    if len(bars)<61: raise ValueError("insufficient history")
    c=[float(b["close"]) for b in bars]
    h=[float(b["high"]) for b in bars]
    l=[float(b["low"]) for b in bars]
    v=[float(b["volume"])*float(b["close"]) for b in bars]
    e20,e50=ema_series(c,20)[-1],ema_series(c,50)[-1]
    mac=[a-b for a,b in zip(ema_series(c,12),ema_series(c,26))]
    macd_ok=mac[-1]>ema_series(mac,9)[-1]
    moves=[0]+[c[i]-c[i-1] for i in range(1,len(c))]
    gains=ema_series([max(q,0) for q in moves],27)[-1]
    losses=ema_series([max(-q,0) for q in moves],27)[-1]
    rsi=100-100/(1+gains/losses) if losses else 100
    trs=[h[0]-l[0]]+[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,len(c))]
    up=[0]+[max(h[i]-h[i-1],0) if h[i]-h[i-1]>l[i-1]-l[i] else 0 for i in range(1,len(c))]
    down=[0]+[max(l[i-1]-l[i],0) if l[i-1]-l[i]>h[i]-h[i-1] else 0 for i in range(1,len(c))]
    atr14=ema_series(trs,27)[-1]
    pd=100*ema_series(up,27)[-1]/atr14 if atr14 else 0
    md=100*ema_series(down,27)[-1]/atr14 if atr14 else 0
    # Full history of DX for ADX (not just today's DIs)
    trsm=ema_series(trs,27)
    ups,downs=ema_series(up,27),ema_series(down,27)
    dx=[]
    for t,a,b in zip(trsm,ups,downs):
        pdi=100*a/t if t else 0; mdi=100*b/t if t else 0
        dx.append(100*abs(pdi-mdi)/(pdi+mdi) if pdi+mdi else 0)
    adx=ema_series(dx,27)[-1]
    trend=c[-1]>e50 and e20>e50
    flags=[trend,macd_ok,50<rsi<75,adx>20 and pd>md,sma(v,7)>sma(v,30)]
    mom=.5*(c[-1]/c[-31]-1)+.5*(c[-1]/c[-8]-1)
    return {"trend":trend,"score":sum(flags),"ema50":e50,"mom":mom,
            "adx":adx,"rsi":rsi,"macd_ok":macd_ok,"volume_ok":flags[-1]}
