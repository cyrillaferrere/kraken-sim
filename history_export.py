#!/usr/bin/env python3
"""Export historique par cycle pour le replay (lecture seule, schema_version 1). Voir docs/HISTORY_SCHEMA.md.
- export_cycle(c, slot, engine, strategy) : instantané complet du cycle (appelé en fin de cycle par cycle_v11.py).
- backfill(c, ...) : instantanés partiels (complete:false) des cycles passés de sim.db ; idempotent (ne remplace jamais un instantané existant).
Aucune valeur inventée : champ indisponible = null + nom dans "missing"."""
import json, os, glob
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
D = os.path.dirname(os.path.abspath(__file__))
SCHEMA = 1
REGIME = {"on": "haussier", "neutral": "neutre", "off": "baissier"}

def _hdir(root): return os.path.join(root or D, "state", "history")
def _utc(ts): return datetime.fromisoformat(ts).astimezone(timezone.utc)
def _paris(ts): return _utc(ts).astimezone(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y %Hh%M")
def _meta(c, k):
    r = c.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone(); return r[0] if r else None
def _cols(c, t): return {r[1] for r in c.execute(f"PRAGMA table_info({t})")}

def _portfolio(c, slot, ts):
    e = c.execute("SELECT equity,cash,exposure,btc_hold FROM equity WHERE slot=?", (slot,)).fetchone()
    C0 = _meta(c, "C0"); C0 = float(C0) if C0 else None
    eq = e[0] if e else None
    peak = max([r[0] for r in c.execute("SELECT equity FROM equity WHERE ts<=?", (ts,))] + ([C0] if C0 else []), default=None)
    fees = c.execute("SELECT COALESCE(SUM(fee),0) FROM orders WHERE ts<=?", (ts,)).fetchone()[0]
    return dict(equity=eq, cash=e[1] if e else None, exposure_pct=e[2] * 100 if e and e[2] is not None else None, btc_hold=e[3] if e else None,
                net_return_pct=(eq / C0 - 1) * 100 if eq is not None and C0 else None,
                cur_dd_pct=(1 - eq / peak) * 100 if eq is not None and peak else None, fees_total=fees)

def _orders(c, slot):
    liq = "liquidity" if "liquidity" in _cols(c, "orders") else "NULL"
    return [dict(id=r[0], asset=r[1], side=r[2], qty=r[3], price=r[4], notional=r[5], fee=r[6], pnl=r[7], reason=r[8], liquidity=r[9])
            for r in c.execute(f"SELECT id,asset,side,qty,price,notional,fee,pnl,reason,{liq} FROM orders WHERE slot=? ORDER BY id", (slot,))]

def _decisions(c, slot):
    return [dict(asset=r[0], action=r[1], reason=r[2]) for r in c.execute("SELECT asset,action,reason FROM decisions WHERE slot=? ORDER BY id", (slot,))]

def _base(c, slot, engine, strategy, complete):
    cy = c.execute("SELECT ts,status,mode FROM cycles WHERE slot=?", (slot,)).fetchone()
    ts = _utc(cy[0]).isoformat(timespec="seconds").replace("+00:00", "Z")
    s = dict(slot=slot, ts=ts, ts_paris=_paris(cy[0]), mode=cy[2], status=cy[1], versions=dict(engine=engine, strategy=strategy, ux=None),
             complete=complete, portfolio=_portfolio(c, slot, cy[0]), positions=None, regime=None, indicators=None,
             decisions=_decisions(c, slot), orders=_orders(c, slot), missing=["versions.ux"])
    s["missing"] += [f"portfolio.{k}" for k, v in s["portfolio"].items() if v is None]
    return s

def snapshot(c, slot, engine, strategy):
    """Instantané complet ; à appeler juste après le commit du cycle (positions/indicateurs = état courant)."""
    s = _base(c, slot, engine, strategy, True)
    px = {r[0]: r[1] for r in c.execute("SELECT asset,bid FROM prices WHERE slot=?", (slot,))}  # valorisation au bid, comme equity()
    s["positions"] = []
    for a, pair, q, avg, ent, hi, st in c.execute("SELECT asset,pair,qty,avg_price,entry_ts,high,stop FROM positions ORDER BY asset"):
        p = px.get(a); v = q * p if p is not None else None
        s["positions"].append(dict(asset=a, pair=pair, qty=q, avg_price=avg, price=p, value=v, pnl=q * (p - avg) if p is not None and avg else None,
                                   pnl_pct=(p / avg - 1) * 100 if p is not None and avg else None, entry_ts=ent, high=hi, stop=st))
        if p is None: s["missing"].append(f"positions.{a}.price")
    snap = json.loads(_meta(c, "daily_snapshot") or "{}")
    if snap:
        band = snap.get("band") or [None, None]
        s["regime"] = dict(state=REGIME.get(snap.get("state")), btc_close=snap.get("btc_close"), ema50=snap.get("btc_e50"), band_low=band[0], band_high=band[1],
                           decided_ts=snap.get("ts"), candle=snap.get("candle"))
    else: s["missing"].append("regime")
    rank = snap.get("rank", {})
    s["indicators"] = [dict(asset=r[0], close=r[1], ema20=r[2], ema50=r[3], rsi=r[4], adx=r[5], macd_hist=r[6], vol_ratio=r[7], score=r[8], rank=rank.get(r[0]),
                            trend_ok=None if r[9] is None else bool(r[9]), slot=r[10])
                       for r in c.execute("SELECT asset,close,ema20,ema50,rsi,adx,macd_hist,vol_ratio,score,trend_ok,slot FROM indicators ORDER BY asset")]
    if not s["indicators"]: s["missing"].append("indicators")
    return s

def _load(path, month):
    if os.path.exists(path):
        return json.load(open(path))
    return dict(schema_version=SCHEMA, month=month, cycles=[])

def _write(path, obj):
    tmp = path + ".tmp"; json.dump(obj, open(tmp, "w"), ensure_ascii=False, separators=(",", ":")); os.replace(tmp, path)

def write_snapshots(snaps, root=None, replace=True):
    h = _hdir(root); os.makedirs(h, exist_ok=True); by = {}
    for s in snaps: by.setdefault(s["ts"][:7], []).append(s)
    for m, lst in by.items():
        p = os.path.join(h, f"{m}.json"); f = _load(p, m); cur = {x["slot"]: x for x in f["cycles"]}
        for s in lst:
            if replace or s["slot"] not in cur: cur[s["slot"]] = s
        f["cycles"] = sorted(cur.values(), key=lambda x: x["ts"]); _write(p, f)
    update_index(root)

def update_index(root=None):
    h = _hdir(root); months = []
    for p in sorted(glob.glob(os.path.join(h, "[0-9][0-9][0-9][0-9]-[0-9][0-9].json"))):
        cy = json.load(open(p))["cycles"]
        if cy: months.append(dict(month=os.path.basename(p)[:7], file=f"state/history/{os.path.basename(p)}", n_cycles=len(cy), first_ts=cy[0]["ts"], last_ts=cy[-1]["ts"]))
    _write(os.path.join(h, "index.json"), dict(schema_version=SCHEMA, updated=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
           first_ts=months[0]["first_ts"] if months else None, last_ts=months[-1]["last_ts"] if months else None,
           n_cycles=sum(m["n_cycles"] for m in months), months=months))

def backfill(c, root=None, skip=()):
    """Cycles passés (status ok) absents de l'historique -> complete:false. Idempotent."""
    h = _hdir(root); have = set()
    for p in glob.glob(os.path.join(h, "[0-9]*-*.json")): have |= {x["slot"] for x in json.load(open(p))["cycles"]}
    ov = "version" if "version" in _cols(c, "orders") else None
    out = []
    for (slot,) in c.execute("SELECT slot FROM cycles WHERE status='ok' ORDER BY ts").fetchall():
        if slot in have or slot in skip: continue
        ev = c.execute(f"SELECT {ov} FROM orders WHERE slot=? AND {ov} IS NOT NULL LIMIT 1", (slot,)).fetchone() if ov else None
        sv = c.execute("SELECT strategy_version FROM cycles WHERE slot=?", (slot,)).fetchone()[0] if "strategy_version" in _cols(c, "cycles") else None
        s = _base(c, slot, ev[0] if ev else None, sv, False)
        s["missing"] += ["positions", "regime", "indicators"] + ([] if ev else ["versions.engine"]) + ([] if sv else ["versions.strategy"])
        out.append(s)
    if out: write_snapshots(out, root, replace=False)
    return len(out)

def export_cycle(c, slot, engine, strategy, root=None):
    """Point d'entrée moteur : rattrapage si l'historique n'existe pas encore, puis instantané du cycle."""
    if not os.path.exists(os.path.join(_hdir(root), "index.json")): backfill(c, root, skip={slot})
    s = snapshot(c, slot, engine, strategy); write_snapshots([s], root); return s

if __name__ == "__main__":  # rattrapage manuel : python3 history_export.py [chemin sim.db] [racine]
    import sqlite3, sys
    db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, "sim.db")
    print(f"{backfill(sqlite3.connect(db), sys.argv[2] if len(sys.argv) > 2 else None)} instantané(s) rattrapé(s)")
