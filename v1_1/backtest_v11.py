#!/usr/bin/env python3
"""Kraken Sim V1.1 — backtest d'ablation (journalier, lecture seule, données publiques Kraken en cache).
Décision une fois par jour sur bougie clôturée t ; exécution : taker au close t (≈ 00:10 UTC t+1),
maker post-only à limite = close t, rempli seulement si le prix de t+1 CROISE la limite (low<lim / high>lim), sinon nouvel essai.
Capital absolu C0 = 6 605,10 $ (paliers de frais en $)."""
import json, os, sys, math, statistics as S
from datetime import datetime, timezone
D = os.path.dirname(os.path.abspath(__file__)); P = os.path.dirname(D); sys.path.insert(0, P)
from backtest import ind
C0 = 6605.10; SLIP = 0.001  # taker : glissement 0,05 % + demi-spread 0,05 %
STABLE = {"USDT","USDC","DAI","PYUSD","USDG","RLUSD","USDS","TUSD","USDD","FDUSD","EURT","EUR","GBP","CHF","AUD","CAD","JPY","USD","UST","USDQ","USDR","EURR","EURQ","TBTC","WBTC","PAXG","XAUT","LSETH","CMETH","METH","WETH","STETH","SBTC","USD1","USDE","AUSD","USTC","BUSD","GUSD","EUROC","EURC","ZUSD","ZEUR","ZGBP","LSSOL","MSOL","JITOSOL"}
TIERS = [(50000,.0015,.0030),(25000,.0020,.0035),(10000,.0022,.0038),(2500,.0030,.0060),(0,.0040,.0080)]
def fee_for(vol30, maker, cfg):
    if not cfg["tier"]: return (.0040 if maker else .0080)
    for th, mk, tk in TIERS:
        if vol30 >= th: return mk if maker else tk

def load():
    raw = json.load(open(os.path.join(P, "ohlc_cache.json")))
    raw = {a: {int(k): tuple(v) for k, v in d.items()} for a, d in raw.items() if a not in STABLE and not a.endswith("USD")}
    data = {}
    for a, d in raw.items():
        if len(d) < 80: continue
        x = ind(d); ts = sorted(d); C = [d[t][2] for t in ts]
        for i, t in enumerate(ts):
            x[t]["h"], x[t]["l"] = d[t][0], d[t][1]; x[t]["v"] = d[t][3] * d[t][2]
            if i >= 20:
                r = [C[j]/C[j-1]-1 for j in range(i-19, i+1)]; sd = S.pstdev(r) * math.sqrt(20)
                x[t]["mra"] = (C[i]/C[i-20]-1) / sd if sd > 0 else None
            else: x[t]["mra"] = None
        data[a] = x
    return data

def universe(data, days, fr):
    """top 10 par volume USD moyen 7 j antérieurs (proxy du volume 24 h), historique >= 60 j, figé pour la journée."""
    U = {}
    for t in days:
        sc = []
        for a, x in data.items():
            if fr is not None and a not in fr: continue
            if t not in x or not x[t]["ok"]: continue
            vs = [x[t-86400*i]["v"] for i in range(0, 7) if t-86400*i in x]
            if len(vs) >= 5: sc.append((sum(vs)/len(vs), a))
        U[t] = [a for _, a in sorted(sc, reverse=True)[:10]]
    return U

BASE = dict(fr=False, tier=False, maker=False, k=None, keep_rank=3, min_hold=1, chal=0.0, mom="v104", top=3, w=0.33, atrm=3.0)

