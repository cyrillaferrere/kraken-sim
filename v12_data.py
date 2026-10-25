#!/usr/bin/env python3
"""Kraken OFFLINE OHLCVT 1440 CSV importer. Manifest-gated, SHA-256 checked.
Official format: timestamp,open,high,low,close,volume,trades; no header.
Timestamps represent OPEN of daily period; exposed 'end' is CLOSED time +86400s.
"""
import csv
import hashlib
import json
import re
from datetime import datetime,timezone,timedelta
from pathlib import Path

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def read_kraken_daily(path, expected_sha256):
    p=Path(path)
    if not re.fullmatch(r"[0-9a-f]{64}",str(expected_sha256)):
        raise ValueError("Expected SHA256 required; no unverified data")
    if sha256_file(p)!=expected_sha256:
        raise ValueError("Kraken CSV does not match pinned SHA256")
    observed={}
    with open(p,newline="",encoding="utf8") as f:
        for number,row in enumerate(csv.reader(f),1):
            if not row: continue
            if len(row)!=7:
                raise ValueError("line %d: Kraken daily OHLCVT requires exactly 7 columns"%number)
            ts=int(float(row[0]))
            opening,high,low,close,volume=map(float,row[1:6])
            trades=int(float(row[6]))
            if ts%86400 or min(opening,high,low,close)<=0 or volume<0 or trades<0:
                raise ValueError("line %d: invalid time/price/volume"%number)
            if high<max(opening,close) or low>min(opening,close) or low>high:
                raise ValueError("line %d: inconsistent OHLC"%number)
            if ts in observed: raise ValueError("duplicate candle at %s"%ts)
            observed[ts]={"end":datetime.fromtimestamp(ts+86400,timezone.utc).isoformat(),
                          "open":opening,"high":high,"low":low,"close":close,
                          "volume":volume,"trades":trades,"imputed":False}
    if not observed: raise ValueError("empty OHLCVT data")
    times=sorted(observed)
    result=[]; missing=0; previous=None
    for ts in range(times[0],times[-1]+86400,86400):
        if ts in observed:
            b=observed[ts]
        else:
            missing+=1
            if previous is None: raise ValueError("impossible first gap")
            b={"end":datetime.fromtimestamp(ts+86400,timezone.utc).isoformat(),
               "open":previous,"high":previous,"low":previous,"close":previous,
               "volume":0.0,"trades":0,"imputed":True}
        result.append(b)
        previous=b["close"]
    return result, {"source_file":p.name,"sha256":expected_sha256,
                    "rows":len(result),"gaps_imputed":missing,
                    "first_closed":result[0]["end"],"last_closed":result[-1]["end"]}

def load_manifest(data_dir):
    root=Path(data_dir).resolve()
    p=root/"MANIFEST.json"
    if not p.is_file(): raise FileNotFoundError("Frozen data/v12/MANIFEST.json required; use MANIFEST.template.json")
    manifest=json.loads(p.read_text(encoding="utf8"))
    files=manifest.get("files")
    if not files or not isinstance(files,list): raise ValueError("Manifest must list actual pinned CSV files")
    output={}; descriptions={}
    for entry in files:
        asset=entry["asset"].upper()
        filename=entry["file"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\.csv",filename):
            raise ValueError("CSV file must be a basename under pinned directory")
        if asset in output: raise ValueError("duplicate asset in manifest: "+asset)
        if not entry.get("source_url") or not entry.get("retrieved_utc"):
            raise ValueError("provenance URL and retrieval time required")
        bars,stat=read_kraken_daily(root/filename,entry.get("sha256"))
        output[asset]=bars
        descriptions[asset]=dict(stat,source_url=entry["source_url"],
                                 retrieved_utc=entry["retrieved_utc"])
    return output, {"files":descriptions,"manifest_sha256":sha256_file(p)}
