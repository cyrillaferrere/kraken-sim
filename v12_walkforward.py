#!/usr/bin/env python3
"""Chronological walk-forward 12 months IS / 3 months OOS.
Pure orchestration — NEVER calls private exchange endpoints or places orders.
No "official" acceptance without an audited V1.1 baseline and full historical
survivorship coverage, both on exactly the same dataset/period/cost assumptions.
"""
import calendar
import copy
from datetime import date,datetime
from itertools import product
from math import sqrt
from statistics import mean,stdev
from v12_acceptance import reject_candidate,choose_candidate
from v12_backtest_core import run_experiment,_drawdown

def add_months(d,n):
    month=d.month-1+n
    year=d.year+month//12
    month=month%12+1
    return date(year,month,min(d.day,calendar.monthrange(year,month)[1]))

def make_folds(days,train_months=12,test_months=3,step_months=3,warmup=250):
    """Date-exclusive boundaries prevent using test observations for training.
    Require initial warm-up before fitting or starting a backtest window.
    """
    dates=sorted({datetime.fromisoformat(x.replace("Z","+00:00")).date() for x in days})
    if len(dates)<warmup+1:
        return []
    start=dates[warmup]
    last=dates[-1]
    output=[]
    while True:
        split=add_months(start,train_months)
        end=add_months(split,test_months)
        if end>last:
            break
        train=[x for x in dates if start<=x<split]
        test=[x for x in dates if split<=x<end]
        if train and test:
            output.append({"train_start":train[0].isoformat(),
                           "train_end":train[-1].isoformat(),
                           "test_start":test[0].isoformat(),
                           "test_end":test[-1].isoformat(),
                           "train_days":len(train),"test_days":len(test)})
        start=add_months(start,step_months)
    return output

def param_grid(default):
    """All dimensions, including 'max_per_asset' for D; fixed defaults separately."""
    keys=sorted(default["grid"])
    values=[default["grid"][k] for k in keys]
    for combo in product(*values):
        point=copy.deepcopy({k:v for k,v in default.items() if k!="grid"})
        point.update(dict(zip(keys,combo)))
        yield point

def neighbors(default):
    """Immediate single-axis neighbors of frozen default (not fitted OOS parameters)."""
    result=[]
    for key,vals in sorted(default["grid"].items()):
        if default[key] not in vals:
            raise ValueError("default value not in sensitivity grid: "+key)
        i=vals.index(default[key])
        for j in (i-1,i+1):
            if 0<=j<len(vals):
                c=copy.deepcopy({k:v for k,v in default.items() if k!="grid"})
                c[key]=vals[j]
                result.append(c)
    return result

def _run(data,name,p,risk,costs,tier,window,metadata,common):
    start=window["start"]+"T00:00:00+00:00" if len(window["start"])==10 else window["start"]
    end=window["end"]+"T23:59:59+00:00" if len(window["end"])==10 else window["end"]
    return run_experiment(data,name,p,risk,costs,tier=tier,
                          start=start,end=end,metadata=metadata,common=common)

def fold_choice(data,name,default,risk,costs,fold,metadata=None,common=None):
    """Fit ONLY within IS, maximizing Calmar at conservative F2 tier."""
    start,end=fold["train_start"],fold["train_end"]
    scoring=[]
    for point in param_grid(default):
        res=_run(data,name,point,risk,costs,"F2",{"start":start,"end":end},metadata,common)
        # Spec chooses the best Calmar in-sample; undefined Calmar is not a winner.
        calmar=res.get("calmar")
        if calmar is not None:
            scoring.append((calmar,point))
    if not scoring:
        raise ValueError("NO_FITTABLE_CALMAR: "+name)
    # Stable tie-breaking to make selection reproducible.
    return max(scoring,key=lambda t:(t[0],repr(sorted(t[1].items()))))[1]

def concat_oos(fold_runs,c0):
    """Concatenate non-overlapping OOS equity paths, respecting compounding.
    Per-fold cash resets are accounted as resets, never presented as live replay.
    """
    scale=1.;series=[]
    fees=spread=slip=gross=0.;trades=0;kill=0
    last_date=None
    for r in fold_runs:
        if r["start"]<=last_date if last_date is not None else False:
            raise ValueError("overlapping or unordered OOS folds")
        before=scale
        for row in r["curve"]:
            series.append({"day":row["day"],"equity":row["equity"]*before,
                           "cash":row["cash"]*before})
        scale*=1+r["net_return"]
        last_date=r["end"]
        fees+=r["fees_usd"]*before
        spread+=r["spread_usd"]*before
        slip+=r["slippage_usd"]*before
        gross+=r["gross_profit_usd"]*before
        trades+=r["closed_roundtrips"]
        kill+=r["kill_switch_count"]
    if not series:
        raise ValueError("no OOS folds")
    values=[row["equity"] for row in series]
    dds,duration=_drawdown(values,c0)
    net=values[-1]/c0-1
    annual=(1+net)**(365/len(values))-1 if 1+net>0 else -1
    returns=[b/a-1 for a,b in zip([c0]+values[:-1],values) if a>0]
    down=sqrt(mean([min(v,0)**2 for v in returns])) if returns else 0
    return {"net_return":net,"max_drawdown_signed":dds,
            "drawdown_duration":duration,"calmar":annual/abs(dds) if dds else None,
            "sortino":mean(returns)*sqrt(365)/down if down else None,
            "fees_spread_slippage_usd":fees+spread+slip,
            "gross_profit_usd":gross,"closed_roundtrips":trades,
            "kill_switch_count":kill,"curve":series}

