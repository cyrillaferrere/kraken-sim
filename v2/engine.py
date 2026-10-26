#!/usr/bin/env python3
"""Kraken Sim V2 — simulation spot USDC, API publique, aucune cle privee."""
import json, math, os, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
INITIAL = 6605.10
FEE = 0.004
SLIPPAGE = 0.0015
ASSETS = ["BTC", "ETH", "SOL", "XRP", "ADA", "LINK", "AVAX", "DOT"]
PAIRS = {a: f"{a}USDC" for a in ASSETS}
WEIGHTS = {"short": 0.20, "medium": 0.30, "long": 0.50}

def api(endpoint, params):
    url = "https://api.kraken.com/0/public/" + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "KrakenSimV2-Paper/1.0"}), timeout=20) as response:
        data = json.load(response)
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data["result"]

def candles(pair, interval):
    result = api("OHLC", {"pair": pair, "interval": interval})
    key = next(k for k in result if k != "last")
    now = time.time()
    return [r for r in result[key] if float(r[0]) + interval * 60 <= now]

def indicators(asset):
    pair = PAIRS[asset]
    hourly = candles(pair, 60)
    daily = candles(pair, 1440)
    if len(hourly) < 170 or len(daily) < 210:
        return None
    h = [float(r[4]) for r in hourly]
    d = [float(r[4]) for r in daily]
    def sma(x, n): return sum(x[-n:]) / n
    def score(fast, slow, price):
        return max(0.0, min(1.0, 0.5 + 5 * (fast / slow - 1))) if price > slow else 0.0
    short = score(sma(h, 12), sma(h, 48), h[-1])
    medium = score(sma(d, 10), sma(d, 30), d[-1])
    long = score(sma(d, 50), sma(d, 200), d[-1])
    ticker = api("Ticker", {"pair": pair})
    key = next(iter(ticker))
    bid, ask = float(ticker[key]["b"][0]), float(ticker[key]["a"][0])
    if bid <= 0 or ask <= 0 or (ask - bid) / ((ask + bid) / 2) > 0.003:
        return None
    return {"asset": asset, "bid": bid, "ask": ask, "spread": (ask-bid)/((ask+bid)/2),
            "signals": {"short": short, "medium": medium, "long": long},
            "last_closed_hour": int(hourly[-1][0]), "last_closed_day": int(daily[-1][0])}

def initial():
    return {"schema": 1, "engine": "V2.0.0", "strategy": "V2.0", "ux": "V2.0.0",
            "mode": "PAPER", "initial": INITIAL, "cash": INITIAL, "positions": {},
            "equity": INITIAL, "pnl_pct": 0, "fees": 0, "cycles": 0, "orders": [],
            "history": [], "signals": [], "updated": None, "status": "INITIALIZED"}

def run():
    s = json.loads(STATE.read_text()) if STATE.exists() else initial()
    slot = int(time.time() // 14400)
    if s.get("slot") == slot:
        print("Already processed this 4h slot"); return
    info = []
    errors = []
    for asset in ASSETS:
        try:
            row = indicators(asset)
            if row: info.append(row)
            else: errors.append(asset + ": insufficient history or excessive spread")
        except Exception as exc:
            errors.append(asset + ": " + str(exc)[:140])
    if len(info) < 4 or not any(x["asset"] == "BTC" for x in info):
        print("HOLD: insufficient verified market data", errors)
        s["status"] = "HOLD_DATA"; s["errors"] = errors
        STATE.write_text(json.dumps(s, indent=2) + "\n")
        return
    # Risk-on seulement si tendance BTC moyen/long terme favorable.
    btc = next(x for x in info if x["asset"] == "BTC")
    risk = (btc["signals"]["medium"] + btc["signals"]["long"]) / 2
    exposure = max(0.0, min(0.85, 0.85 * risk))
    # Allocation dynamique : chaque horizon compete pour le capital.
    candidates = []
    for x in info:
        for horizon, base in WEIGHTS.items():
            strength = x["signals"][horizon]
            if strength > 0.55:
                candidates.append((x["asset"], horizon, strength * base))
    candidates.sort(key=lambda x: x[2], reverse=True)
    candidates = candidates[:12]
    weight_sum = sum(c[2] for c in candidates)
    targets = {}
    for asset, horizon, weight in candidates:
        targets[asset] = targets.get(asset, 0) + exposure * weight / weight_sum if weight_sum else 0
    # Cap par actif; excedent conserve en USDC.
    targets = {a: min(w, 0.35) for a, w in targets.items()}
    prices = {x["asset"]: x for x in info}
    held = s.get("positions", {})
    # Equity mark-to-market au bid.
    equity = float(s["cash"]) + sum(float(q)*prices[a]["bid"] for a,q in held.items() if a in prices)
    if any(a not in prices for a in held):
        s["status"] = "HOLD_MISSING_POSITION_PRICE"; s["errors"] = errors
        STATE.write_text(json.dumps(s, indent=2) + "\n"); return
    orders = []
    # Vente avant achat, seuil de reequilibrage 2% du capital.
    for asset in sorted(set(held) | set(targets)):
        if asset not in prices: continue
        current = held.get(asset, 0) * prices[asset]["bid"]
        target = equity * targets.get(asset, 0)
        if current - target > max(25, equity * 0.02):
            qty = min(held[asset], (current-target)/prices[asset]["bid"])
            px = prices[asset]["bid"]*(1-SLIPPAGE)
            gross = qty*px; fee = gross*FEE
            s["cash"] += gross-fee; s["fees"] += fee
            held[asset] = max(0, held[asset]-qty)
            if held[asset] < 1e-10: held.pop(asset)
            orders.append({"asset":asset,"side":"SELL","qty":qty,"price":px,"fee":fee})
    for asset, horizon, weight in candidates:
        if asset not in targets or asset not in prices: continue
        current = held.get(asset, 0)*prices[asset]["ask"]
        target = equity*targets[asset]
        need = target-current
        if need <= max(25,equity*0.02): continue
        # Un seul achat par actif par cycle.
        if any(o["asset"]==asset and o["side"]=="BUY" for o in orders): continue
        budget = min(need, s["cash"]*0.98)
        if budget < 25: continue
        px = prices[asset]["ask"]*(1+SLIPPAGE)
        qty = budget/(px*(1+FEE)); fee = qty*px*FEE
        s["cash"] -= qty*px+fee; s["fees"] += fee
        held[asset] = held.get(asset,0)+qty
        orders.append({"asset":asset,"side":"BUY","qty":qty,"price":px,"fee":fee})
    s["positions"] = held
    s["equity"] = s["cash"] + sum(q*prices[a]["bid"] for a,q in held.items())
    s["pnl_pct"] = 100*(s["equity"]/s["initial"]-1)
    s["slot"] = slot; s["cycles"] = s.get("cycles",0)+1
    s["updated"] = datetime.now(timezone.utc).isoformat()
    s["status"] = "ACTIVE" if orders else "HOLD"
    s["errors"] = errors
    s["signals"] = [{**x,"target_pct":round(100*targets.get(x["asset"],0),2)} for x in info]
    for order in orders:
        order["ts"] = s["updated"]
    s["orders"] = (orders + s.get("orders",[]))[:200]
    s["history"] = (s.get("history",[]) + [{"ts":s["updated"],"equity":round(s["equity"],4),"cash":round(s["cash"],4),"orders":len(orders)}])[-500]
    STATE.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n")
    print("V2",s["status"],"equity",s["equity"],"orders",len(orders))

if __name__ == "__main__": run()
