#!/usr/bin/env python3
"""Kraken paper-trading sim: one idempotent cycle per UTC hour slot. Public data only, no real orders."""
import json, sqlite3, sys, time, urllib.request, urllib.parse, os, math
from datetime import datetime, timezone
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D); DB = os.environ.get("SIM_DB", os.path.join(D, "sim.db"))
C0 = 6605.10; C0_SOURCE = "fallback: Cyril's Kraken value 24/10/2026 14:36 UTC (MCP connector exposes no live balance)"
FEE, SLIP = 0.008, 0.0005  # V1.02 : 0,80 % = taker Tier 1 Kraken (exécution au ask/bid)
MAX_W, TOP_N, MAX_SPREAD = 0.35, 3, 0.003
KILL_DD = 0.30; ATR_MULT = 3.0; MIN_HOLD_H = 24; REBAL_BAND = 0.10; MIN_ORDER = 25.0
STABLE = {"USDT","USDC","DAI","PYUSD","USDG","FDUSD","TUSD","USDE","USDS","EUR","GBP","EURC","RLUSD","USD1","USDQ","USDR","GHO","AUD","CAD","CHF","JPY","PAXG","XAUT","TBTC","WBTC"}
API = "https://api.kraken.com/0/public/"

def get(ep, **p):
    url = API + ep + ("?" + urllib.parse.urlencode(p) if p else "")
    for i in range(3):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"kraken-sim"}), timeout=30))
            if r.get("error"): raise RuntimeError(r["error"])
            return r["result"]
        except Exception as e:
            if i == 2: raise
            time.sleep(2)

