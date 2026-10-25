#!/usr/bin/env python3
"""Aperçu lecture seule des 5 indicateurs (données publiques Kraken) -> indicators_preview.json. N'écrit rien dans sim.db, ne trade pas."""
import json, os, sys, sqlite3
from datetime import datetime, timezone
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from cycle import get
from backtest import ind
c = sqlite3.connect(os.path.join(D, "sim.db")); uni = json.loads(dict(c.execute("SELECT k,v FROM meta"))["universe"])
pairs = {v["wsname"].split("/")[0]: k for k, v in get("AssetPairs").items() if v.get("quote") in ("ZUSD", "USD") and not k.endswith(".d")}
def daily(p):
    r = get("OHLC", pair=p, interval=1440); k = [x for x in r if x != "last"][0]
    return {int(a[0]): (float(a[2]), float(a[3]), float(a[4]), float(a[6])) for a in r[k][:-1]}
b = ind(daily(pairs["XBT"])); bx = b[max(b)]; regime = bx["c"] > bx["e50"]; rows = []
for a in uni:
    d = ind(daily(pairs[a])); x = d[max(d)]
    t = x["c"] > x["e50"] and x["e20"] > x["e50"]; r = 50 < x["rsi"] < 75; ad = x["adx"] > 20 and x["pdi"] > x["mdi"]
    rows.append(dict(asset=a, trend=t, macd=bool(x["macd"]), rsi_ok=r, rsi=x["rsi"], adx_ok=ad, adx=x["adx"], vol=bool(x["volup"]), mom=x["mom"], score=sum([t, bool(x["macd"]), r, ad, bool(x["volup"])]), regime=regime))
json.dump(dict(ts=datetime.now(timezone.utc).isoformat(timespec="seconds"), rows=rows), open(os.path.join(D, "indicators_preview.json"), "w"))
print(len(rows), "regime", regime)
