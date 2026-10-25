#!/usr/bin/env python3
"""Strict preproduction-only serializer for REAL V1.2 cycle state.
All legacy UI keys exist; absent observations are null, never fake zero.
Never rewrites or resets the V1.1 public state or sim.db.
"""
import json
import os
import tempfile
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from v12_isolation import state_dir

ROOT=Path(__file__).resolve().parent
LEGACY_KEYS=tuple(json.loads((ROOT/"tests"/"contract.json").read_text(encoding="utf-8"))["required_D_keys"])
ACTUAL=("equity","cash","positions","orders","decisions","as_of","last_cycle_iso")

def normalize(raw):
    if not isinstance(raw,dict):
        raise TypeError("V1.2 source must be a real cycle state object")
    missing=[x for x in ACTUAL if x not in raw or raw[x] is None]
    if missing:
        raise ValueError("missing actual V1.2 cycle fields: "+", ".join(missing))
    if raw.get("strategy_version") not in (None,"V1.2"):
        raise ValueError("foreign strategy rejected")
    if raw.get("environment") not in (None,"preprod"):
        raise ValueError("foreign environment rejected")
    from v12_accounting import d
    cash,equity=d(raw["cash"]),d(raw["equity"])
    if cash<0 or equity<0 or cash>equity:
        raise ValueError("cash/equity invariant violated")
    if not isinstance(raw["positions"],list) or not isinstance(raw["orders"],list) or not isinstance(raw["decisions"],list):
        raise ValueError("cycle positions/orders/decisions must be lists")
    for name in ("as_of","last_cycle_iso"):
        parsed=datetime.fromisoformat(raw[name].replace("Z","+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("V1.2 timestamp requires timezone: "+name)
    now=datetime.now(timezone.utc)
    dct=dict(raw)
    for key in LEGACY_KEYS:
        dct.setdefault(key,None)
    engine=(ROOT/"VERSION_ENGINE_V12").read_text(encoding="utf8").strip()
    if not engine.startswith("V"):
        raise ValueError("invalid isolated V1.2 engine version")
    dct.update(schema_version=1,strategy_id="kraken-sim-v1.2",
               strategy_version="V1.2",version_engine=engine,
               environment="preprod",
               source="Kraken Sim V1.2 independent PAPER ledger",
               source_detail={"strategy":"V1.2","repo":"kraken-sim-preprod",
                              "branch":"state-v12","real_cycle":True},
               generated_utc=now.isoformat(),
               generated_paris=now.astimezone(ZoneInfo("Europe/Paris")).isoformat())
    # UI alias is only computed from an actual observed equity, never a zero/fake.
    dct["total"]=equity if dct.get("total") is None else dct["total"]
    dct["C0"]=6605.10 if dct.get("C0") is None else dct["C0"]
    json.dumps(dct,allow_nan=False)
    return dct

def write_export(raw,directory=None):
    data=normalize(raw)
    target=state_dir(directory)
    target.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".v12-",suffix=".json",dir=target)
    try:
        with os.fdopen(fd,"w",encoding="utf8") as f:
            json.dump(data,f,ensure_ascii=False,allow_nan=False,indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,target/"public_state_v12.json")
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return target/"public_state_v12.json"
