#!/usr/bin/env python3
"""Independent V1.2 PAPER ledger. No V1.1 imports, no implicit DB path."""
import os
import sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parent
C0 = 6605.10

class IsolationError(RuntimeError): pass

def state_dir(raw=None):
    raw = raw if raw is not None else os.environ.get("V12_STATE_DIR")
    if not raw or not os.path.isabs(raw):
        raise IsolationError("V12_STATE_DIR: explicit absolute path required")
    path = Path(raw).resolve()
    if path == ROOT or ROOT in path.parents or path == Path("/"):
        raise IsolationError("V1.2 cannot write inside production repository")
    if path.name in ("kraken-sim", "kraken-sim-state", "state"):
        raise IsolationError("forbidden V1.2 directory")
    if path.exists() and not path.is_dir():
        raise IsolationError("V1.2 state target must be a directory")
    return path

def db_path(raw=None):
    return state_dir(raw) / "sim_v12.db"

def connect(raw=None):
    path = db_path(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.execute("CREATE TABLE IF NOT EXISTS cycles(slot TEXT PRIMARY KEY, ts TEXT NOT NULL, status TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL)")
    db.commit()
    return db

def record_cycle(db, slot, ts, status="validated"):
    if not slot or not ts: raise ValueError("slot and timestamp required")
    with db:
        cur = db.execute("INSERT OR IGNORE INTO cycles(slot,ts,status) VALUES(?,?,?)",(slot,ts,status))
    return cur.rowcount == 1
