#!/usr/bin/env python3
"""Backtest V2 (critique Grok) : univers point-in-time mensuel, variantes B/B'/B''/B''', walk-forward 6m/3m.
Données : OHLC journalier public Kraken (720 bougies max). Coûts : 0,40 % + 0,05 % + 0,05 % par côté. Lecture seule."""
import json, urllib.request, time, os, sys
from datetime import datetime, timezone
from backtest import ind, COST
CACHE="ohlc_cache.json"
if os.environ.get("FEE"): COST=float(os.environ["FEE"])+0.001
OUT=os.environ.get("OUT","backtest2_results.json")
STABLE={"USDT","USDC","DAI","PYUSD","USDG","RLUSD","USDS","TUSD","USDD","FDUSD","EURT","EUR","GBP","CHF","AUD","CAD","JPY","USD","UST","USDQ","USDR","EURR","EURQ","TBTC","WBTC","PAXG","XAUT","LSETH","CMETH","METH","WETH","STETH","SBTC","USD1","USDE","AUSD","USTC","BUSD","GUSD","EUROC","EURC","ZUSD","ZEUR","ZGBP"}
def J(u): return json.load(urllib.request.urlopen(u, timeout=30))
def pairs():
    r=J("https://api.kraken.com/0/public/AssetPairs")["result"]; out={}
    for k,p in r.items():
        if p.get("quote") not in ("ZUSD","USD") or ".d" in k or p.get("status","online")!="online": continue
        b=p["wsname"].split("/")[0]
        if b in STABLE or b.endswith("USD"): continue
        out[b]=k
    return out
def load():
    if os.path.exists(CACHE): return json.load(open(CACHE))
    raw={}
    for b,k in pairs().items():
        for _ in range(3):
            try:
                r=J(f"https://api.kraken.com/0/public/OHLC?pair={k}&interval=1440")
                if r["error"]: raise Exception(r["error"])
                rr=r["result"]; kk=[x for x in rr if x!="last"][0]
                raw[b]={str(int(a[0])):[float(a[2]),float(a[3]),float(a[4]),float(a[6])] for a in rr[kk][:-1]}; break
            except Exception as e: time.sleep(3)
        time.sleep(1.1)
    json.dump(raw,open(CACHE,"w")); return raw
def month(t): d=datetime.fromtimestamp(t,timezone.utc); return d.year*12+d.month-1
def build_universe(raw, data, days, N=20):
    """au 1er jour de chaque mois : top N par volume USD moyen 30 j antérieurs, historique >= 60 j."""
    U={}
    for t in days:
        m=month(t)
        if m in U: continue
        sc=[]
        for a,d in raw.items():
            if a not in data or t not in data[a] or not data[a][t]["ok"]: continue
            vs=[d[str(t-86400*i)][3]*d[str(t-86400*i)][2] for i in range(1,31) if str(t-86400*i) in d]
            if len(vs)>=25: sc.append((sum(vs)/len(vs),a))
        U[m]=[a for _,a in sorted(sc,reverse=True)[:N]]
    return U
