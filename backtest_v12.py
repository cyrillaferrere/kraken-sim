#!/usr/bin/env python3
"""V1.2 offline exploratory backtest ONLY — not official OOS validation.
Frozen Kraken CSV MANIFEST required; never download/overwrite datasets silently.
"""
import argparse
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from v12_data import load_manifest
from v12_backtest_core import run_experiment

ROOT=Path(__file__).resolve().parent
def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--experimental",action="store_true",
                   help="Explicitly acknowledge these are NOT walk-forward approval results")
    p.add_argument("--data-dir",required=False)
    p.add_argument("--out",required=False)
    p.add_argument("--start",required=False)
    p.add_argument("--end",required=False)
    x=p.parse_args(argv)
    if not x.experimental:
        p.error("official OOS walk-forward, benchmarks and acceptance criteria not yet available; pass --experimental to test the defaults")
    if not x.data_dir or not x.out:
        p.error("offline frozen --data-dir and --out required")
    param=json.loads((ROOT/"strategy"/"v1_2"/"params.json").read_text())
    if param["STRATEGY_VERSION"]!="V1.2" or param["STATUS"]!="experimental-unselected":
        p.error("strategy version/status must be experimental V1.2")
    data,meta=load_manifest(x.data_dir)
    if len(data)<2 or "BTC" not in data:
        p.error("insufficient pinned dataset: BTC plus other assets required")
    results=[]
    for name in "ABCD":
        for fee in ("F1","F2"):
            results.append(run_experiment(data,name,param["CANDIDATES"][name],param["RISK"],
                                          param["COSTS"],tier=fee,start=x.start,end=x.end,c0=param["C0"]))
    dest=Path(x.out).resolve()
    if dest==ROOT/"backtest_v12_results.json":
        p.error("do not overwrite official results name with unvalidated exploratory data")
    dest.parent.mkdir(parents=True,exist_ok=True)
    output={"status":"EXPERIMENTAL_NOT_OOS_VALIDATED","strategy_version":"V1.2",
            "generated_utc":datetime.now(timezone.utc).isoformat(),
            "manifest_sha256":meta["manifest_sha256"],"data":meta["files"],
            "warnings":["No 12m/3m walk-forward yet","No V1.1 benchmark reproduction yet",
                        "No formal stress/sensitivity/gap delisting acceptance yet",
                        "Daily OHLC does not prove maker queue fill"],
            "runs":results}
    dest.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print("Exploratory V1.2 runs written:",dest)
    print("NOT A DEPLOYMENT APPROVAL. Walk-forward and V1.1 comparison remain mandatory.")
    return 0
if __name__=="__main__": sys.exit(main())
