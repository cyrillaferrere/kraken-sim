#!/usr/bin/env python3
"""Kraken Sim V1.1 — moteur paper trading (AUCUN ordre réel ; API publique Kraken uniquement).
- Décision quotidienne UNE fois après 00:00 UTC (cible ~00:10) sur bougies journalières CLÔTURÉES (contrôle d'horodatage),
  instantané figé pour la journée (meta daily_snapshot). Rattrapage autorisé jusqu'à 22:59 UTC si la décision a échoué.
- Cycles intraday (horaires) : stops ATR (taker), coupe-circuit, exécution/relance des ordres post-only en attente. Aucun nouveau signal.
- Aucun nouvel achat (pose ou remplissage) dans les BLOCK_MIN minutes avant 00:00 UTC.
- Univers : AssetPairs?country_code=FR (repli : exclusion XMR + liste EEA), quote USD, hors stablecoins, spread <= 0,3 %, top 10 volume 24 h.
- Frais : palier dynamique sur volume simulé 30 j glissants. Entrées et sorties non urgentes : maker post-only, remplissage prudent
  (rempli seulement si des transactions publiques POSTÉRIEURES croisent strictement la limite pour un volume >= quantité) ; sinon relance.
  Stop A et risk-off dur : taker (ask/bid + glissement).
- Régime BTC 3 états : risk-on si close > EMA50 + k·ATR14 ; risk-off dur si close < EMA50 − k·ATR14 ; neutre entre les deux.
- Maintien tant que rang momentum <= KEEP_RANK ; rotation au plus une fois par jour, détention >= MIN_HOLD_H, challenger > +10 %.
- Momentum = ½ rendement 30 j + ½ rendement 7 j (bougies clôturées) — identique V1.04, retenu par l'ablation."""
import json, os, sys, time
from datetime import datetime, timezone, timedelta
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import cycle as V  # fonctions V1.04 (get, db, meta, depth_ok, STABLE) ; ne lance rien
from backtest import ind
VERSION = (open(os.path.join(D, "VERSION_ENGINE")).read().strip() if os.path.exists(os.path.join(D, "VERSION_ENGINE")) else "V1.1")  # source unique de la version moteur
K_HYST, KEEP_RANK, MIN_HOLD_H, CHAL = 0.15, 4, 48, 0.10
TOP_N, W, ATR_MULT, KILL_DD, MAX_SPREAD, MIN_ORDER, SLIP = 3, 0.33, 3.0, 0.30, 0.003, 25.0, 0.0005
BLOCK_MIN = int(os.environ.get("SIM_BLOCK_MIN", 60))
B_TAKER_AFTER = 3  # sortie B (clôture < EMA50) non remplie après 3 cycles -> taker
TIERS = [(50000, .0015, .0030), (25000, .0020, .0035), (10000, .0022, .0038), (2500, .0030, .0060), (0, .0040, .0080)]
CORE = [("XBT", 500.0), ("ETH", 300.0), ("XRP", 200.0)]  # socle de DÉPART : positions normales gérées par la stratégie (vendables)
CORE_MIN_HOLD_H = 48  # détention min. depuis l'achat initial avant une sortie de tendance B
# Stratégie : source unique strategy/params.json (mêmes valeurs par défaut ci-dessus) ; SIM_BLOCK_MIN (env) reste prioritaire
_SP = os.path.join(D, "strategy", "params.json")
_S = json.load(open(_SP)) if os.path.exists(_SP) else {}
STRATEGY_VERSION = _S.get("STRATEGY_VERSION", "V1.1")
for _k in ("K_HYST", "KEEP_RANK", "MIN_HOLD_H", "CHAL", "TOP_N", "W", "ATR_MULT", "KILL_DD", "MAX_SPREAD", "MIN_ORDER", "SLIP", "B_TAKER_AFTER", "CORE_MIN_HOLD_H"):
    if _k in _S: globals()[_k] = _S[_k]
if "BLOCK_MIN" in _S and "SIM_BLOCK_MIN" not in os.environ: BLOCK_MIN = int(_S["BLOCK_MIN"])
EEA_FALLBACK = {"XMR"}  # repli si country_code=FR indisponible

