#!/usr/bin/env python3
"""Emit JSON of all dashboard data from sim.db."""
import json, sqlite3, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
D = os.path.dirname(os.path.abspath(__file__)); c = sqlite3.connect(os.environ.get("SIM_DB", os.path.join(D, "sim.db")))
P = ZoneInfo("Europe/Paris")
m = dict(c.execute("SELECT k,v FROM meta")); C0 = float(m["C0"])
paris = lambda ts: datetime.fromisoformat(ts).astimezone(P).strftime("%d/%m %Hh%M")
eqs = c.execute("SELECT slot,ts,equity,cash,btc_hold,exposure FROM equity ORDER BY slot").fetchall()
last = eqs[-1]; slot = last[0]
peak, mdd = C0, 0
for e in eqs: peak = max(peak, e[2]); mdd = max(mdd, 1 - e[2] / peak)
sells = c.execute("SELECT pnl FROM orders WHERE side='sell' AND pnl IS NOT NULL").fetchall()
wins = sum(1 for (p,) in sells if p > 0)
px = {r[0]: r for r in c.execute("SELECT asset,bid,ask,last FROM prices WHERE slot=?", (slot,))}
positions = []
_tests = {r[0] for r in c.execute("SELECT asset FROM orders WHERE side='buy' AND COALESCE(test,0)=1")}
for a, pair, qty, avg, entry, high, stop in c.execute("SELECT * FROM positions"):
    b = px[a][1]; positions.append(dict(asset=a, pair=pair, qty=qty, avg=avg, price=b, value=qty*b, pnl_pct=(b/avg-1)*100, stop=stop, high=high, entry_iso=entry, test=a in _tests))
out = dict(
  C0=C0, C0_source=m["C0_source"], start=paris(m["start_ts"]), as_of=paris(last[1]), slot=slot, killed=m.get("killed")=="1",
  equity=last[2], cash=last[3], exposure_pct=last[5]*100, net_return_pct=(last[2]/C0-1)*100,
  btc_hold=last[4], btc_return_pct=(last[4]/C0-1)*100, vs_btc_pct=(last[2]/C0-last[4]/C0)*100, vs_cash_pct=(last[2]/C0-1)*100,
  max_dd_pct=mdd*100, cur_dd_pct=(1-last[2]/peak)*100,
  fees=c.execute("SELECT COALESCE(SUM(fee),0) FROM orders").fetchone()[0],
  n_trades=c.execute("SELECT COUNT(*) FROM orders").fetchone()[0], n_closed=len(sells),
  win_rate_pct=(wins/len(sells)*100) if sells else None, n_cycles=len(eqs),
  universe=json.loads(m.get("universe","[]")),
  curve=[dict(t=paris(e[1]), sim=e[2], btc=e[4], cash=C0) for e in eqs],
  positions=positions,
  orders=[dict(t=paris(r[0]), pair=r[1], side={"buy":"achat","sell":"vente"}.get(r[2],r[2]) + (" (test)" if r[7] else ""), qty=r[3], price=r[4], fee=r[5], reason=r[6]) for r in c.execute("SELECT ts,pair,side,qty,price,fee,reason,COALESCE(test,0) FROM orders ORDER BY id DESC LIMIT 25")],
  allocation=[],
  decisions=[dict(t=paris(r[0]), asset=("TOUS" if r[1]=="ALL" else r[1]), action={"signal":"signal","cash":"liquidités","hold":"conserver","buy":"achat","sell":"vente","skip":"ignoré"}.get(r[2],r[2]), reason=r[3]) for r in c.execute("SELECT ts,asset,action,reason FROM decisions ORDER BY id DESC LIMIT 30")],
)
wf = {}
for tag, fn in (("040", "backtest2_results.json"), ("080", "backtest2_fee080.json")):
    w = json.load(open(os.path.join(D, fn)))
    keep = ("B", "Bfixe", "BTC", "EW")
    wf[tag] = dict(folds=[dict(test=r["test"], res={k: dict(ret=r["res"][k]["ret"], mdd=r["res"][k]["mdd"]) for k in keep}) for r in w["folds"]],
                   agg={k: dict(ret=w["agg"][k]["ret"], mdd=w["agg"][k]["mdd"], pos=w["agg"][k].get("pos_folds")) for k in keep}, period=w["period"], n=w["n_folds"])
