#!/usr/bin/env python3
"""Pure sizing/rebalancing rules for V1.2; execution takes place next session."""
from v12_indicators import correlation_return

def bounded(weights,cap=0.9,per_asset=0.3):
    """Preserve relative weights and stop even floating-point overshoot."""
    clean={a:min(float(per_asset),max(0.,float(v))) for a,v in weights.items() if float(v)>0}
    total=sum(clean.values())
    if total>cap and total>0:
        factor=cap/total
        clean={k:v*factor for k,v in clean.items()}
    return clean

def retained_momentum_candidates(ranked,held,k,buffer=2):
    """Keep held eligible assets within top K+buffer; fill remaining slots from best ranks."""
    ranked=[str(x) for x in ranked]
    protected=[a for a in ranked[:k+buffer] if a in held]
    chosen=protected[:k]
    for a in ranked:
        if len(chosen)>=k: break
        if a not in chosen:chosen.append(a)
    return chosen

def rebalance_actions(current,target,band=0.02):
    """Return order desired weight DELTAS; sell orders first. No simultaneous buy and sell."""
    assets=set(current)|set(target)
    out=[]
    for a in sorted(assets):
        old=float(current.get(a,0));desired=float(target.get(a,0))
        if abs(desired-old)>band:
            out.append((a,"sell" if old>desired else "buy",abs(desired-old)))
    return sorted(out,key=lambda x:(x[1]!="sell",x[0]))

def correlation_allowed(asset,weight,proposed_weights,historical_bars,window=60,threshold=0.85,max_group=0.4):
    """Fail CLOSED when 60-day comparable daily returns aren't known."""
    a=historical_bars.get(asset)
    if a is None or len(a)<window+1:
        return False
    correlated=float(weight)
    for other,w in proposed_weights.items():
        if other==asset or w<=0: continue
        b=historical_bars.get(other)
        if b is None or len(b)<window+1:
            return False
        if any(x.get("imputed") for x in a[-window-1:]) or any(x.get("imputed") for x in b[-window-1:]):
            return False
        if correlation_return(a,b,n=window)>threshold:
            correlated+=float(w)
    return correlated<=max_group+1e-12