def db():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
    CREATE TABLE IF NOT EXISTS cycles(slot TEXT PRIMARY KEY, ts TEXT, status TEXT, note TEXT);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, slot TEXT, ts TEXT, pair TEXT, asset TEXT, side TEXT, qty REAL, price REAL, notional REAL, fee REAL, reason TEXT, pnl REAL);
    CREATE TABLE IF NOT EXISTS positions(asset TEXT PRIMARY KEY, pair TEXT, qty REAL, avg_price REAL, entry_ts TEXT, high REAL, stop REAL);
    CREATE TABLE IF NOT EXISTS equity(slot TEXT PRIMARY KEY, ts TEXT, equity REAL, cash REAL, btc_hold REAL, exposure REAL);
    CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, slot TEXT, ts TEXT, asset TEXT, action TEXT, reason TEXT);
    CREATE TABLE IF NOT EXISTS indicators(slot TEXT, ts TEXT, asset TEXT, close REAL, ema20 REAL, ema50 REAL, macd_ok INTEGER, rsi REAL, adx REAL, pdi REAL, mdi REAL, vol_ok INTEGER, mom REAL, score INTEGER, regime INTEGER, trend_ok INTEGER, rsi_ok INTEGER, adx_ok INTEGER, PRIMARY KEY(slot, asset));
    CREATE TABLE IF NOT EXISTS prices(slot TEXT, asset TEXT, bid REAL, ask REAL, last REAL, PRIMARY KEY(slot, asset));
    """)
    cols = {r[1] for r in c.execute("PRAGMA table_info(indicators)")}
    for col in ("vol_ratio", "macd_hist"):
        if col not in cols: c.execute(f"ALTER TABLE indicators ADD COLUMN {col} REAL")  # V1.03 : valeurs affichées (anciennes lignes = NULL)
    if "test" not in {r[1] for r in c.execute("PRAGMA table_info(orders)")}: c.execute("ALTER TABLE orders ADD COLUMN test INTEGER DEFAULT 0")  # achat test ponctuel
    return c

def meta(c, k, v=None):
    if v is None:
        r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone(); return r[0] if r else None
    c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, str(v)))

def universe():
    pairs = get("AssetPairs")
    usd = {k: v for k, v in pairs.items() if v.get("quote") in ("ZUSD","USD") and v.get("status","online")=="online" and not k.endswith(".d")}
    tick = get("Ticker")
    rows = []
    for k, v in usd.items():
        t = tick.get(k)
        if not t: continue
        base = v["wsname"].split("/")[0]
        if base in STABLE or base.startswith("USD"): continue
        bid, ask, last = float(t["b"][0]), float(t["a"][0]), float(t["c"][0])
        if bid <= 0: continue
        spread = (ask - bid) / ((ask + bid) / 2)
        vol_usd = float(t["v"][1]) * float(t["p"][1])
        rows.append(dict(pair=k, asset=base, bid=bid, ask=ask, last=last, spread=spread, vol=vol_usd, ordermin=float(v.get("ordermin", 0))))
    rows = [r for r in rows if r["spread"] <= MAX_SPREAD]
    rows.sort(key=lambda r: -r["vol"])
    return rows[:10], {r["asset"]: r for r in rows}

def ohlc(pair, iv):
    r = get("OHLC", pair=pair, interval=iv)
    k = [x for x in r if x != "last"][0]
    return [(float(a[2]), float(a[3]), float(a[4])) for a in r[k]][:-1]  # closed candles: high, low, close

def atr(c, n=14):
    tr = [max(c[i][0]-c[i][1], abs(c[i][0]-c[i-1][2]), abs(c[i][1]-c[i-1][2])) for i in range(1, len(c))]
    return sum(tr[-n:]) / n

def sma(x, n): return sum(x[-n:]) / n

def depth_ok(pair, side, qty):
    d = get("Depth", pair=pair, count=25); k = list(d)[0]
    book = d[k]["asks" if side == "buy" else "bids"]
    return sum(float(l[1]) for l in book) >= qty

def main():
    now = datetime.now(timezone.utc); slot = now.strftime("%Y%m%d%H"); ts = now.isoformat(timespec="seconds")
    c = db()
    if c.execute("SELECT 1 FROM cycles WHERE slot=?", (slot,)).fetchone():
        print(f"slot {slot} already done; nothing to do"); return
    if meta(c, "C0") is None:
        meta(c, "C0", C0); meta(c, "C0_source", C0_SOURCE); meta(c, "cash", C0); meta(c, "start_ts", ts); meta(c, "killed", 0)
    dec = lambda a, act, why: c.execute("INSERT INTO decisions(slot,ts,asset,action,reason) VALUES(?,?,?,?,?)", (slot, ts, a, act, why))
    top, allq = universe()
    btc = allq.get("BTC") or allq.get("XBT")
    if meta(c, "btc_qty") is None:
        meta(c, "btc_qty", C0 * (1 - FEE) / (btc["ask"] * (1 + SLIP)))
    cash = float(meta(c, "cash")); killed = meta(c, "killed") == "1"
    pos = {r[0]: dict(pair=r[1], qty=r[2], avg=r[3], entry=r[4], high=r[5], stop=r[6]) for r in c.execute("SELECT * FROM positions")}
    # quotes for held assets not in universe
    for a, p in pos.items():
        if a not in allq:
            t = list(get("Ticker", pair=p["pair"]).values())[0]
            allq[a] = dict(pair=p["pair"], asset=a, bid=float(t["b"][0]), ask=float(t["a"][0]), last=float(t["c"][0]))
    def equity(): return cash + sum(p["qty"] * allq[a]["bid"] for a, p in pos.items())
    tests = set(json.loads(meta(c, "test_assets") or "[]"))  # positions issues d'un achat test (state/test_buy.json)
    def fill(a, side, qty, why, test=0):
        nonlocal cash
        q = allq[a]; pair = q["pair"]
        if not depth_ok(pair, side, qty): dec(a, "skip", f"profondeur insuffisante pour {side} {qty:.6g}"); return False
        px = q["ask"] * (1 + SLIP) if side == "buy" else q["bid"] * (1 - SLIP)
        notional = qty * px; fee = notional * FEE; pnl = None
        if side == "buy":
            cash -= notional + fee
            p = pos.get(a)
            if p: p["avg"] = (p["avg"] * p["qty"] + notional + fee) / (p["qty"] + qty); p["qty"] += qty
            else: pos[a] = dict(pair=pair, qty=qty, avg=(notional + fee) / qty, entry=ts, high=q["last"], stop=None)
        else:
            cash += notional - fee; p = pos[a]
            pnl = (px * (1 - FEE) - p["avg"]) * qty
            p["qty"] -= qty
            test = test or int(a in tests)
            if p["qty"] * q["bid"] < 1: del pos[a]; tests.discard(a)
        c.execute("INSERT INTO orders(slot,ts,pair,asset,side,qty,price,notional,fee,reason,pnl,test) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                  (slot, ts, pair, a, side, qty, px, notional, fee, why, pnl, test))
        dec(a, side, why); print(f"{side.upper()} {qty:.6g} {a} @ {px:.6g} fee {fee:.2f} — {why}"); return True

    note = ""
    if killed:
        note = "kill-switch active; no trading"
    else:
        eq = equity(); dd = 1 - eq / C0
        if dd >= KILL_DD:
            for a in list(pos): fill(a, "sell", pos[a]["qty"], f"COUPE-CIRCUIT : drawdown {dd:.1%} >= 30% depuis C0")
            meta(c, "killed", 1); note = "kill-switch triggered"
        else:
            # signals — stratégie B « confluence 5 indicateurs + régime BTC » (bougies journalières clôturées)
            from backtest import ind
            def daily(pair):
                r = get("OHLC", pair=pair, interval=1440); k = [x for x in r if x != "last"][0]
                return {int(a[0]): (float(a[2]), float(a[3]), float(a[4]), float(a[6])) for a in r[k][:-1]}
            sig = {}
            cand = {r["asset"]: r for r in top}
            for a in pos: cand.setdefault(a, allq[a])
            bt = ind(daily(btc["pair"])); bx = bt[max(bt)]
            regime = bx["c"] > bx["e50"]
            dec("BTC", "régime", f"régime BTC {'HAUSSIER' if regime else 'BAISSIER'} (clôture {bx['c']:.0f} vs EMA50 {bx['e50']:.0f})")
            for a, q in cand.items():
                try: d = ind(daily(q["pair"]))
                except Exception as e: dec(a, "skip", f"erreur OHLC {e}"); continue
                x = d[max(d)]
                if not x["ok"] or x["mom"] is None: dec(a, "skip", "historique insuffisant"); continue
                conf = []
                if x["c"] > x["e50"] and x["e20"] > x["e50"]: conf.append("EMA20>EMA50")
                if x["macd"]: conf.append("MACD>signal")
                if 50 < x["rsi"] < 75: conf.append(f"RSI {x['rsi']:.0f}")
                if x["adx"] > 20 and x["pdi"] > x["mdi"]: conf.append(f"ADX {x['adx']:.0f}")
                if x["volup"]: conf.append("volume 7j>30j")
                c.execute("INSERT OR REPLACE INTO indicators(slot,ts,asset,close,ema20,ema50,macd_ok,rsi,adx,pdi,mdi,vol_ok,mom,score,regime,trend_ok,rsi_ok,adx_ok,vol_ratio,macd_hist) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (slot, ts, a, x["c"], x["e20"], x["e50"], int(bool(x["macd"])), x["rsi"], x["adx"], x["pdi"], x["mdi"], int(bool(x["volup"])), x["mom"], len(conf), int(regime),
                          int(x["c"] > x["e50"] and x["e20"] > x["e50"]), int(50 < x["rsi"] < 75), int(x["adx"] > 20 and x["pdi"] > x["mdi"]), x["vr"], x["mh"]))
                entry = regime and "EMA20>EMA50" in conf and len(conf) >= 4
                keep = regime and x["c"] > x["e50"]
                sig[a] = dict(mom=x["mom"], trend=entry, keep=keep, atr=x["atr"], conf=conf, in_top=a in [r["asset"] for r in top])
            meta(c, "last_signals", json.dumps(sig))
            # 1) stops suiveurs ATR (3×ATR journalier)
            for a in list(pos):
                p = pos[a]; s = sig.get(a); last = allq[a]["last"]
                p["high"] = max(p["high"] or last, last)
                if s: p["stop"] = max(p["stop"] or 0, p["high"] - ATR_MULT * s["atr"])
                if p["stop"] and allq[a]["bid"] <= p["stop"]:
                    fill(a, "sell", p["qty"], f"stop suiveur ATR touché : bid {allq[a]['bid']:.6g} <= stop {p['stop']:.6g}")
            stopped = {r[0] for r in c.execute("SELECT asset FROM orders WHERE slot=? AND side='sell'", (slot,))}
            ranked = sorted([a for a, s in sig.items() if s["in_top"] and s["trend"] and a not in stopped], key=lambda a: -sig[a]["mom"])
            held = [a for a in pos if sig.get(a, {}).get("keep")]
            target = held + [a for a in ranked if a not in held][:max(0, TOP_N - len(held))]
            for a, s in sig.items():
                dec(a, "signal", f"{len(s['conf'])}/5 confirmés : {', '.join(s['conf']) or 'aucun'} ; momentum {s['mom']:+.2%}{' -> CIBLE' if a in target else ''}")
            # 3) exits (respect min hold unless trend broken)
            for a in list(pos):
                if a in target: continue
                p = pos[a]; held_h = (now - datetime.fromisoformat(p["entry"])).total_seconds() / 3600; s = sig.get(a)
                broken = (s is None) or (not s["keep"])
                if a in tests and broken and held_h < MIN_HOLD_H:  # achat test : détention min. 24h avant sortie sur tendance (stop ATR toujours actif)
                    dec(a, "hold", f"position test : sortie tendance/régime différée, détention min. {MIN_HOLD_H}h non atteinte ({held_h:.0f}h)"); continue
                if a in tests and not broken and held_h < MIN_HOLD_H:
                    dec(a, "hold", f"position test : détention min. {MIN_HOLD_H}h ({held_h:.0f}h)"); continue
                if broken or held_h >= MIN_HOLD_H:
                    fill(a, "sell", p["qty"], "sortie : clôture < EMA50 ou régime BTC baissier" if broken else f"sortie : sorti du top {TOP_N} momentum (détenu {held_h:.0f}h)")
                else: dec(a, "hold", f"hors cible mais détention min. {MIN_HOLD_H}h non atteinte ({held_h:.0f}h), tendance intacte")
            # 4) entries / rebalance with band
            w = min(MAX_W, 0.33)  # V1.01: poids cible 33 % (était non défini)
            for a in target:
                if a in tests and not sig[a]["trend"]:  # pas de redimensionnement d'une position test sans signal 4/5
                    dec(a, "hold", "position test conservée (pas de signal d'entrée 4/5, pas de redimensionnement)"); continue
                tv = w * eq; cv = pos[a]["qty"] * allq[a]["bid"] if a in pos else 0
                diff = tv - cv
                if abs(diff) < max(MIN_ORDER, REBAL_BAND * tv):
                    if a in pos: dec(a, "hold", f"dans la bande de rééquilibrage (actuel {cv:.0f} vs cible {tv:.0f} USD)")
                    continue
                if diff > 0:
                    spend = min(diff, cash / (1 + FEE) * 0.999)
                    if spend < MIN_ORDER: dec(a, "skip", "liquidités insuffisantes"); continue
                    qty = spend / (allq[a]["ask"] * (1 + SLIP))
                    fill(a, "buy", qty, f"{'entrée' if cv == 0 else 'renfort'}: confirmé par {', '.join(sig[a]['conf'])} + régime BTC haussier ; momentum {sig[a]['mom']:+.2%} ; cible {w:.0%} de l'équité")
                elif a in pos:
                    fill(a, "sell", -diff / allq[a]["bid"], f"allègement au poids cible {w:.0%}")
            if not target: dec("ALL", "cash", "aucun actif avec ≥4/5 confirmations (dont EMA20>EMA50) et régime BTC haussier -> reste en liquidités")
            # 5) achat test ponctuel (hors stratégie), consommé une seule fois
            tf = os.path.join(D, "state", "test_buy.json")
            if os.path.exists(tf):
                try:
                    tb = json.load(open(tf)); pair = tb.get("pair", "XBTUSD"); pct = float(tb.get("pct", 0.05)); why = tb.get("reason", "Achat test hors stratégie")
                    a = next((k for k, q in allq.items() if q["pair"] == pair or k + "USD" == pair or k == pair), None)
                    if a is None: res = f"paire {pair} introuvable"
                    else:
                        spend = min(pct * equity(), cash / (1 + FEE) * 0.999)
                        if spend < MIN_ORDER: res = "liquidités insuffisantes"
                        else:
                            qty = spend / (allq[a]["ask"] * (1 + SLIP))
                            if fill(a, "buy", qty, f"TEST : {why}", test=1):
                                tests.add(a); res = "ok"
                                if a in sig and pos[a]["stop"] is None: pos[a]["stop"] = pos[a]["high"] - ATR_MULT * sig[a]["atr"]
                            else: res = "profondeur insuffisante"
                except Exception as e: res = f"erreur {e}"
                tb = dict(tb) if isinstance(tb, dict) else {}
                tb.update(consumed_slot=slot, consumed_ts=ts, result=res)
                json.dump(tb, open(os.path.join(D, "state", f"test_buy_consumed_{slot}.json"), "w"), ensure_ascii=False, indent=1); os.remove(tf)
                print(f"test_buy: {res}")
            # initialise stops for new positions
            for a, p in pos.items():
                if p["stop"] is None and a in sig: p["stop"] = p["high"] - ATR_MULT * sig[a]["atr"]
    # persist
    c.execute("DELETE FROM positions")
    for a, p in pos.items(): c.execute("INSERT INTO positions VALUES(?,?,?,?,?,?,?)", (a, p["pair"], p["qty"], p["avg"], p["entry"], p["high"], p["stop"]))
    meta(c, "cash", cash); meta(c, "test_assets", json.dumps(sorted(a for a in tests if a in pos)))
    for a, q in allq.items():
        if a in pos or a in [r["asset"] for r in top] or a in (btc["asset"], "ETH"):
            c.execute("INSERT OR REPLACE INTO prices VALUES(?,?,?,?,?)", (slot, a, q["bid"], q["ask"], q["last"]))
    eq = equity(); exp = 1 - cash / eq if eq else 0
    btch = float(meta(c, "btc_qty")) * btc["bid"]
    c.execute("INSERT INTO equity VALUES(?,?,?,?,?,?)", (slot, ts, eq, cash, btch, exp))
    c.execute("INSERT INTO cycles VALUES(?,?,?,?)", (slot, ts, "ok", note))
    meta(c, "universe", json.dumps([r["asset"] for r in top]))
    c.commit()
    print(f"slot {slot}: equity {eq:.2f} USD, cash {cash:.2f}, exposure {exp:.0%}, BTC hold {btch:.2f}, C0 {C0}")

if __name__ == "__main__": main()