out["walkforward"] = wf
# ---------- socle de départ (positions normales de la stratégie) + référence « socle conservé » ----------
_cr = []
try: _cr = c.execute("SELECT asset,pair,qty,avg,cost,fee,price,fee_rate,ts FROM core").fetchall()
except sqlite3.OperationalError: pass
_core_pos = []
for a, pair, qty, avg, cost, fee, p0, fr_, cts in _cr:
    b = px[a][1] if a in px else p0
    held = sum(p["qty"] for p in positions if p.get("asset") == a)
    _core_pos.append(dict(asset=a, pair=pair, qty=qty, avg=avg, buy_price=p0, fee=fee, fee_rate=fr_, cost=cost, price=b, value=qty*b, pnl=qty*b-cost, pnl_pct=(qty*b/cost-1)*100, t=paris(cts), held_qty=held, held_pct=min(held / qty * 100, 999) if qty else 0))
_cv = sum(p["value"] for p in _core_pos); _cc = sum(p["cost"] for p in _core_pos)
C0S = float(m.get("C0_strat", C0)); C0C = float(m.get("C0_core", 0))
_se = last[3] + sum(p["value"] for p in positions)
_bench = _cv + (C0 - C0C)  # socle conservé sans toucher + liquidités initiales
out["core"] = dict(C0=C0C, cost=_cc, fees=sum(p["fee"] for p in _core_pos), value=_cv, pnl=_cv - C0C, pnl_pct=(_cv / C0C - 1) * 100 if C0C else None, positions=_core_pos,
                   bench=_bench, bench_pct=(_bench / C0 - 1) * 100, vs_bench=last[2] - _bench, start=_core_pos[0]["t"] if _core_pos else None)
_origin = {p["asset"]: p["t"] for p in _core_pos}
for p in positions:
    if p.get("asset") in _origin: p["origin"] = "achat initial (socle de départ, " + _origin[p["asset"]] + ")"
out["total"] = dict(C0=C0, equity=last[2], pnl=last[2] - C0, pnl_pct=(last[2] / C0 - 1) * 100)
out["allocation"] = [dict(label=p["asset"], value=p["value"]) for p in positions] + [dict(label="Liquidités", value=last[3])]
_ce = {r[0]: r for r in c.execute("SELECT slot,core_value,strat_equity FROM equity")} if "core_value" in {r[1] for r in c.execute("PRAGMA table_info(equity)")} else {}
for pt, e in zip(out["curve"], eqs):
    x = _ce.get(e[0]); pt["core"] = (x[1] + C0 - C0C) if x and x[1] is not None and C0C else None; pt["strat"] = None  # core = référence socle conservé
bt = json.load(open(os.path.join(D, "backtest_results.json")))
out["backtest"] = dict(periods=bt["periods"], rows={k: [dict(v=v, **r) for v, r in res.items()] for k, res in bt["results"].items()})

