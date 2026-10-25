#!/usr/bin/env python3
"""Offline, point-in-time liquidity eligibility comparison. NO engine mutations.

Input JSON: observations with asof, asset, quote, daily_volume_quote, bid,
ask, optional depth_sell_usdc_2pct, fx_to_usdc. fx_to_usdc converts quote
turnover to USDC AT THE OBSERVATION DATE. Cannot infer depth from candles.
Output: eligibility + coverage only, never a claim of OOS profitability.
"""
import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

THRESHOLDS={"A_5m":5_000_000,"B_2m":2_000_000,"B_1m":1_000_000,
            "B_500k":500_000,"C_global_5m":5_000_000}
FIXED={"max_spread":0.003,"max_slippage":0.0015,
       "max_failed_fills":0.05,"min_mean_pairs":4,
       "min_daily_history":220,"order_equity_fraction":0.02,
       "walk_forward_in_months":12,"walk_forward_out_months":3,
       "fee_scenarios":["F1","F2"],
       "fallback":"A_5m"}
def number(value):
    if isinstance(value,bool):raise ValueError("boolean numeric")
    v=float(value)
    if not math.isfinite(v) or v<0:raise ValueError("nonfinite or negative")
    return v
def time(value):
    if not isinstance(value,str):raise ValueError("timestamp required")
    t=datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None:raise ValueError("timezone required")
    return t.astimezone(timezone.utc).date().isoformat()
def analyze(data):
    if not isinstance(data,dict) or not isinstance(data.get("observations"),list):
        raise ValueError("observations array required")
    by=defaultdict(dict)
    for row in data["observations"]:
        day=time(row["asof"]);asset=str(row["asset"]).upper();quote=str(row["quote"]).upper()
        if not asset.isalnum() or quote not in ("USDC","USD","EUR"):
            raise ValueError("unsupported pair")
        key=(asset,quote)
        if key in by[day]:raise ValueError("duplicate observation")
        vol=number(row["daily_volume_quote"])*number(row["fx_to_usdc"])
        bid=number(row["bid"]);ask=number(row["ask"])
        if bid<=0 or ask<bid:raise ValueError("invalid quote")
        by[day][key]={"vol":vol,"spread":(ask-bid)/((ask+bid)/2),
                      "bars":int(row.get("closed_daily_bars",0)),
                      "depth":row.get("depth_sell_usdc_2pct")}
    # Requires 30 observed daily points for EVERY candidate date (no forward
    # fill, no missing-date median, no future volume).
    from datetime import date,timedelta
    dates=sorted(by)
    snapshots=[]
    for day in dates:
        today=date.fromisoformat(day)
        window=[(today-timedelta(days=i)).isoformat() for i in range(29,-1,-1)]
        if any(k not in by for k in window):continue
        assets={a for a,q in by[day] if q=="USDC"}
        counts={name:0 for name in THRESHOLDS};states={}
        for asset in sorted(assets):
            needed={q:[by[t].get((asset,q)) for t in window]
                    for q in ("USDC","USD","EUR")}
            usdc=needed["USDC"]
            if any(x is None for x in usdc):continue
            last=usdc[-1]
            if last["bars"]<FIXED["min_daily_history"] or last["spread"]>FIXED["max_spread"]:continue
            usdcmedian=sorted(x["vol"] for x in usdc)[14:16]
            median=sum(usdcmedian)/2
            # Total volume at each observation date, not sum of
            # cross-market medians. Missing historical quote => never assume
            # zero: C is unassessable without complete coverage.
            global_median=None
            if all(all(x is not None for x in needed[q]) for q in needed):
                daily=[sum(needed[q][i]["vol"] for q in needed) for i in range(30)]
                ordered=sorted(daily);global_median=(ordered[14]+ordered[15])/2
            tests={k:(median>=v if k!="C_global_5m" else
                       global_median is not None and global_median>=v)
                   for k,v in THRESHOLDS.items()}
            for name,ok in tests.items():
                if ok:counts[name]+=1
            states[asset]={"usdc_median":round(median,2),
                           "global_median":round(global_median,2) if global_median is not None else None,
                           "usdc_spread":round(last["spread"],6),
                           "eligible":tests,
                           "execution_depth_verified":last["depth"] is not None}
        snapshots.append({"asof":day,"eligible_count":counts,"assets":states})
    n=len(snapshots)
    means={name:(sum(s["eligible_count"][name] for s in snapshots)/n if n else None)
           for name in THRESHOLDS}
    return {"status":"ELIGIBILITY_DIAGNOSTIC_ONLY_NOT_OOS_RESULT",
            "fixed_criteria":FIXED,"scenarios":THRESHOLDS,
            "evaluated_days":n,"mean_eligible_pairs":means,
            "observations":snapshots,
            "execution_metrics_verified":False,
            "strategy_returns_verified":False,
            "decision":"NO_SELECTION_PENDING_DEPTH_FILLS_AND_WALK_FORWARD"}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    src=Path(args.input).resolve();dst=Path(args.output).resolve()
    if src==dst:raise ValueError("input and output paths must differ")
    if dst.exists():raise ValueError("will not overwrite existing report")
    report=analyze(json.loads(src.read_text(encoding="utf8")))
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print(json.dumps({"status":report["status"],"days":report["evaluated_days"]}))
if __name__=="__main__":main()