def run(v, data, btc, days, U, fixed=None):
    """v in B, B1 (B'), B2 (B''), B3 (B''')."""
    cash=1.0; pos={}; fees=0; trades=0; W=[]; Lo=[]; peak=1; mdd=0; eqs=[]
    for t in days:
        univ=fixed or U[month(t)]; bx=btc[t]
        above=[a for a in univ if t in data.get(a,{}) and data[a][t]["c"]>data[a][t]["e50"]]
        reg=bx["c"]>bx["e50"]
        breadth=len(above)/max(1,len(univ))
        reg2=reg and (v=="B" or breadth>0.40)
        for a in list(pos):
            x=data[a].get(t)
            if not x: # plus de données (retiré) : on sort au dernier prix connu
                x={"c":pos[a]["last"],"atr":0,"e50":0}
            p=pos[a]; p["last"]=x["c"]; p["hi"]=max(p["hi"],x["c"])
            if v in("B","B1"): m=3.0
            else: m=3.5 if p["hi"]-p["px"]>=1.5*p["atr0"] else 2.0
            stop=p["hi"]-m*x["atr"]
            if v=="B3" and not p["tp"] and x["c"]>=p["px"]+2*p["atr0"]:
                q=p["q"]/2; val=q*x["c"]*(1-COST); fees+=q*x["c"]*COST; cash+=val; trades+=1
                p["real"]+=val; p["q"]-=q; p["tp"]=True
            if x["c"]<=stop or not (reg2 and x["c"]>x["e50"]):
                val=p["q"]*x["c"]*(1-COST); fees+=p["q"]*x["c"]*COST; cash+=val; trades+=1
                pnl=p["real"]+val-p["cost"]; (W if pnl>0 else Lo).append(pnl); del pos[a]
        eq=cash+sum(p["q"]*p["last"] for p in pos.values())
        if reg2:
            cands=[]
            for a in univ:
                x=data.get(a,{}).get(t)
                if not x or not x["ok"] or x["mom"] is None or a in pos: continue
                trend=x["c"]>x["e50"] and x["e20"]>x["e50"]
                if v=="B":
                    n=trend+x["macd"]+(50<x["rsi"]<75)+(x["adx"]>20 and x["pdi"]>x["mdi"])+x["volup"]
                    ok=trend and n>=4
                else: ok=trend and x["macd"] and x["volup"]
                if ok: cands.append((x["mom"],a))
            for _,a in sorted(cands,reverse=True):
                if len(pos)>=3: break
                x=data[a][t]
                if v=="B": w=0.33
                else:
                    m0=3.0 if v=="B1" else 2.0
                    w=min(0.35, 0.01/(m0*x["atr"]/x["c"]))
                amt=min(w*eq,cash)
                if amt<0.02*eq: continue
                fees+=amt*COST; pos[a]=dict(q=amt*(1-COST)/x["c"],hi=x["c"],px=x["c"],atr0=x["atr"],cost=amt,real=0,tp=False,last=x["c"]); cash-=amt; trades+=1
        eq=cash+sum(p["q"]*p["last"] for p in pos.values())
        peak=max(peak,eq); mdd=max(mdd,1-eq/peak); eqs.append(eq)
    # clôture fictive en fin de fenêtre (valorisée sans frais de sortie)
    for p in pos.values():
        pnl=p["real"]+p["q"]*p["last"]-p["cost"]; (W if pnl>0 else Lo).append(pnl)
    n=len(W)+len(Lo)
    return dict(ret=eqs[-1]-1,mdd=mdd,trades=trades,fees=fees,win=len(W)/n if n else None,
                avgw=sum(W)/len(W) if W else None,avgl=sum(Lo)/len(Lo) if Lo else None,eqs=eqs)
def bench(data, btc, days, U):
    b=[btc[t]["c"] for t in days]; eqs=[x/b[0]*(1-COST) for x in b]
    # equal-weight univers PIT, rééquilibré mensuellement, coûts sur le turnover
    eq=1.0; w={}; ew=[]; prev=None
    for i,t in enumerate(days):
        if i:
            r=0
            for a,wa in w.items():
                x0=data[a].get(days[i-1]); x1=data[a].get(t)
                r+=wa*((x1["c"]/x0["c"]-1) if x0 and x1 else 0)
            eq*=1+r
            w={a:wa*((data[a][t]["c"]/data[a][days[i-1]]["c"]) if data[a].get(t) and data[a].get(days[i-1]) else 1)/(1+r) for a,wa in w.items()}
        m=month(t)
        if m!=prev:
            un=[a for a in U[m] if t in data[a]]; tgt={a:1/len(un) for a in un}
            to=sum(abs(tgt.get(a,0)-w.get(a,0)) for a in set(tgt)|set(w)); eq*=1-to*COST; w=tgt; prev=m
        ew.append(eq)
    def st(e):
        pk=0;md=0
        for x in e: pk=max(pk,x); md=max(md,1-x/pk)
        return dict(ret=e[-1]/1-1 if e[0]==e[0] else 0,mdd=md,eqs=e)
    a=st(eqs); c=st([x for x in ew]); return a,c