def fee_rate(c, now, maker):
    since = (now - timedelta(days=30)).isoformat(timespec="seconds")
    vol = c.execute("SELECT COALESCE(SUM(notional),0) FROM orders WHERE ts>?", (since,)).fetchone()[0]
    for th, mk, tk in TIERS:
        if vol >= th: return (mk if maker else tk), vol

def universe():
    try:
        pairs = V.get("AssetPairs", country_code="FR"); src = "country_code=FR"
    except Exception:
        pairs = V.get("AssetPairs"); src = "repli (exclusion XMR)"
    usd = {k: v for k, v in pairs.items() if v.get("quote") in ("ZUSD", "USD") and v.get("status", "online") == "online" and not k.endswith(".d")}
    tick = V.get("Ticker"); rows = []
    for k, v in usd.items():
        t = tick.get(k)
        if not t: continue
        base = v["wsname"].split("/")[0]
        if base in V.STABLE or base.startswith("USD") or (src != "country_code=FR" and base in EEA_FALLBACK): continue
        bid, ask, last = float(t["b"][0]), float(t["a"][0]), float(t["c"][0])
        if bid <= 0: continue
        rows.append(dict(pair=k, asset=base, bid=bid, ask=ask, last=last, spread=(ask-bid)/((ask+bid)/2), vol=float(t["v"][1])*float(t["p"][1])))
    ok = sorted([r for r in rows if r["spread"] <= MAX_SPREAD], key=lambda r: -r["vol"])
    return ok[:10], {r["asset"]: r for r in rows}, src

def daily(pair, today0):
    r = V.get("OHLC", pair=pair, interval=1440); k = [x for x in r if x != "last"][0]
    rows = [a for a in r[k] if int(a[0]) < today0]  # uniquement les bougies dont la journée est terminée
    if not rows or int(rows[-1][0]) != today0 - 86400: raise RuntimeError(f"bougie du {datetime.fromtimestamp(today0-86400, timezone.utc):%d/%m} absente/non clôturée")
    return {int(a[0]): (float(a[2]), float(a[3]), float(a[4]), float(a[6])) for a in rows}

def crossed(pair, side, lim, since_iso, qty):
    """Remplissage prudent : volume des transactions publiques postérieures à la pose dont le prix croise STRICTEMENT la limite."""
    since = int(datetime.fromisoformat(since_iso).timestamp() * 1e9)
    r = V.get("Trades", pair=pair, since=since); k = [x for x in r if x != "last"][0]
    v = sum(float(t[1]) for t in r[k] if (float(t[0]) < lim if side == "buy" else float(t[0]) > lim))
    return v >= qty