def run(cfg, data, days, U):
    btc = data["XBT"]; cash = C0; pos = {}; pend = {}; vlog = []  # (t, notional)
    fees = 0.0; gross_closed = []; holds = []; trades = 0; eqs = []; peak = C0; mdd = 0; rt = 0
    def vol30(t): return sum(n for tt, n in vlog if t - 30*86400 < tt <= t)
    def mom(x): return x["mom"] if cfg["mom"] == "v104" else x["mra"]
    def buy(a, t, px, maker, amt):
        nonlocal cash, fees, trades
        f = fee_for(vol30(t), maker, cfg); p = px if maker else px*(1+SLIP)
        q = amt/(p*(1+f)); fee = q*p*f; cash -= q*p + fee; fees += fee; trades += 1; vlog.append((t, q*p))
        if a in pos: P0 = pos[a]; P0["cost"] += q*p+fee; P0["q"] += q
        else: pos[a] = dict(q=q, cost=q*p+fee, hi=data[a][t]["c"], t0=t, last=data[a][t]["c"], sold=0.0)
    def sell(a, t, px, maker, q=None, why=""):
        nonlocal cash, fees, trades, rt
        P0 = pos[a]; q = P0["q"] if q is None else min(q, P0["q"]); f = fee_for(vol30(t), maker, cfg); p = px if maker else px*(1-SLIP)
        fee = q*p*f; cash += q*p - fee; fees += fee; trades += 1; vlog.append((t, q*p))
        frac = q/P0["q"]; P0["sold"] += q*p - fee; P0["q"] -= q
        if P0["q"] <= 1e-12 or frac > 0.999:
            pnl = P0["sold"] - P0["cost"]; gross_closed.append(pnl); holds.append((t-P0["t0"])/86400); rt += 1; del pos[a]
        else:  # vente partielle : on garde la base de coût au prorata
            pass
    prev_state = None
    for i, t in enumerate(days):
        bx = btc[t]
        # 1) exécuter les ordres maker en attente (placés hier à close t-1) si le prix de t croise la limite
        for a, o in list(pend.items()):
            x = data[a].get(t)
            if not x: del pend[a]; continue
            if o["side"] == "buy" and x["l"] < o["lim"] and a not in pos:
                buy(a, t, o["lim"], True, min(o["amt"], cash))
                pos[a]["hi"] = max(pos[a]["hi"], x["c"])
            elif o["side"] == "sell" and a in pos and x["h"] > o["lim"]:
                sell(a, t, o["lim"], True, o.get("q"))
            elif o["side"] == "sell" and a in pos and o.get("fallback"):
                o["tries"] = o.get("tries", 0) + 1
                if o["tries"] >= 1: sell(a, t, x["c"], False, o.get("q"))  # sortie B non remplie : taker le lendemain
            del pend[a]
        # 2) régime BTC
        if cfg["k"] is None: state = "on" if bx["c"] > bx["e50"] else "off"
        else:
            up, lo = bx["e50"] + cfg["k"]*bx["atr"], bx["e50"] - cfg["k"]*bx["atr"]
            state = "on" if bx["c"] > up else ("off" if bx["c"] < lo else "neutral")
        univ = U[t]
        # 3) classement momentum de l'univers
        rk = sorted([a for a in univ if t in data[a] and data[a][t]["ok"] and mom(data[a][t]) is not None], key=lambda a: -mom(data[a][t]))
        rank = {a: j+1 for j, a in enumerate(rk)}
        def entry_ok(x):
            if x["mom"] is None or mom(x) is None: return False
            tr = x["c"] > x["e50"] and x["e20"] > x["e50"]
            n = tr + bool(x["macd"]) + (50 < x["rsi"] < 75) + (x["adx"] > 20 and x["pdi"] > x["mdi"]) + bool(x["volup"])
            return tr and n >= 4
        cands = [a for a in rk if entry_ok(data[a][t])]
        # 4) sorties
        for a in list(pos):
            x = data[a].get(t)
            if not x: sell(a, days[i-1], pos[a]["last"], False); continue
            p = pos[a]; p["last"] = x["c"]; p["hi"] = max(p["hi"], x["c"]); stop = p["hi"] - cfg["atrm"]*x["atr"]
            if x["c"] <= stop: sell(a, t, x["c"], False); continue            # A : stop ATR -> taker
            if state == "off": sell(a, t, x["c"], False); continue             # risk-off dur -> taker
            if x["c"] < x["e50"]:                                              # B : tendance propre cassée
                if cfg["maker"]: pend[a] = dict(side="sell", lim=x["c"], fallback=True)
                else: sell(a, t, x["c"], False)
                continue
            held = (t - p["t0"])/86400
            if cfg["keep_rank"] == 3 and cfg["chal"] == 0 and cfg["min_hold"] == 1:   # V1.04 : hors top 3 des candidats après 24 h
                tgt = [b for b in pos if b in rank][:0]
                held_ok = [b for b in pos if data[b].get(t) and data[b][t]["c"] > data[b][t]["e50"]]
                target = held_ok + [b for b in cands if b not in held_ok][:max(0, cfg["top"]-len(held_ok))]
                out_c = a not in [b for b in cands][:cfg["top"]] and a not in target
                # V1.04 : C = pas dans la cible ; cible = détenues gardées + meilleurs candidats -> une détenue gardée sort seulement si son rang > top et un candidat meilleur existe
                worse = rank.get(a, 99) > cfg["top"] and any(b not in pos and rank[b] < rank.get(a, 99) for b in cands)
                if held >= 1 and worse:
                    if cfg["maker"]: pend[a] = dict(side="sell", lim=x["c"])
                    else: sell(a, t, x["c"], False)
            else:
                ra = rank.get(a, 99)
                if held >= cfg["min_hold"] and ra > cfg["keep_rank"]:
                    ch = [b for b in cands if b not in pos and mom(data[b][t]) > mom(x) + cfg["chal"]*abs(mom(x))]
                    if ch:
                        if cfg["maker"]: pend[a] = dict(side="sell", lim=x["c"])
                        else: sell(a, t, x["c"], False)
        eq = cash + sum(p["q"]*p["last"] for p in pos.values())
        # 5) entrées (régime risk-on seulement), top N candidats, 33 %
        if state == "on":
            nslots = cfg["top"] - len([a for a in pos if not (a in pend and pend[a]["side"] == "sell")])
            for a in cands[:cfg["top"]]:
                if nslots <= 0: break
                if a in pos or a in pend: continue
                amt = min(cfg["w"]*eq, cash*0.999)
                if amt < 25: break
                if cfg["maker"]: pend[a] = dict(side="buy", lim=data[a][t]["c"], amt=amt)
                else: buy(a, t, data[a][t]["c"], False, amt)
                nslots -= 1
        eq = cash + sum(p["q"]*p["last"] for p in pos.values())
        peak = max(peak, eq); mdd = max(mdd, 1-eq/peak); eqs.append(eq)
        if eq <= C0*0.70: break  # coupe-circuit
    for a, p in pos.items(): gross_closed.append(p["sold"] + p["q"]*p["last"] - p["cost"]); holds.append((days[-1]-p["t0"])/86400)
    W = sum(x for x in gross_closed if x > 0); L = -sum(x for x in gross_closed if x < 0)
    months = len(days)/30.44; net = eqs[-1]-C0
    return dict(ret=eqs[-1]/C0-1, mdd=mdd, fees=fees, fees_over_gross=(fees/(net+fees) if net+fees > 0 else None), gross=net+fees,
                rt_month=rt/months, median_hold=S.median(holds) if holds else None, pf=(W/L if L else None), trades=trades, eqs=eqs)