def main():
    raw={a:{int(k):tuple(v) for k,v in d.items()} for a,d in load().items()}
    data={a:ind(d) for a,d in raw.items() if len(d)>=80}
    raw={a:{str(k):v for k,v in d.items()} for a,d in raw.items()}
    btc=data["XBT"]; days=[t for t in sorted(btc) if btc[t]["ok"]]
    U=build_universe(raw,data,days)
    FIX=["XBT","ETH","SOL","XRP","ZEC","NEAR","SUI","HYPE","TAO","XDG"]
    f=lambda t: datetime.fromtimestamp(t,timezone.utc).strftime("%d/%m/%Y")
    # walk-forward : 6 mois d'apprentissage (préchauffage, aucun paramètre ré-optimisé), test 3 mois, roulant
    ms=sorted({month(t) for t in days}); folds=[]
    i=6
    while i<len(ms):
        test=[t for t in days if ms[i]<=month(t)<ms[min(i+3,len(ms))] ] if i+3<=len(ms) else [t for t in days if month(t)>=ms[i]]
        train=[t for t in days if ms[i-6]<=month(t)<ms[i]]
        if len(test)>=30: folds.append((train,test))
        i+=3
    V=["B","B1","B2","B3"]; out={"folds":[],"agg":{},"universe_months":{},"n_pairs":len(raw),"n_usable":len(data)}
    agg={v:[1.0] for v in V+["Bfixe","BTC","EW"]}; tot={v:dict(trades=0,fees=0,W=[],L=[],pos=0) for v in V+["Bfixe"]}
    for tr,te in folds:
        row={"train":f"{f(tr[0])} – {f(tr[-1])}","test":f"{f(te[0])} – {f(te[-1])}","res":{}}
        for v in V+["Bfixe"]:
            r=run("B" if v=="Bfixe" else v,data,btc,te,U,fixed=FIX if v=="Bfixe" else None)
            rt=run("B" if v=="Bfixe" else v,data,btc,tr,U,fixed=FIX if v=="Bfixe" else None)
            agg[v]+= [agg[v][-1]*e for e in r["eqs"]]
            T=tot[v]; T["trades"]+=r["trades"]; T["fees"]+=r["fees"]*agg[v][-len(r["eqs"])-1]; T["pos"]+=r["ret"]>0
            row["res"][v]={k:r[k] for k in r if k!="eqs"}; row["res"][v]["train_ret"]=rt["ret"]
        b,e=bench(data,btc,te,U)
        for k,x in (("BTC",b),("EW",e)):
            agg[k]+=[agg[k][-1]*q for q in x["eqs"]]; row["res"][k]={"ret":x["ret"],"mdd":x["mdd"]}
        out["folds"].append(row)
    for v,e in agg.items():
        pk=0;md=0
        for x in e: pk=max(pk,x); md=max(md,1-x/pk)
        out["agg"][v]={"ret":e[-1]-1,"mdd":md,**({"trades":tot[v]["trades"],"fees":tot[v]["fees"],"pos_folds":tot[v]["pos"]} if v in tot else {})}
    # stats gagnants/perdants agrégées
    for v in V+["Bfixe"]:
        ws=[r["res"][v] for r in out["folds"]]
        out["agg"][v]["win"]=None; 
    # période complète (pour win/avg agrégés)
    full=[t for t in days if month(t)>=ms[6]]
    for v in V+["Bfixe"]:
        r=run("B" if v=="Bfixe" else v,data,btc,full,U,fixed=FIX if v=="Bfixe" else None)
        out["agg"][v].update(full_ret=r["ret"],full_mdd=r["mdd"],win=r["win"],avgw=r["avgw"],avgl=r["avgl"],full_trades=r["trades"],full_fees=r["fees"])
    out["universe_months"]={f"{m//12}-{m%12+1:02d}":U[m] for m in sorted(U)}
    out["n_folds"]=len(folds); out["period"]=f"{f(full[0])} – {f(full[-1])}"
    json.dump(out,open(OUT,"w"),indent=1,ensure_ascii=False)
    P=lambda x:"   n.d." if x is None else f"{x*100:6.1f}%"
    for r in out["folds"]:
        print("TEST",r["test"],"|", "  ".join(f"{k} {P(x['ret'])}/{P(x['mdd'])}" for k,x in r["res"].items()))
    for v,a in out["agg"].items(): print(v,{k:(round(x,4) if isinstance(x,float) else x) for k,x in a.items()})
    print(out["n_pairs"],out["n_usable"],out["period"])
if __name__=="__main__": main()
