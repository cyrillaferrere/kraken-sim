#!/usr/bin/env python3
"""Daily backtest on Kraken public OHLC (max 720 daily candles). Costs: fee 0.40% + slippage 0.05% + half-spread 0.05% per side."""
import json, urllib.request, sys, math
COST = 0.004 + 0.0005 + 0.0005
U = ["XXBTZUSD","XETHZUSD","SOLUSD","XXRPZUSD","ZECUSD","NEARUSD","SUIUSD","HYPEUSD","TAOUSD","XDGUSD"]
def get(pair):
    r = json.load(urllib.request.urlopen(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440", timeout=30))["result"]
    k = [x for x in r if x != "last"][0]
    return {int(a[0]): (float(a[2]), float(a[3]), float(a[4]), float(a[6])) for a in r[k][:-1]}
def ema(x, n):
    k = 2/(n+1); o=[x[0]]
    for v in x[1:]: o.append(o[-1]+k*(v-o[-1]))
    return o
def ind(d):
    ts = sorted(d); H=[d[t][0] for t in ts]; L=[d[t][1] for t in ts]; C=[d[t][2] for t in ts]; V=[d[t][3]*d[t][2] for t in ts]
    n=len(C); tr=[H[0]-L[0]]+[max(H[i]-L[i],abs(H[i]-C[i-1]),abs(L[i]-C[i-1])) for i in range(1,n)]
    atr=ema(tr,27)  # Wilder 14 ~ EMA 27
    up=[0]+[max(H[i]-H[i-1],0) if H[i]-H[i-1]>L[i-1]-L[i] else 0 for i in range(1,n)]
    dn=[0]+[max(L[i-1]-L[i],0) if L[i-1]-L[i]>H[i]-H[i-1] else 0 for i in range(1,n)]
    sp,sm=ema(up,27),ema(dn,27); pdi=[100*a/b if b else 0 for a,b in zip(sp,atr)]; mdi=[100*a/b if b else 0 for a,b in zip(sm,atr)]
    dx=[100*abs(a-b)/(a+b) if a+b else 0 for a,b in zip(pdi,mdi)]; adx=ema(dx,27)
    ch=[0]+[C[i]-C[i-1] for i in range(1,n)]; g=ema([max(c,0) for c in ch],27); l=ema([max(-c,0) for c in ch],27)
    rsi=[100-100/(1+a/b) if b else 100 for a,b in zip(g,l)]
    m=[a-b for a,b in zip(ema(C,12),ema(C,26))]; sig=ema(m,9)
    e20,e50=ema(C,20),ema(C,50)
    s50=[sum(C[max(0,i-49):i+1])/min(i+1,50) for i in range(n)]
    v7=[sum(V[max(0,i-6):i+1])/min(i+1,7) for i in range(n)]; v30=[sum(V[max(0,i-29):i+1])/min(i+1,30) for i in range(n)]
    return {t: dict(c=C[i],atr=atr[i],adx=adx[i],pdi=pdi[i],mdi=mdi[i],rsi=rsi[i],macd=m[i]>sig[i],e20=e20[i],e50=e50[i],s50=s50[i],volup=v7[i]>v30[i],vr=v7[i]/v30[i] if v30[i] else None,mh=m[i]-sig[i],
            mom=(C[i]/C[i-30]-1)*.5+(C[i]/C[i-7]-1)*.5 if i>=30 else None, ok=i>=60) for i,t in enumerate(ts)}
def signals(v, x, btc):
    """return (entry_ok, keep_ok, list_of_confirmations)"""
    if v=="A":  # current: SMA50 trend + positive momentum
        e = x["c"]>x["s50"] and x["mom"]>0; return e, x["c"]>x["s50"], ["SMA50"] if e else []
    conf = []
    if x["c"]>x["e50"] and x["e20"]>x["e50"]: conf.append("EMA20>50")
    if x["macd"]: conf.append("MACD")
    if 50<x["rsi"]<75: conf.append("RSI")
    if x["adx"]>20 and x["pdi"]>x["mdi"]: conf.append("ADX")
    if x["volup"]: conf.append("Volume")
    reg = btc["c"]>btc["e50"]
    trend = "EMA20>50" in conf
    if v=="B":  # 5 indicators, need trend + >=4/5, BTC regime
        return reg and trend and len(conf)>=4, reg and x["c"]>x["e50"], conf
    if v=="C":  # 3 indicators all: EMA trend + MACD + RSI, BTC regime
        return reg and trend and "MACD" in conf and "RSI" in conf, reg and x["c"]>x["e50"], conf
    if v=="D":  # 4 of: trend required + 3 of (MACD,RSI,ADX,Volume)... = B with >=3 confirmations beyond regime
        return reg and trend and len(conf)>=3, reg and x["c"]>x["e50"], conf
def run(v, data, btcd, days, top=3, w=0.33, atrm=3.0):
    cash=1.0; pos={}; fees=0; trades=0; wins=0; closed=0; peak=1; mdd=0; eqs=[]
    for t in days:
        btc=btcd[t]
        # exits
        for a in list(pos):
            x=data[a].get(t)
            if not x: continue
            p=pos[a]; p["hi"]=max(p["hi"],x["c"]); stop=p["hi"]-atrm*x["atr"]
            _,keep,_=signals(v,x,btc)
            if x["c"]<=stop or not keep:
                val=p["q"]*x["c"]*(1-COST); fees+=p["q"]*x["c"]*COST; cash+=val; trades+=1; closed+=1; wins+=val>p["cost"]; del pos[a]
        eq=cash+sum(p["q"]*data[a][t]["c"] for a,p in pos.items() if t in data[a])
        cands=sorted([(x["mom"],a) for a in data if (x:=data[a].get(t)) and x["ok"] and x["mom"] is not None and a not in pos and signals(v,x,btc)[0]],reverse=True)
        for _,a in cands:
            if len(pos)>=top: break
            amt=min(w*eq, cash)
            if amt<0.02*eq: break
            x=data[a][t]; fees+=amt*COST; pos[a]=dict(q=amt*(1-COST)/x["c"],hi=x["c"],cost=amt); cash-=amt; trades+=1
        eq=cash+sum(p["q"]*data[a][t]["c"] for a,p in pos.items() if t in data[a])
        peak=max(peak,eq); mdd=max(mdd,1-eq/peak); eqs.append(eq)
    return dict(ret=eqs[-1]-1, mdd=mdd, trades=trades, fees=fees, win=wins/closed if closed else None)
def main():
    raw={a:get(a) for a in U}; data={a:ind(d) for a,d in raw.items()}; btcd=data["XXBTZUSD"]
    days=[t for t in sorted(btcd) if btcd[t]["ok"]]
    cut=days[int(len(days)*0.6)]
    from datetime import datetime,timezone
    f=lambda t: datetime.fromtimestamp(t,timezone.utc).strftime("%d/%m/%Y")
    periods={"complet":days,"apprentissage":[t for t in days if t<cut],"hors-échantillon":[t for t in days if t>=cut]}
    out={"periods":{k:f"{f(v[0])} – {f(v[-1])} ({len(v)} j)" for k,v in periods.items()},"history":{a:len(d) for a,d in raw.items()},"results":{}}
    for k,ds in periods.items():
        res={}
        for v in "ABCD": res[v]=run(v,data,btcd,ds)
        b0,b1=btcd[ds[0]]["c"],btcd[ds[-1]]["c"]; pk=0;md=0
        for t in ds: pk=max(pk,btcd[t]["c"]); md=max(md,1-btcd[t]["c"]/pk)
        res["BTC"]=dict(ret=b1/b0*(1-COST)-1,mdd=md,trades=1,fees=COST,win=None)
        out["results"][k]=res
    json.dump(out,open("backtest_results.json","w"),indent=1)
    for k,res in out["results"].items():
        print(k,out["periods"][k])
        for v,r in res.items(): print(f"  {v:4} ret {r['ret']*100:7.1f}%  mdd {r['mdd']*100:5.1f}%  trades {r['trades']:3}  fees {r['fees']*100:5.1f}%C0  win {'' if r['win'] is None else round(r['win']*100)}")
    print(out["history"])

if __name__ == '__main__': main()
