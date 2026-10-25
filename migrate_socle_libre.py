"""Migration unique : le socle de départ devient des positions normales de la stratégie (aucun ordre)."""
import sqlite3, json, sys
db = sys.argv[1] if len(sys.argv) > 1 else "/workspace/kraken-sim/sim.db"
c = sqlite3.connect(db); m = dict(c.execute("SELECT k,v FROM meta"))
if m.get("core_migrated"): print("déjà migré"); sys.exit()
sig = json.loads(m.get("last_signals") or "{}"); slot = c.execute("SELECT MAX(slot) FROM prices").fetchone()[0]
for a, pair, qty, avg, ts in c.execute("SELECT asset,pair,qty,avg,ts FROM core").fetchall():
    last = c.execute("SELECT last FROM prices WHERE slot=? AND asset=?", (slot, a)).fetchone()[0]
    stop = last - 3 * sig[a]["atr"] if a in sig else None
    c.execute("INSERT OR REPLACE INTO positions VALUES(?,?,?,?,?,?,?)", (a, pair, qty, avg, ts, last, stop)); print(a, qty, avg, ts, "stop", stop)
for k, v in (("C0_strat", m["C0"]), ("core_migrated", "2026-10-25T10:33:33Z")): c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)", (k, v))
c.commit()