def main():
    now = datetime.now(timezone.utc); slot = now.strftime("%Y%m%d%H"); ts = now.isoformat(timespec="seconds")
    today0 = int(datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp()); day = now.strftime("%Y-%m-%d")
    c = V.db()
    c.executescript("""CREATE TABLE IF NOT EXISTS core(asset TEXT PRIMARY KEY, pair TEXT, qty REAL, avg REAL, cost REAL, fee REAL, price REAL, fee_rate REAL, ts TEXT);
    CREATE TABLE IF NOT EXISTS pending(asset TEXT PRIMARY KEY, pair TEXT, side TEXT, qty REAL, lim REAL, placed_ts TEXT, reason TEXT, kind TEXT, tries INTEGER DEFAULT 0, day TEXT);""")
    oc = {r[1] for r in c.execute("PRAGMA table_info(orders)")}
    for col, typ in (("liquidity", "TEXT"), ("fee_rate", "REAL"), ("version", "TEXT"), ("core", "INTEGER DEFAULT 0"), ("strategy_version", "TEXT")):
        if col not in oc: c.execute(f"ALTER TABLE orders ADD COLUMN {col} {typ}")
    ec = {r[1] for r in c.execute("PRAGMA table_info(equity)")}
    for col in ("core_value", "strat_equity"):
        if col not in ec: c.execute(f"ALTER TABLE equity ADD COLUMN {col} REAL")
    if "mode" not in {r[1] for r in c.execute("PRAGMA table_info(cycles)")}: c.execute("ALTER TABLE cycles ADD COLUMN mode TEXT")
    for _t in ("decisions", "cycles"):
        if "strategy_version" not in {r[1] for r in c.execute(f"PRAGMA table_info({_t})")}: c.execute(f"ALTER TABLE {_t} ADD COLUMN strategy_version TEXT")
    if c.execute("SELECT 1 FROM cycles WHERE slot=?", (slot,)).fetchone(): print(f"slot {slot} déjà traité"); return
    M = lambda k, v=None: V.meta(c, k, v)
    if M("C0") is None:
        M("C0", V.C0); M("C0_source", V.C0_SOURCE); M("C0_core", sum(b for _, b in CORE)); M("C0_strat", V.C0); M("cash", V.C0 - sum(b for _, b in CORE)); M("start_ts", ts); M("killed", 0)
    C0 = float(M("C0")); M("version", VERSION); C0S = C0  # un seul portefeuille : coupe-circuit sur le total
    dec = lambda a, act, why: c.execute("INSERT INTO decisions(slot,ts,asset,action,reason,strategy_version) VALUES(?,?,?,?,?,?)", (slot, ts, a, act, why, STRATEGY_VERSION))
    snap = json.loads(M("daily_snapshot") or "{}")
    mins_to_close = (today0 + 86400 - now.timestamp()) / 60
    mode = "daily" if snap.get("day") != day and now.hour < 23 else "intraday"
    if os.environ.get("SIM_FORCE_MODE"): mode = os.environ["SIM_FORCE_MODE"]
    top, allq, usrc = universe()
    btc = allq.get("XBT") or allq.get("BTC")
    if M("btc_qty") is None: M("btc_qty", C0 * (1 - .008) / (btc["ask"] * (1 + SLIP)))
    # ---------- socle permanent : achat unique au démarrage (limite maker au bid, frais maker du palier) ----------
    if M("C0_core") and M("core_done") is None:
        for a, budget in CORE:
            q = allq[a]; rate, _ = fee_rate(c, now, True); lim = q["bid"]; qty = budget / (1 + rate) / lim; notional = qty * lim; fee = notional * rate
            c.execute("INSERT OR REPLACE INTO core VALUES(?,?,?,?,?,?,?,?,?)", (a, q["pair"], qty, (notional + fee) / qty, notional + fee, fee, lim, rate, ts))
            c.execute("INSERT INTO orders(slot,ts,pair,asset,side,qty,price,notional,fee,reason,pnl,test,liquidity,fee_rate,version,core,strategy_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (slot, ts, q["pair"], a, "buy", qty, lim, notional, fee, f"SOCLE : achat de départ {budget:.0f} $ (limite post-only au bid, position gérée ensuite par la stratégie)", None, 0, "maker", rate, VERSION, 1, STRATEGY_VERSION))
            dec(a, "socle", f"achat socle {qty:.6g} {a} @ {lim:.6g} (maker {rate*100:.2f} %, frais {fee:.2f} $)"); print(f"SOCLE BUY {qty:.6g} {a} @ {lim:.6g} maker fee {fee:.2f}")
        M("core_done", ts)
    core = {r[0]: dict(pair=r[1], qty=r[2], avg=r[3], cost=r[4]) for r in c.execute("SELECT asset,pair,qty,avg,cost FROM core")}
    for a, p in core.items():
        if a not in allq:
            t = list(V.get("Ticker", pair=p["pair"]).values())[0]; allq[a] = dict(pair=p["pair"], asset=a, bid=float(t["b"][0]), ask=float(t["a"][0]), last=float(t["c"][0]))
    core_value = lambda: sum(p["qty"] * allq[a]["bid"] for a, p in core.items())  # référence : socle conservé sans toucher
    cash = float(M("cash")); killed = M("killed") == "1"
    pos = {r[0]: dict(pair=r[1], qty=r[2], avg=r[3], entry=r[4], high=r[5], stop=r[6]) for r in c.execute("SELECT * FROM positions")}
    if M("core_done") and M("core_migrated") is None:  # le socle devient des positions normales (une seule fois)
        for a, p in core.items():
            if a not in pos: pos[a] = dict(pair=p["pair"], qty=p["qty"], avg=p["avg"], entry=c.execute("SELECT ts FROM core WHERE asset=?", (a,)).fetchone()[0], high=allq[a]["last"], stop=None)
        M("C0_strat", C0); M("core_migrated", ts)
    core_entry = {r[0]: r[1] for r in c.execute("SELECT asset,ts FROM core")}
    pend = {r[0]: dict(pair=r[1], side=r[2], qty=r[3], lim=r[4], placed=r[5], reason=r[6], kind=r[7], tries=r[8], day=r[9]) for r in c.execute("SELECT * FROM pending")}
    for a, p in list(pos.items()) + list(pend.items()):
        if a not in allq:
            t = list(V.get("Ticker", pair=p["pair"]).values())[0]
            allq[a] = dict(pair=p["pair"], asset=a, bid=float(t["b"][0]), ask=float(t["a"][0]), last=float(t["c"][0]))
    tests = set(json.loads(M("test_assets") or "[]"))
    def equity(): return cash + sum(p["qty"] * allq[a]["bid"] for a, p in pos.items())
    def fill(a, side, qty, px, liq, why, test=0):
        nonlocal cash
        q = allq[a]; rate, _ = fee_rate(c, now, liq == "maker")
        notional = qty * px; fee = notional * rate; pnl = None
        if side == "buy":
            cash -= notional + fee; p = pos.get(a)
            if p: p["avg"] = (p["avg"]*p["qty"] + notional + fee) / (p["qty"] + qty); p["qty"] += qty
            else: pos[a] = dict(pair=q["pair"], qty=qty, avg=(notional+fee)/qty, entry=ts, high=q["last"], stop=None)
        else:
            cash += notional - fee; p = pos[a]; pnl = (px*(1-rate) - p["avg"]) * qty; p["qty"] -= qty
            test = test or int(a in tests)
            if p["qty"] * q["bid"] < 1: del pos[a]; tests.discard(a)
        c.execute("INSERT INTO orders(slot,ts,pair,asset,side,qty,price,notional,fee,reason,pnl,test,liquidity,fee_rate,version,strategy_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (slot, ts, q["pair"], a, side, qty, px, notional, fee, why, pnl, test, liq, rate, VERSION, STRATEGY_VERSION))
        dec(a, side, f"{why} [{liq} {rate*100:.2f} %]"); print(f"{side.upper()} {qty:.6g} {a} @ {px:.6g} {liq} fee {fee:.2f} — {why}")
    def taker(a, side, qty, why):
        q = allq[a]
        if not V.depth_ok(q["pair"], side, qty): dec(a, "skip", f"profondeur insuffisante pour {side} {qty:.6g}"); return False
        fill(a, side, qty, q["ask"]*(1+SLIP) if side == "buy" else q["bid"]*(1-SLIP), "taker", why); return True
    def post(a, side, qty, why, kind):
        q = allq[a]; lim = q["bid"] if side == "buy" else q["ask"]  # post-only : côté passif du carnet
        pend[a] = dict(pair=q["pair"], side=side, qty=qty, lim=lim, placed=ts, reason=why, kind=kind, tries=pend.get(a, {}).get("tries", 0), day=snap.get("day", day))
        dec(a, "ordre", f"post-only {'achat' if side=='buy' else 'vente'} {qty:.6g} @ {lim:.6g} ({kind}) : {why}")
    note = f"{mode} ; univers {usrc}"
    if killed: note += " ; coupe-circuit actif"
    else:
        eq = equity(); dd = 1 - eq / C0  # coupe-circuit sur le portefeuille total
        if dd >= KILL_DD:
            pend.clear()
            for a in list(pos): taker(a, "sell", pos[a]["qty"], f"COUPE-CIRCUIT : drawdown {dd:.1%} >= 30 % depuis C0")
            M("killed", 1); note += " ; coupe-circuit déclenché"
        else:
            # ---------- A) exécution prudente des ordres post-only en attente ----------
            for a, o in list(pend.items()):
                if o["side"] == "sell" and a not in pos: del pend[a]; continue
                blocked = o["side"] == "buy" and mins_to_close <= BLOCK_MIN
                try: hit = crossed(o["pair"], o["side"], o["lim"], o["placed"], o["qty"])
                except Exception as e: hit = False; dec(a, "skip", f"Trades indisponible : {e}")
                if hit and not blocked:
                    if o["side"] == "buy":
                        spend = o["qty"] * o["lim"]; rate, _ = fee_rate(c, now, True)
                        if spend * (1 + rate) > cash: o["qty"] = cash / (1 + rate) / o["lim"] * 0.999
                        if o["qty"] * o["lim"] >= MIN_ORDER: fill(a, "buy", o["qty"], o["lim"], "maker", o["reason"])
                    else: fill(a, "sell", min(o["qty"], pos[a]["qty"]), o["lim"], "maker", o["reason"])
                    del pend[a]; continue
                if blocked:
                    dec(a, "annulé", f"post-only achat annulé : fenêtre sans achat de {BLOCK_MIN} min avant 00:00 UTC"); del pend[a]; continue
                o["tries"] += 1
                if o["kind"] == "B" and o["tries"] >= B_TAKER_AFTER:
                    del pend[a]; taker(a, "sell", pos[a]["qty"], o["reason"] + f" (post-only non rempli après {o['tries']} cycles -> taker)"); continue
                post(a, o["side"], o["qty"], o["reason"], o["kind"]); pend[a]["tries"] = o["tries"]  # relance au nouveau prix passif
            # ---------- B) décision quotidienne ----------
            if mode == "daily":
                try:
                    bt = ind(daily(btc["pair"], today0)); bx = bt[max(bt)]
                except Exception as e:
                    dec("BTC", "skip", f"décision quotidienne reportée : {e}"); bx = None
                if bx:
                    up, lo = bx["e50"] + K_HYST*bx["atr"], bx["e50"] - K_HYST*bx["atr"]
                    state = "on" if bx["c"] > up else ("off" if bx["c"] < lo else "neutral")
                    lab = {"on": "RISK-ON (achats autorisés)", "neutral": "NEUTRE (pas de nouvel achat, positions gérées sur leur propre tendance/stop)", "off": "RISK-OFF DUR (sortie)"}[state]
                    dec("BTC", "régime", f"régime BTC {lab} : clôture {bx['c']:.0f} vs bande EMA50 {bx['e50']:.0f} ± {K_HYST}×ATR14 [{lo:.0f} ; {up:.0f}]")
                    sig = {}; cand = {r["asset"]: r for r in top}
                    for a in pos: cand.setdefault(a, allq[a])
                    for a, q in cand.items():
                        try: d = ind(daily(q["pair"], today0))
                        except Exception as e: dec(a, "skip", f"OHLC : {e}"); continue
                        x = d[max(d)]
                        if not x["ok"] or x["mom"] is None: dec(a, "skip", "historique insuffisant"); continue
                        conf = []
                        tr = x["c"] > x["e50"] and x["e20"] > x["e50"]
                        if tr: conf.append("EMA20>EMA50")
                        if x["macd"]: conf.append("MACD>signal")
                        if 50 < x["rsi"] < 75: conf.append(f"RSI {x['rsi']:.0f}")
                        if x["adx"] > 20 and x["pdi"] > x["mdi"]: conf.append(f"ADX {x['adx']:.0f}")
                        if x["volup"]: conf.append("volume 7j>30j")
                        c.execute("INSERT OR REPLACE INTO indicators(slot,ts,asset,close,ema20,ema50,macd_ok,rsi,adx,pdi,mdi,vol_ok,mom,score,regime,trend_ok,rsi_ok,adx_ok,vol_ratio,macd_hist) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                  (slot, ts, a, x["c"], x["e20"], x["e50"], int(bool(x["macd"])), x["rsi"], x["adx"], x["pdi"], x["mdi"], int(bool(x["volup"])), x["mom"], len(conf), int(state == "on"), int(tr), int(50 < x["rsi"] < 75), int(x["adx"] > 20 and x["pdi"] > x["mdi"]), x["vr"], x["mh"]))
                        sig[a] = dict(mom=x["mom"], entry=tr and len(conf) >= 4, above=x["c"] > x["e50"], atr=x["atr"], close=x["c"], e50=x["e50"], conf=conf, in_top=a in [r["asset"] for r in top])
                    ranked = sorted([a for a, s in sig.items() if s["in_top"]], key=lambda a: -sig[a]["mom"]); rank = {a: i+1 for i, a in enumerate(ranked)}
                    cands = [a for a in ranked if sig[a]["entry"]]
                    for a in [p for p in pend if pend[p]["side"] == "buy"]: del pend[a]  # ordres d'achat de la veille annulés, ré-évalués
                    exits = []
                    for a in list(pos):
                        p = pos[a]; s = sig.get(a); held_h = (now - datetime.fromisoformat(p["entry"])).total_seconds() / 3600
                        if s: p["stop"] = max(p["stop"] or 0, max(p["high"], s["close"]) - ATR_MULT * s["atr"])
                        if state == "off":
                            pend.pop(a, None); taker(a, "sell", p["qty"], f"sortie : régime BTC risk-off dur (clôture BTC < EMA50 − {K_HYST}×ATR)"); exits.append(a); continue
                        if s and not s["above"]:
                            if a in tests and held_h < 24: dec(a, "hold", f"position test : sortie tendance différée, détention min. 24 h ({held_h:.0f} h)"); continue
                            if a in core_entry and p["entry"] == core_entry[a] and held_h < CORE_MIN_HOLD_H: dec(a, "hold", f"socle de départ sous l'EMA50 : sortie tendance différée, détention min. {CORE_MIN_HOLD_H} h depuis l'achat initial ({held_h:.0f} h)"); continue
                            post(a, "sell", p["qty"], f"sortie B : clôture {s['close']:.6g} < EMA50 {s['e50']:.6g}", "B"); exits.append(a); continue
                        ra = rank.get(a, 99)
                        if ra > KEEP_RANK and held_h >= MIN_HOLD_H:
                            ch = [b for b in cands if b not in pos and sig[b]["mom"] > (s["mom"] if s else -9) + CHAL*abs(s["mom"] if s else 0)]
                            if ch:
                                post(a, "sell", p["qty"], f"rotation C : rang {ra} > {KEEP_RANK}, détenu {held_h:.0f} h, challenger {ch[0]} nettement meilleur (momentum {sig[ch[0]]['mom']:+.2%} vs {s['mom']:+.2%})", "C"); exits.append(a); continue
                            dec(a, "hold", f"rang {ra} > {KEEP_RANK} mais aucun challenger > +{CHAL:.0%} : conserver")
                        elif ra > KEEP_RANK: dec(a, "hold", f"rang {ra} > {KEEP_RANK} mais détention {held_h:.0f} h < {MIN_HOLD_H} h : conserver")
                        else: dec(a, "hold", f"rang {ra} ≤ {KEEP_RANK}, au-dessus de l'EMA50 : conserver")
                    entries = []
                    if state == "on" and mins_to_close > BLOCK_MIN:
                        eq = equity(); full = lambda a: pos[a]["qty"] * allq[a]["bid"] >= 0.5 * W * eq  # une position < ½ cible (socle) n'occupe pas un emplacement
                        free = TOP_N - len([a for a in pos if a not in exits and full(a)])
                        for a in cands[:TOP_N]:
                            if free <= 0: break
                            have = pos[a]["qty"] * allq[a]["bid"] if a in pos else 0
                            if a in pos and full(a): continue
                            amt = min(W * eq - have, cash / 1.004 * 0.999)
                            if amt < MIN_ORDER: dec(a, "skip", "liquidités insuffisantes"); break
                            post(a, "buy", amt / allq[a]["bid"], (f"renfort jusqu'à la cible (position de départ {have:.0f} $) ; " if have else "") + f"entrée : {', '.join(sig[a]['conf'])} ; rang momentum {rank[a]} ({sig[a]['mom']:+.2%}) ; régime BTC risk-on ; cible {W:.0%}", "E"); entries.append(a); free -= 1
                    elif state != "on": dec("ALL", "cash", f"régime BTC {dict(neutral='neutre', off='risk-off dur').get(state, state)} : aucun nouvel achat")
                    for a, s in sig.items(): dec(a, "signal", f"{len(s['conf'])}/5 : {', '.join(s['conf']) or 'aucun'} ; momentum {s['mom']:+.2%} ; rang {rank.get(a, '—')}")
                    snap = dict(day=day, ts=ts, candle=datetime.fromtimestamp(today0-86400, timezone.utc).strftime("%Y-%m-%d"), state=state, btc_close=bx["c"], btc_e50=bx["e50"], band=[lo, up],
                                universe=[r["asset"] for r in top], universe_src=usrc, rank=rank, cands=cands, entries=entries, exits=exits,
                                params=dict(k=K_HYST, keep_rank=KEEP_RANK, min_hold_h=MIN_HOLD_H, chal=CHAL, block_min=BLOCK_MIN))
                    M("daily_snapshot", json.dumps(snap)); M("last_signals", json.dumps(sig)); M("universe", json.dumps(snap["universe"]))
            # ---------- C) stops ATR intraday (taker), sur stop figé à la décision quotidienne ----------
            for a in list(pos):
                p = pos[a]; last = allq[a]["last"]; p["high"] = max(p["high"] or last, last)
                if p["stop"] is None and a in json.loads(M("last_signals") or "{}"): p["stop"] = p["high"] - ATR_MULT * json.loads(M("last_signals"))[a]["atr"]
                if p["stop"] and allq[a]["bid"] <= p["stop"]:
                    pend.pop(a, None); taker(a, "sell", p["qty"], f"stop suiveur A : bid {allq[a]['bid']:.6g} <= stop {p['stop']:.6g}")
    # ---------- persistance ----------
    c.execute("DELETE FROM positions")
    for a, p in pos.items(): c.execute("INSERT INTO positions VALUES(?,?,?,?,?,?,?)", (a, p["pair"], p["qty"], p["avg"], p["entry"], p["high"], p["stop"]))
    c.execute("DELETE FROM pending")
    for a, o in pend.items(): c.execute("INSERT INTO pending VALUES(?,?,?,?,?,?,?,?,?,?)", (a, o["pair"], o["side"], o["qty"], o["lim"], o["placed"], o["reason"], o["kind"], o["tries"], o["day"]))
    M("cash", cash); M("test_assets", json.dumps(sorted(a for a in tests if a in pos)))
    rate_m, vol30 = fee_rate(c, now, True); M("fee_vol30", vol30); M("fee_maker", rate_m); M("fee_taker", fee_rate(c, now, False)[0])
    for a, q in allq.items():
        if a in pos or a in pend or a in [r["asset"] for r in top] or a in (btc["asset"], "ETH") or a in core:
            c.execute("INSERT OR REPLACE INTO prices VALUES(?,?,?,?,?)", (slot, a, q["bid"], q["ask"], q["last"]))
    eq = equity(); cv = core_value(); seq = eq; exp = 1 - cash / eq if eq else 0; btch = float(M("btc_qty")) * btc["bid"]  # core_value = référence « socle conservé » (hors liquidités)
    c.execute("INSERT INTO equity(slot,ts,equity,cash,btc_hold,exposure,core_value,strat_equity) VALUES(?,?,?,?,?,?,?,?)", (slot, ts, eq, cash, btch, exp, cv, seq))
    c.execute("INSERT INTO cycles(slot,ts,status,note,mode,strategy_version) VALUES(?,?,?,?,?,?)", (slot, ts, "ok", note, mode, STRATEGY_VERSION))
    c.commit()
    print(f"{VERSION} slot {slot} [{mode}] : total {eq:.2f} $ (réf. socle conservé {cv + float(M("C0")) - float(M("C0_core") or 0):.2f}), liquidités {cash:.2f}, exposition {exp:.0%}, ordres en attente {len(pend)}, BTC hold {btch:.2f}")

if __name__ == "__main__": main()