def bench(data, days):
    b = data["XBT"]; e = [C0*(1-.008-SLIP)*b[t]["c"]/b[days[0]]["c"] for t in days]; pk = 0; md = 0
    for x in e: pk = max(pk, x); md = max(md, 1-x/pk)
    return dict(ret=e[-1]/C0-1, mdd=md)

if __name__ == "__main__":
    data = load(); btc = data["XBT"]; days = [t for t in sorted(btc) if btc[t]["ok"]]
    fr = set(json.load(open(os.path.join(D, "fr_usd_bases.json")))["bases"]) | {"XBT", "XDG"}
    cut = days[int(len(days)*0.6)]; OPT = [t for t in days if t < cut]; VAL = [t for t in days if t >= cut]
    f = lambda t: datetime.fromtimestamp(t, timezone.utc).strftime("%d/%m/%Y")
    Uus = universe(data, days, None); Ufr = universe(data, days, fr)
    def R(cfg, ds): return run(cfg, data, ds, Ufr if cfg["fr"] else Uus)
    out = dict(periods=dict(opt=f"{f(OPT[0])} – {f(OPT[-1])} ({len(OPT)} j)", val=f"{f(VAL[0])} – {f(VAL[-1])} ({len(VAL)} j)"),
               n_assets=len(data), steps=[], grid={}, btc=dict(opt=bench(data, OPT), val=bench(data, VAL)))
    print(out["periods"])
    def sel(cfg, key, values):
        res = {}
        for v in values:
            c = dict(cfg); c.update(v if isinstance(v, dict) else {key: v}); r = R(c, OPT); res[json.dumps(v)] = {k: r[k] for k in r if k != "eqs"}
            print("  grid", key, v, f"opt ret {r['ret']*100:.1f}% mdd {r['mdd']*100:.1f}%")
        best = max(res, key=lambda k: res[k]["ret"] - 0.5*res[k]["mdd"])  # critère : rendement net − 0,5 × drawdown max (période d'optimisation uniquement)
        out["grid"][key] = dict(results=res, chosen=json.loads(best)); v = json.loads(best)
        c = dict(cfg); c.update(v if isinstance(v, dict) else {key: v}); return c
    cfg = dict(BASE); steps = [("V1.04 reproduite", cfg)]
    cfg = dict(cfg, fr=True); steps.append(("+ univers FR (country_code=FR)", cfg))
    cfg = dict(cfg, tier=True); steps.append(("+ palier de frais dynamique 30 j", cfg))
    cfg = dict(cfg, maker=True); steps.append(("+ maker-first post-only (remplissage prudent)", cfg))
    cfg = sel(cfg, "k", [0, 0.15, 0.25, 0.5]); steps.append((f"+ hystérésis BTC 3 états k={cfg['k']}", cfg))
    cfg = sel(cfg, "rot", [dict(keep_rank=K, min_hold=H, chal=0.10) for K in (3, 4, 5, 6) for H in (1, 2)]); steps.append((f"+ tampon de rang ≤{cfg['keep_rank']}, détention ≥{cfg['min_hold']*24} h, challenger +10 %", cfg))
    cfg = sel(cfg, "mom", ["v104", "radj"]); steps.append((f"+ momentum {'rendement 20 j / volatilité 20 j' if cfg['mom']=='radj' else 'V1.04 (½ r30 + ½ r7)'}", cfg))
    for name, c in steps:
        ro, rv = R(c, OPT), R(c, VAL)
        out["steps"].append(dict(name=name, cfg=c, opt={k: ro[k] for k in ro if k != "eqs"}, val={k: rv[k] for k in rv if k != "eqs"}))
        print(f"{name:55} OPT {ro['ret']*100:7.1f}% dd {ro['mdd']*100:5.1f}% | VAL {rv['ret']*100:7.1f}% dd {rv['mdd']*100:5.1f}% fees {rv['fees']:.0f}$ rt/m {rv['rt_month']:.1f} hold {rv['median_hold']} pf {rv['pf']}")
    rf = R(cfg, VAL); out["final_val_curve"] = [dict(t=f(t), eq=e) for t, e in zip(VAL, rf["eqs"])]
    out["final_cfg"] = cfg; print("BTC", out["btc"])
    json.dump(out, open(os.path.join(D, "ablation_results.json"), "w"), indent=1, ensure_ascii=False)