# ---------- V1.01 ----------
FEE, SLIP = 0.004, 0.0005
out["version"] = m.get("version", "V1.04")
st = datetime.fromisoformat(c.execute("SELECT MIN(ts) FROM cycles").fetchone()[0])
out["start_iso"] = st.isoformat(); out["start_paris"] = st.astimezone(P).strftime("%d/%m/%Y %Hh%M")
el = datetime.now(timezone.utc) - st; h = int(el.total_seconds() // 3600)
out["uptime"] = f"{h // 24} j {h % 24} h {int(el.total_seconds() % 3600 // 60)} min" if h >= 24 else f"{h} h {int(el.total_seconds() % 3600 // 60)} min"
out["rendered"] = datetime.now(P).strftime("%d/%m %Hh%M")
slots = [e[0] for e in eqs]
pr = {}
for sl, a, b, ak, l in c.execute("SELECT slot,asset,bid,ask,last FROM prices"): pr.setdefault(sl, {})[a] = (b, ak, l)
out["btc_series"] = [dict(t=paris(e[1]), p=pr.get(e[0], {}).get("XBT", (None,)*3)[2]) for e in eqs if "XBT" in pr.get(e[0], {})]
out["btc_last"] = out["btc_series"][-1]["p"] if out["btc_series"] else None
# panier 50/50 BTC/ETH acheté au 1er cycle (ask + glissement, frais 0,40 %)
f0 = pr.get(slots[0], {})
if "XBT" in f0 and "ETH" in f0:
    qb = C0 / 2 * (1 - FEE) / (f0["XBT"][1] * (1 + SLIP)); qe = C0 / 2 * (1 - FEE) / (f0["ETH"][1] * (1 + SLIP)); last_basket = None
    for pt, e in zip(out["curve"], eqs):
        p = pr.get(e[0], {})
        if "XBT" in p and "ETH" in p: last_basket = qb * p["XBT"][0] + qe * p["ETH"][0]
        pt["basket"] = last_basket
    out["basket"] = last_basket; out["basket_return_pct"] = (last_basket / C0 - 1) * 100 if last_basket else None
# drawdown depuis le pic
pk = C0; out["dd_series"] = []
for e in eqs: pk = max(pk, e[2]); out["dd_series"].append(dict(t=paris(e[1]), dd=(1 - e[2] / pk) * 100))
# brut vs frais
out["pnl_net"] = last[2] - C0; out["pnl_gross"] = out["pnl_net"] + out["fees"]
# temps investi
ex = [e[5] for e in eqs]; out["invested_pct"] = sum(ex) / len(ex) * 100; out["cycles_invested"] = sum(1 for x in ex if x > 0.01)
# P&L par crypto (réalisé + latent)
pc = {}
for a, pnl, fee in c.execute("SELECT asset,COALESCE(pnl,0),fee FROM orders"): pc.setdefault(a, dict(real=0, fees=0, unreal=0)); pc[a]["real"] += pnl; pc[a]["fees"] += fee
for p in positions: pc.setdefault(p["asset"], dict(real=0, fees=0, unreal=0)); pc[p["asset"]]["unreal"] = p["qty"] * (p["price"] - p["avg"])
out["pnl_by_asset"] = sorted([dict(asset=a, total=v["real"] + v["unreal"], **v) for a, v in pc.items()], key=lambda r: -r["total"])
sp = [dict(asset=r[0], pnl=r[1], t=paris(r[2])) for r in c.execute("SELECT asset,pnl,ts FROM orders WHERE side='sell' AND pnl IS NOT NULL")]
W = [x["pnl"] for x in sp if x["pnl"] > 0]; L = [x["pnl"] for x in sp if x["pnl"] <= 0]
out["trade_stats"] = dict(best=max(sp, key=lambda x: x["pnl"]) if sp else None, worst=min(sp, key=lambda x: x["pnl"]) if sp else None,
                          avg_win=sum(W) / len(W) if W else None, avg_loss=sum(L) / len(L) if L else None, n_win=len(W), n_loss=len(L))
# journal en langage clair
fr = lambda x: f"{x:,.2f}".replace(",", " ").replace(".", ",")
def phrase(r):
    t, a, side, qty, px, notional, fee, why, pnl, test = r
    if str(why).startswith("SOCLE"): return f"[SOCLE] Le {paris(t)}, achat de départ de {qty:.6g} {a} à {fr(px)} $ (soit {fr(notional)} $, frais maker {fr(fee)} $) : position ensuite gérée par la stratégie comme les autres (stop, régime, rotation)."
    if test: return f"[TEST] Le {paris(t)}, la sim a {'acheté' if side == 'buy' else 'vendu'} {qty:.6g} {a} à {fr(px)} $ (soit {fr(notional)} $, frais {fr(fee)} $)" + (f" ; résultat {'+' if pnl>=0 else '−'}{fr(abs(pnl))} $" if pnl is not None else "") + f", ordre test hors stratégie, motif : {why.replace('TEST : ','')}."
    if side == "buy":
        s = f"Le {paris(t)}, la sim a acheté {qty:.6g} {a} à {fr(px)} $ (soit {fr(notional)} $, frais {fr(fee)} $) parce que {why.split(':',1)[-1].strip()}."
    else:
        res = f" ; résultat {'+' if pnl>=0 else '−'}{fr(abs(pnl))} $" if pnl is not None else ""
        s = f"Le {paris(t)}, la sim a vendu {qty:.6g} {a} à {fr(px)} $ (frais {fr(fee)} $){res}, motif : {why}."
    return s
out["journal"] = [phrase(r) for r in c.execute("SELECT ts,asset,side,qty,price,notional,fee,reason,pnl,COALESCE(test,0) FROM orders ORDER BY id DESC LIMIT 30")]
# indicateurs
ind_rows, ind_src = [], None
try:
    ls = c.execute("SELECT MAX(slot) FROM indicators").fetchone()[0]
    if ls:
        for r in c.execute("SELECT asset,trend_ok,macd_ok,rsi_ok,rsi,adx_ok,adx,vol_ok,mom,score,regime,ts,pdi,mdi,close,ema50,vol_ratio,macd_hist FROM indicators WHERE slot=? ORDER BY score DESC, mom DESC", (ls,)):
            ind_rows.append(dict(asset=r[0], trend=bool(r[1]), macd=bool(r[2]), rsi_ok=bool(r[3]), rsi=r[4], adx_ok=bool(r[5]), adx=r[6], vol=bool(r[7]), mom=r[8], score=r[9], regime=bool(r[10]), pdi=r[12], mdi=r[13], ema_pct=(r[14]/r[15]-1)*100 if r[15] else None, vol_ratio=r[16], macd_hist=r[17]))
        ind_src = "cycle du " + paris(r[11])
except sqlite3.OperationalError: pass
if not ind_rows and os.path.exists(os.path.join(D, "indicators_preview.json")):
    pv = json.load(open(os.path.join(D, "indicators_preview.json"))); ind_rows = sorted(pv["rows"], key=lambda r: (-r["score"], -(r["mom"] or 0)))
    ind_src = "aperçu en lecture seule du " + paris(pv["ts"]) + " (le 1er cycle précède V1.01 ; le prochain cycle horaire l'enregistrera en base)"
# V1.03 : paires pour le recalcul en direct dans le HTML (univers courant + positions ; régime via BTC)
_assets = list(dict.fromkeys(json.loads(m.get("universe", "[]")) + [p["asset"] for p in positions] + [r["asset"] for r in ind_rows]))
out["ind_live"] = [dict(asset=a, pair=a + "USD") for a in _assets]; out["ind_btc_pair"] = "XBTUSD"
# V1.04 : conditions de sortie par position (snapshot du cycle)
_ix = {}
try:
    for a, cl, e50, rg in c.execute("SELECT asset,close,ema50,regime FROM indicators WHERE slot=(SELECT MAX(slot) FROM indicators)"): _ix[a] = (cl, e50, rg)
except sqlite3.OperationalError: pass
out["last_cycle_iso"] = last[1]; out["min_hold_h"] = 24; out["atr_mult"] = 3.0
out["btc_regime"] = bool(_ix["XBT"][2]) if "XBT" in _ix else None
for p in positions:
    x = _ix.get(p["asset"]); p["close"] = x[0] if x else None; p["ema50"] = x[1] if x else None
    p["held_h"] = (datetime.fromisoformat(last[1]) - datetime.fromisoformat(p["entry_iso"])).total_seconds() / 3600
out["indicators"] = ind_rows; out["indicators_src"] = ind_src

# ---------- V1.1 : données structurées pour la nouvelle interface ----------
for pt, e in zip(out["curve"], eqs): pt["iso"] = e[1]; pt["exp"] = e[5] * 100
for pt, e in zip(out["dd_series"], eqs): pt["iso"] = e[1]
_bs = [e for e in eqs if "XBT" in pr.get(e[0], {})]
for pt, e in zip(out["btc_series"], _bs): pt["iso"] = e[1]
_oc = {r[1] for r in c.execute("PRAGMA table_info(orders)")}
_q = "SELECT id,ts,pair,asset,side,qty,price,notional,fee,reason,pnl,COALESCE(test,0)," + ("liquidity,fee_rate" if "liquidity" in _oc else "NULL,NULL") + "," + ("COALESCE(core,0)" if "core" in _oc else "0") + " FROM orders ORDER BY id DESC"
out["orders_full"] = [dict(id=r[0], iso=r[1], t=paris(r[1]), pair=r[2], asset=r[3], side=r[4], type=("Achat" if r[4] == "buy" else "Vente") + (" test" if r[11] else ""), qty=r[5], price=r[6], notional=r[7], fee=r[8], reason=r[9], pnl=r[10], test=bool(r[11]), liquidity=r[12], fee_rate=r[13], core=bool(r[14])) for r in c.execute(_q)]
for o in out["orders_full"]:
    if o["core"]: o["type"] = "Achat initial (socle de départ)"
_cm = {r[0]: (r[1], r[2] if len(r) > 2 else None) for r in c.execute("SELECT slot,ts," + ("mode" if "mode" in {x[1] for x in c.execute("PRAGMA table_info(cycles)")} else "NULL") + " FROM cycles")}
_g = {}
for sl, ts_, a, act, why in c.execute("SELECT slot,ts,asset,action,reason FROM decisions ORDER BY id DESC LIMIT 600"):
    _g.setdefault(sl, []).append(dict(asset=("TOUS" if a == "ALL" else a), action={"signal":"signal","cash":"liquidités","hold":"conserver","buy":"achat","sell":"vente","skip":"ignoré"}.get(act, act), reason=why))
out["decision_cycles"] = [dict(slot=sl, iso=_cm.get(sl, (None,))[0], t=paris(_cm[sl][0]) if sl in _cm else sl, mode=_cm.get(sl, (None, None))[1], items=v) for sl, v in sorted(_g.items(), reverse=True)[:40]]
try: out["pending"] = [dict(asset=r[0], side=r[2], qty=r[3], lim=r[4], placed=paris(r[5]), reason=r[6], kind=r[7], tries=r[8]) for r in c.execute("SELECT * FROM pending")]
except sqlite3.OperationalError: out["pending"] = []
out["snapshot"] = json.loads(m["daily_snapshot"]) if m.get("daily_snapshot") else None
if out["snapshot"]:
    out["btc_regime_state"] = out["snapshot"]["state"]; out["btc_regime"] = out["snapshot"]["state"] == "on"
    out["min_hold_h"] = out["snapshot"]["params"]["min_hold_h"]; out["keep_rank"] = out["snapshot"]["params"]["keep_rank"]
out["fees_tier"] = dict(vol30=float(m["fee_vol30"]) if m.get("fee_vol30") else None, maker=float(m["fee_maker"]) if m.get("fee_maker") else None, taker=float(m["fee_taker"]) if m.get("fee_taker") else None)
out["schedule"] = dict(daily_utc="00:10", intraday="toutes les heures à hh:10", block_min=60) if out["version"] == "V1.1" else dict(intraday="toutes les heures à hh:05")
_ab = os.path.join(D, "v1_1", "ablation_results.json")
if os.path.exists(_ab):
    A = json.load(open(_ab)); out["ablation"] = dict(periods=A["periods"], btc=A["btc"], steps=[dict(name=s["name"], opt={k: s["opt"][k] for k in ("ret","mdd","fees","fees_over_gross","rt_month","median_hold","pf")}, val={k: s["val"][k] for k in ("ret","mdd","fees","fees_over_gross","rt_month","median_hold","pf")}) for s in A["steps"]])
# leçons
lp = os.path.join(D, "lecons.md")
out["lessons"] = [b.strip() for b in open(lp).read().split("\n## ")[1:] if b.strip()] if os.path.exists(lp) else []
# affichage seulement : XBT -> BTC, XDG -> DOGE (codes de paire inchangés)
import re
def _disp(o, k=None):
    if isinstance(o, dict): return {kk: _disp(v, kk) for kk, v in o.items()}
    if isinstance(o, list): return [_disp(v, k) for v in o]
    if isinstance(o, str) and k != "pair": return re.sub(r"\bXDG\b", "DOGE", re.sub(r"\bXBT\b", "BTC", o))
    return o
out = _disp(out)
print(json.dumps(out, indent=1))
