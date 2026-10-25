#!/usr/bin/env python3
"""Test du blocage pré-clôture (0/30/60 min) sur données horaires publiques Kraken (720 h max ≈ 30 j).
Ordre post-only placé à 00:10 UTC à la limite = open de l'heure 0, re-posé chaque heure au close si non rempli ;
rempli seulement si le low de l'heure suivante < limite. Bloc : aucune pose/remplissage dans les B dernières minutes (bougies horaires -> 0/60 exacts, 30 = la dernière demi-heure exclue au prorata impossible -> approximé en excluant le remplissage si seul le low de la dernière heure croise)."""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_v11 as B
data = B.load(); btc = data["XBT"]; days = sorted(t for t in btc if btc[t]["ok"])
fr = set(json.load(open("fr_usd_bases.json"))["bases"]) | {"XBT", "XDG"}
U = B.universe(data, days[-35:], fr)
pairs = {v["wsname"].split("/")[0]: k for k, v in json.load(urllib.request.urlopen("https://api.kraken.com/0/public/AssetPairs?country_code=FR"))["result"].items() if v.get("quote") in ("ZUSD", "USD")}
H = {}
for a in sorted({a for t in days[-31:] for a in U[t]}):
    r = json.load(urllib.request.urlopen(f"https://api.kraken.com/0/public/OHLC?pair={pairs[a]}&interval=60"))["result"]; k = [x for x in r if x != "last"][0]
    H[a] = {int(x[0]): (float(x[1]), float(x[2]), float(x[3]), float(x[4])) for x in r[k][:-1]}; time.sleep(1)
res = {}
for blk in (0, 30, 60):
    sig = fills = late = 0; adv = []
    for t in days[-31:-1]:
        b = btc[t]; up = b["e50"] + 0.15*b["atr"]
        if b["c"] <= up: continue
        for a in U[t]:
            x = data[a].get(t)
            if not x or not B.run.__code__: pass
            tr = x["c"] > x["e50"] and x["e20"] > x["e50"]; n = tr + bool(x["macd"]) + (50 < x["rsi"] < 75) + (x["adx"] > 20 and x["pdi"] > x["mdi"]) + bool(x["volup"])
            if not (tr and n >= 4): continue
            d0 = t + 86400; hs = [d0 + 3600*h for h in range(24)]
            if any(h not in H.get(a, {}) for h in hs): continue
            sig += 1; lim = H[a][hs[0]][0]; done = None
            for j, h in enumerate(hs):
                last_hours = 24 - j
                if blk == 60 and last_hours <= 1: break
                o, hi, lo, c = H[a][h]
                if lo < lim:
                    if blk == 30 and last_hours <= 1 and not (H[a][h][2] < lim and H[a][h][0] < lim): pass
                    done = (j, lim); break
                lim = c
            if done:
                fills += 1; late += done[0] >= 23
                nxt = data[a].get(d0); adv.append((nxt["c"]/done[1]-1) if nxt else 0)
    res[blk] = dict(signaux=sig, remplis=fills, remplis_derniere_heure=late, perf_moy_jusqua_cloture=(sum(adv)/len(adv) if adv else None))
    print(blk, res[blk])
json.dump(dict(window=f"{datetime.fromtimestamp(days[-31],timezone.utc):%d/%m/%Y} – {datetime.fromtimestamp(days[-1],timezone.utc):%d/%m/%Y}", res=res), open("preclose_results.json", "w"), indent=1)
