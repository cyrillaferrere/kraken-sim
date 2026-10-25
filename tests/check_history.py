#!/usr/bin/env python3
"""Valide le schéma state/history (schema_version 1) sur un échantillon généré depuis une COPIE de sim.db (répertoire temporaire, prod intacte)."""
import json, os, re, shutil, sqlite3, sys, tempfile
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, R)
import history_export as H
SNAP = {"slot", "ts", "ts_paris", "mode", "status", "versions", "complete", "portfolio", "positions", "regime", "indicators", "decisions", "orders", "missing"}
PF = {"equity", "cash", "exposure_pct", "btc_hold", "net_return_pct", "cur_dd_pct", "fees_total"}
POS = {"asset", "pair", "qty", "avg_price", "price", "value", "pnl", "pnl_pct", "entry_ts", "high", "stop"}
REG = {"state", "btc_close", "ema50", "band_low", "band_high"}
IND = {"asset", "close", "ema20", "ema50", "rsi", "adx", "macd_hist", "vol_ratio", "score", "rank", "trend_ok"}
ORD = {"id", "asset", "side", "qty", "price", "notional", "fee", "pnl", "reason", "liquidity"}
ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
err = []
def ck(cond, msg):
    if not cond: err.append(msg)
def check_snap(s):
    ck(SNAP <= s.keys(), f"{s.get('slot')}: clés manquantes {SNAP - s.keys()}")
    ck(ISO.match(s["ts"]), f"ts {s['ts']}"); ck(re.match(r"^\d\d/\d\d/\d{4} \d\dh\d\d$", s["ts_paris"]), f"ts_paris {s['ts_paris']}")
    ck(set(s["versions"]) == {"engine", "strategy", "ux"}, "versions"); ck(PF <= s["portfolio"].keys(), "portfolio")
    for k in ("decisions", "orders"): ck(isinstance(s[k], list), k)
    for o in s["orders"]: ck(ORD <= o.keys(), "orders keys")
    for d in s["decisions"]: ck({"asset", "action", "reason"} <= d.keys(), "decisions keys")
    for k in ("positions", "regime", "indicators"):
        if s[k] is None: ck(k in s["missing"], f"{k} null sans missing")
    if s["complete"]:
        for p in s["positions"]: ck(POS <= p.keys(), "positions keys")
        if s["regime"]: ck(REG <= s["regime"].keys() and s["regime"]["state"] in ("haussier", "neutre", "baissier", None), "regime")
        for i in s["indicators"]: ck(IND <= i.keys(), "indicators keys")
    else: ck({"positions", "regime", "indicators"} <= set(s["missing"]), "backfill: missing incomplet")
    ck(json.loads(json.dumps(s)) == s, "non sérialisable")
tmp = tempfile.mkdtemp(); db = os.path.join(tmp, "sim.db"); shutil.copy(os.path.join(R, "sim.db"), db); c = sqlite3.connect(db)
slots = [r[0] for r in c.execute("SELECT slot FROM cycles WHERE status='ok' ORDER BY ts")]
assert slots, "aucun cycle dans sim.db"
s = H.export_cycle(c, slots[-1], "V1.2", "V1.1", root=tmp)  # 1er passage : rattrapage + instantané complet
H.export_cycle(c, slots[-1], "V1.2", "V1.1", root=tmp); H.backfill(c, root=tmp)  # idempotence
idx = json.load(open(os.path.join(tmp, "state/history/index.json")))
ck(idx["schema_version"] == 1 and idx["n_cycles"] == len(slots), f"index n_cycles {idx['n_cycles']} != {len(slots)}")
for m in idx["months"]:
    f = json.load(open(os.path.join(tmp, m["file"]))); cy = f["cycles"]
    ck(f["schema_version"] == 1 and f["month"] == m["month"] and m["n_cycles"] == len(cy), "mois")
    ck([x["ts"] for x in cy] == sorted(x["ts"] for x in cy), "tri"); ck(len({x["slot"] for x in cy}) == len(cy), "doublon slot")
    for x in cy: check_snap(x); ck(x["complete"] == (x["slot"] == slots[-1]), f"complete {x['slot']}")
size = len(json.dumps(s, ensure_ascii=False, separators=(",", ":")).encode())
shutil.rmtree(tmp)
if err: print("ÉCHEC :", *err, sep="\n - "); sys.exit(1)
print(f"historique OK : {len(slots)} cycles, instantané complet {size} octets")
