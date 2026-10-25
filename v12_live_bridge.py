#!/usr/bin/env python3
"""One-shot Kraken public market check, and offline testable IT wiring.

Default CLI reads Kraken PUBLIC endpoints and prints a summary, WITHOUT
creating a portfolio. It never places trades, invokes Grok or schedules work.
The engine runner below is for integration tests / future authorized scheduler.
"""
import argparse
import json
import os
import tempfile
from datetime import datetime,timezone
from pathlib import Path
from v12_autonomy import utc
from v12_isolation import state_dir
from v12_kraken_public import collect,overview

def paper_step(engine,snapshot,now,verified_issue=None):
    """Engine-owned step, with optional already-authenticated IT issue.

    Does NOT call Kraken or GitHub itself; the caller must use read-only
    collectors/issue parser, and keep agent output separate from risk data.
    """
    moment=utc(now) if isinstance(now,str) else now.astimezone(timezone.utc)
    if snapshot.get("data_origin")!="KRAKEN_PUBLIC_API":
        raise ValueError("REAL_MARKET_COLLECTOR_REQUIRED")
    if utc(snapshot["observed_at"])!=moment:
        raise ValueError("MARKET_TIMESTAMP_MISMATCH")
    executed=engine.tick(snapshot,moment.isoformat())
    if executed["status"] not in ("DRY_RUN","PAUSED_MISSING_MARKET"):
        raise ValueError("UNEXPECTED_ENGINE_CYCLE_STATE")
    synthesis=None
    if executed["status"]=="DRY_RUN":
        synthesis=engine.build_synthesis(snapshot,moment.isoformat())
    accepted=[]
    if verified_issue is not None:
        if not isinstance(verified_issue,dict) or "batch" not in verified_issue or "issue_number" not in verified_issue:
            raise ValueError("VERIFIED_ISSUE_REQUIRED")
        if synthesis is None:raise ValueError("MARKET_PAUSED_NO_GROK_ADMISSION")
        accepted=engine.admit_batch(verified_issue["batch"],moment.isoformat())
    return {"tick":executed,"synthesis":synthesis,"it_decisions":accepted,
            "live_orders":0,"source":"KRAKEN_PUBLIC_PAPER"}

def fetch_and_step(engine,authorized_github_user_id,github_read_token,max_pairs=40):
    """One-shot full PUBLIC Kraken -> authorized GitHub Issue -> PAPER engine.

    Deliberately NOT exposed as a CLI or scheduled workflow. Before first
    invocation, Cyril must approve isolated state storage, token permissions,
    trading policy and use of the PAPER executor. No exchange API keys.
    """
    from v12_grok_issues import fetch_recent,InboxError
    if not github_read_token or type(authorized_github_user_id) is not int or authorized_github_user_id<=0:
        raise ValueError("GROK_ISSUE_AUTHORIZATION_REQUIRED")
    snapshot=collect(max_pairs=max_pairs)
    # Independent stop and risk management runs FIRST, even if GitHub is down.
    result=paper_step(engine,snapshot,snapshot["observed_at"])
    try:
        issues=fetch_recent(authorized_github_user_id,github_read_token)
    except InboxError:
        result["it_status"]="GITHUB_UNAVAILABLE_NO_NEW_DECISIONS"
        return result
    if not issues:
        result["it_status"]="NO_GROK_IT"
        return result
    result["it_issue_numbers"]=[]
    result["it_errors"]=[]
    for issue in issues:
        try:
            decisions=engine.admit_batch(issue["batch"],snapshot["observed_at"])
            result["it_decisions"].extend(decisions)
            result["it_issue_numbers"].append(issue["issue_number"])
        except (ValueError,TypeError,KeyError) as exc:
            result["it_errors"].append({"issue_number":issue["issue_number"],"reason":str(exc)})
    result["it_status"]="GROK_ITS_PARTIALLY_REJECTED" if result["it_errors"] else "GROK_ITS_PROCESSED"
    return result

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--check-market",action="store_true",required=True)
    parser.add_argument("--max-pairs",type=int,default=8)
    args=parser.parse_args(argv)
    snapshot=collect(max_pairs=args.max_pairs)
    result=overview(snapshot)
    result["cli_mode"]="PUBLIC_DATA_READ_ONLY_NO_PAPER_CYCLE"
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
