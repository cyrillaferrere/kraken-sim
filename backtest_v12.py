#!/usr/bin/env python3
"""OFFLINE-only strategy investigation. No orders, keys or API calls.
Diagnostic runs CANNOT select a winner. WALK-FORWARD is fail-closed until
full historical universe + independent V1.1 reproduction are supplied.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from v12_data import load_manifest
from v12_backtest_core import run_experiment,calendar_days
from v12_walkforward import (make_folds,evaluate_candidate,require_verifiable_baseline,
                             gate_results)
from v12_baselines import baselines
from v12_signals import point_in_time_universe

ROOT=Path(__file__).resolve().parent
SPEC=ROOT/"strategy"/"v1_2"/"params.json"

def main(argv=None):
    p=argparse.ArgumentParser(description="Kraken Sim V1.2 — recherche backtest hors ligne seulement")
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--experimental",action="store_true",help="diagnostics non comparables à des performances validées")
    mode.add_argument("--walk-forward",action="store_true",help="essai protocole OOS, exige univers historique et baseline V1.1 audités")
    p.add_argument("--data-dir",required=True,help="dossier local avec CSV Kraken et MANIFEST.json figé")
    p.add_argument("--out",required=True,help="fichier JSON de sortie hors dépôt d'état")
    p.add_argument("--baseline-v11-json",help="reproduction auditée V1.1 exigée en mode walk-forward")
    p.add_argument("--start",default=None)
    p.add_argument("--end",default=None)
    args=p.parse_args(argv)
    params=json.loads(SPEC.read_text(encoding="utf8"))
    if params["STRATEGY_VERSION"]!="V1.2" or params["STATUS"]!="experimental-unselected":
        p.error("Only frozen and unselected V1.2 strategy hypotheses can be analyzed")
    data,meta=load_manifest(args.data_dir,require_complete=args.walk_forward)
    if len(data)<2 or "BTC" not in data:
        p.error("pinned BTC and other historical assets required")
    instruments=meta["files"]
    sha=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    now=datetime.now(timezone.utc)
    dest=Path(args.out).resolve()
    if dest.is_relative_to(ROOT/"state") or dest.name=="public_state_v12.json":
        p.error("never write an experimental report to the live state")
    if not args.walk_forward and dest==ROOT/"backtest_v12_results.json":
        p.error("exploratory diagnostics cannot overwrite official result filename")
    report={"schema_version":1,"strategy_version":"V1.2","engine_version":(ROOT/"VERSION_ENGINE_V12").read_text().strip(),
            "generated_utc":now.isoformat(),"code_commit":sha,
            "manifest_sha256":meta["manifest_sha256"],"universe_coverage":meta.get("coverage"),
            "financial_approval":False}
    if args.experimental:
        runs={}
        for name in "ABCD":
            runs[name]={}
            for fee in ("F1","F2"):
                runs[name][fee]=run_experiment(data,name,params["CANDIDATES"][name],params["RISK"],
                                               params["COSTS"],tier=fee,start=args.start,end=args.end,
                                               c0=params["C0"],metadata=instruments,common=params["COMMON"])
        report.update(status="EXPERIMENTAL_DIAGNOSTICS_ONLY",
                      warnings=["NOT OUT OF SAMPLE","No verified V1.1 replay","No survivorship guarantee",
                                "Never use these diagnostics to rank candidates or approve deployment"],
                      unvalidated_diagnostics=runs,selected_candidate=None)
    else:
        # Reject BEFORE optimization if the V1.1 reference has not been reproduced.
        if not args.baseline_v11_json:
            p.error("V11_BASELINE_NOT_REPRODUCED: supply validated reference on the same dataset")
        raw_btc=calendar_days(data)
        folds=make_folds(raw_btc,train_months=int(params["VALIDATION"]["train_months"]),
                         test_months=int(params["VALIDATION"]["test_months"]),
                         step_months=int(params["VALIDATION"]["step_months"]))
        # At least 5 live eligible instruments at the TRAINING start, never chosen using future listing.
        folds=[f for f in folds if len(point_in_time_universe(data,f["train_start"]))>=5]
        if not folds:
            p.error("NO_WALK_FORWARD_FOLDS: insufficient verified historical breadth or dates")
        v11=json.loads(Path(args.baseline_v11_json).read_text(encoding="utf8"))
        require_verifiable_baseline(v11,meta["manifest_sha256"],folds)
        evaluations={}
        for name in "ABCD":
            evaluations[name]=evaluate_candidate(data,name,params["CANDIDATES"][name],
                                                  params["RISK"],params["COSTS"],folds,
                                                  metadata=instruments,common=params["COMMON"],c0=params["C0"])
        decision=gate_results(evaluations,v11,meta["manifest_sha256"],folds)
        reference={}
        for fee in ("F1","F2"):
            per_fold=[]
            for f in folds:
                bench=baselines(data,(f["test_start"],f["test_end"]),
                                params["COSTS"][fee],params["COSTS"],params["C0"])
                per_fold.append({name:{"return":row["net_return"],
                                       "max_drawdown":row["max_drawdown_signed"],
                                       "fees_usd":row["fees_usd"]} for name,row in bench.items()})
            # Compounded OOS period returns, consistent with concatenated candidate path.
            reference[fee]={name:{"net_return":__import__("math").prod(1+b[name]["return"] for b in per_fold)-1,
                                  "folds":[b[name] for b in per_fold]}
                            for name in ("BTC","EQUAL_BTC_ETH_XRP","CASH")}
            reference[fee]["V1.1"]={"net_return":v11["results"][fee]["net_return"],
                                    "source":"audited replay matching manifest"}
        report.update(status="WALK_FORWARD_EVALUATED_PAPER_ONLY",
                      windows=folds,benchmarks=reference,
                      decision=decision,evaluations=evaluations,
                      warnings=["NO APPROVAL: Grok/Cyril must still sign off",
                                "Historical delisting LAST_PRINT convention is an optimistic proxy",
                                "OHLC maker partial model is a hypothesis, not execution evidence"])
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf8")
    print("V1.2 offline report:",dest)
    print("Financial approval: NO. No bot trading cycle started.")
    return 0

if __name__=="__main__":sys.exit(main())
