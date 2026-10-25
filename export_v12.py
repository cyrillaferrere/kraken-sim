#!/usr/bin/env python3
"""Preproduction-only state serializer; never fabricate absent market data."""
import json
import os
import tempfile
from v12_isolation import state_dir
REQUIRED=("equity","cash","positions","orders","decisions","as_of","last_cycle_iso")

def normalize(raw):
    if not isinstance(raw,dict): raise TypeError("state object required")
    absent=[k for k in REQUIRED if k not in raw]
    if absent: raise ValueError("missing actual cycle fields: "+", ".join(absent))
    if raw.get("strategy_version") not in (None,"V1.2"): raise ValueError("foreign strategy")
    if raw.get("environment") not in (None,"preprod"): raise ValueError("foreign environment")
    d=dict(raw)
    d.update(schema_version=1,strategy_id="kraken-sim-v1.2",
             strategy_version="V1.2",version_engine="V1.3",
             environment="preprod",source="V1.2 independent paper simulation")
    return d

def write_export(raw,directory=None):
    data=normalize(raw)
    target=state_dir(directory)
    target.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".v12-",suffix=".json",dir=target)
    try:
        with os.fdopen(fd,"w",encoding="utf8") as f:
            json.dump(data,f,ensure_ascii=False,allow_nan=False,indent=2)
            f.write("\n")
        os.replace(tmp,target/"public_state_v12.json")
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return target/"public_state_v12.json"