def evaluate_candidate(data,name,defaults,risk,costs,folds,metadata=None,common=None,c0=6605.10):
    """Run all OOS folds after IS tuning; F1/F2 use SAME trained parameters."""
    if not folds:raise ValueError("NO_WALK_FORWARD_FOLDS")
    results={"F1":[],"F2":[]};choices=[]
    for fold in folds:
        p=fold_choice(data,name,defaults,risk,costs,fold,metadata,common)
        choices.append({"fold":fold,"params":p})
        window={"start":fold["test_start"],"end":fold["test_end"]}
        for tier in ("F1","F2"):
            results[tier].append(_run(data,name,p,risk,costs,tier,window,metadata,common))
    aggs={tier:concat_oos(result,c0) for tier,result in results.items()}
    # Sensitivity: all neighbors of UNOPTIMIZED defaults, with same OOS windows.
    neighbor_returns=[]
    for point in neighbors(defaults):
        runs=[_run(data,name,point,risk,costs,"F2",
                   {"start":f["test_start"],"end":f["test_end"]},metadata,common) for f in folds]
        neighbor_returns.append(concat_oos(runs,c0)["net_return"])
    return {"folds":choices,"oos_f1":aggs["F1"],"oos_f2":aggs["F2"],
            "fold_returns_oos_f2":[r["net_return"] for r in results["F2"]],
            "default_neighbors_oos_f2":neighbor_returns}

def require_verifiable_baseline(payload,manifest_sha,folds):
    """A comparison without an independently reproduced V1.1 reference is rejected."""
    if not isinstance(payload,dict) or payload.get("status")!="REPRODUCED_V11":
        raise ValueError("V11_BASELINE_NOT_REPRODUCED")
    if payload.get("manifest_sha256")!=manifest_sha:
        raise ValueError("BASELINE_DATASET_MISMATCH")
    expected=[(f["test_start"],f["test_end"]) for f in folds]
    if payload.get("fold_windows")!=[list(x) for x in expected]:
        raise ValueError("BASELINE_FOLD_MISMATCH")
    for tier in ("F1","F2"):
        item=payload.get("results",{}).get(tier,{})
        if not isinstance(item.get("net_return"),(float,int)):
            raise ValueError("BASELINE_MISSING_"+tier)
    if not payload.get("v11_replay_verified"):
        raise ValueError("V11_BASELINE_REPLAY_UNVERIFIED")
    return payload

def gate_results(evaluations,baseline,manifest_sha,folds):
    """Reject anything without defensible OOS and frozen comparison."""
    verified=require_verifiable_baseline(baseline,manifest_sha,folds)
    candidates={}
    for name,ev in evaluations.items():
        a,b=ev["oos_f1"],ev["oos_f2"]
        x={"evaluation_status":"VALIDATED_WALK_FORWARD",
           "net_oos_f1":a["net_return"],"net_oos_f2":b["net_return"],
           "v11_net_oos_f2":verified["results"]["F2"]["net_return"],
           "max_drawdown_oos_f2":b["max_drawdown_signed"],
           "fold_returns_oos_f2":ev["fold_returns_oos_f2"],
           "fees_spread_slippage_usd_f2":b["fees_spread_slippage_usd"],
           "gross_profit_usd_f2":b["gross_profit_usd"],
           "neighbors_oos_f2":ev["default_neighbors_oos_f2"],
           "closed_roundtrips_oos":b["closed_roundtrips"],
           "calmar_oos_f2":b["calmar"],"sortino_oos_f2":b["sortino"]}
        rejected,why=reject_candidate(x)
        candidates[name]={"metrics":x,"rejected":rejected,"reasons":why}
    selected=choose_candidate({n:d["metrics"] for n,d in candidates.items()})
    return {"status":"WALK_FORWARD_EVALUATED","selected_candidate":selected,
            "decision":"NO_DEPLOYMENT" if selected is None else "REQUIRES_CYRIL_APPROVAL",
            "candidates":candidates}
