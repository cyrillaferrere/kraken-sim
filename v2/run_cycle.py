#!/usr/bin/env python3
"""V2 unattended routine preflight and safe candidate staging (no network, no publication).

A cycle never silently uses synthetic or missing inputs. The routine accepts only
externally collected and verified plan, market snapshot, and portfolio state.
"""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from engine import execute_plan, MarketRejected
from paper_executor import RejectedCycle
from plan_contract import InvalidPlan

ROOT = Path(__file__).resolve().parent


def stage_candidate(plan_path, market_path, state_path, output_path, now=None):
    plan_path, market_path, state_path, output_path = map(Path, (plan_path, market_path, state_path, output_path))
    if output_path.resolve() in {plan_path.resolve(), market_path.resolve(), state_path.resolve()}:
        raise ValueError("Refusing to overwrite input")
    if output_path.name == "state.json":
        raise ValueError("Refusing direct state publication")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    market = json.loads(market_path.read_text(encoding="utf-8"))
    previous = json.loads(state_path.read_text(encoding="utf-8"))
    candidate = execute_plan(plan, previous, market, now=now)
    if candidate is previous or candidate == previous:
        return {"status": "SKIPPED", "reason": "duplicate or cycle under 45 minutes"}
    if candidate.get("mode") != "PAPER" or candidate.get("data_source") != "grokbot_verified":
        raise ValueError("Invalid candidate mode or source")
    if candidate.get("initial") is None or candidate.get("_ledger") is None:
        raise ValueError("Missing verified portfolio ledger")
    if output_path.exists():
        raise FileExistsError("Candidate path exists; refusing overwrite")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=output_path.parent, prefix=".candidate-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(candidate, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, output_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {"status": "STAGED", "cycle_id": candidate["last_cycle_id"],
            "orders": len(candidate.get("orders") or []) - len(previous.get("orders") or []),
            "candidate_path": str(output_path)}


def main():
    parser = argparse.ArgumentParser(description="V2 PAPER routine: safe offline candidate only")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--market", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(stage_candidate(args.plan, args.market, args.state, args.output),
                         ensure_ascii=False))
    except (InvalidPlan, MarketRejected, RejectedCycle, ValueError, OSError, KeyError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
