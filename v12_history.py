#!/usr/bin/env python3
"""Append-only V1.2 paper snapshots using HISTORY_SCHEMA schema_version=1.
Each snapshot is an immutable observation of a real cycle. No invented fills.
"""
import json
import os
import re
import tempfile
from pathlib import Path
from v12_isolation import state_dir

def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".v12-history-",suffix=".json",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf8") as out:
            json.dump(data,out,ensure_ascii=False,allow_nan=False,indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def record_snapshot(raw, directory=None):
    if not isinstance(raw,dict):
        raise ValueError("snapshot dict required")
    slot=str(raw.get("slot") or "")
    ts=str(raw.get("ts") or "")
    if not re.fullmatch(r"\d{10}",slot) or not ts.startswith(slot[:4]+"-") or not raw.get("status"):
        raise ValueError("invalid cycle slot/timestamp/status")
    if raw.get("strategy_version") not in ("V1.2",None):
        raise ValueError("refusing foreign strategy")
    root=state_dir(directory)
    month=slot[:4]+"-"+slot[4:6]
    folder=root/"history"
    file=folder/(month+".json")
    previous={"schema_version":1,"month":month,"cycles":[]}
    if file.exists():
        previous=json.loads(file.read_text(encoding="utf8"))
        if previous.get("schema_version")!=1 or previous.get("month")!=month:
            raise ValueError("history schema mismatch")
    if any(x.get("slot")==slot for x in previous["cycles"]):
        raise ValueError("duplicate immutable slot: refusing overwrite")
    item=dict(raw)
    item["strategy_version"]="V1.2"
    item["schema_version"]=1
    previous["cycles"].append(item)
    previous["cycles"].sort(key=lambda x:x["slot"])
    atomic_json(file,previous)
    months=[]
    for p in sorted(folder.glob("????-??.json")):
        d=json.loads(p.read_text(encoding="utf8"))
        cycles=d.get("cycles",[])
        if cycles:
            months.append({"month":d["month"],"file":"history/"+p.name,
                           "n_cycles":len(cycles),"first_ts":cycles[0]["ts"],"last_ts":cycles[-1]["ts"]})
    index={"schema_version":1,"updated":ts,"first_ts":months[0]["first_ts"],
           "last_ts":months[-1]["last_ts"],"n_cycles":sum(m["n_cycles"] for m in months),
           "months":months}
    atomic_json(folder/"index.json",index)
    return file
