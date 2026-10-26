#!/usr/bin/env python3
"""V2 PAPER: validate GrokBot plan and externally sourced Kraken market snapshot.

No API keys, no Kraken private endpoints, no real orders. Default: HOLD.
The first autonomous execution remains disabled until explicit owner GO.
"""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from decimal import Decimal

from plan_contract import (
    validate_plan, InvalidPlan, dec, ALLOWED_ASSETS, MAX_INVESTED_USDC,
    MAX_SPREAD_PCT, MIN_DEPTH_MULTIPLE, MAX_DRAWDOWN_PCT,
    REFERENCE_CAPITAL_USDC
)
from paper_executor import apply_cycle, RejectedCycle

ROOT = Path(__file__).resolve().parent
SOURCE = "grokbot_verified"


class MarketRejected(ValueError):
    pass


def market_snapshot(snapshot, now=None):
    """Reject stale, unsourced, or incomplete snapshots rather than invent prices."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(snapshot, dict) or snapshot.get("source") != "kraken_public":
        raise MarketRejected("Verified public Kraken snapshot required")
    try:
        ts = datetime.fromisoformat(snapshot["ts"].replace("Z", "+00:00"))
    except (ValueError, KeyError, AttributeError):
        raise MarketRejected("Invalid market timestamp") from None
    if ts.tzinfo is None or ts > now or now - ts > timedelta(seconds=10):
        raise MarketRejected("Market snapshot older than 10 seconds")
    quotes = snapshot.get("quotes")
    if not isinstance(quotes, dict) or not quotes:
        raise MarketRejected("No market quotes")
    out = {}
    for asset, quote in quotes.items():
        if asset not in ALLOWED_ASSETS or not isinstance(quote, dict):
            raise MarketRejected("Unsupported or malformed quote")
        if quote.get("pair") != asset + "/USDC":
            raise MarketRejected("Only XXX/USDC quotes accepted")
        if not isinstance(quote.get("endpoint"), str) or not quote["endpoint"].startswith("https://api.kraken.com/0/public/"):
            raise MarketRejected("Kraken public endpoint provenance required")
        try:
            price = dec(quote["price"], "price", min_value=Decimal("0.000000000000000001"))
            spread = dec(quote["spread_pct"], "spread_pct")
            depth = dec(quote["depth_usdc"], "depth_usdc")
            fee_rate = dec(quote["fee_rate_pct"], "fee_rate_pct", max_value=Decimal("100"))
        except (InvalidPlan, KeyError) as exc:
            raise MarketRejected(f"Invalid market quote {asset}: {exc}") from exc
        out[asset] = {"price": price, "spread_pct": spread, "depth_usdc": depth,
                      "fee_rate_pct": fee_rate}
    return out


def plan_status(plan, state, snapshot, now=None):
    """Read-only preview; never submits an order, including a PAPER order."""
    now = now or datetime.now(timezone.utc)
    p = validate_plan(plan, now)
    quotes = market_snapshot(snapshot, now)
    if state.get("data_source") != SOURCE:
        return {"status": "HOLD", "reason": "Verified initial portfolio missing", "plan_id": p["plan_id"]}
    if p["expired"]:
        return {"status": "HOLD", "reason": "Plan expired: no new buys", "plan_id": p["plan_id"]}
    initial = dec((state.get("_ledger") or {}).get("initial", state.get("initial")), "initial", min_value=Decimal("0.000000000000000001"))
    cash = dec((state.get("_ledger") or {}).get("cash", state.get("cash")), "cash")
    positions = (state.get("_ledger") or {}).get("positions", state.get("positions")) or {}
    if any(a not in quotes for a, q in positions.items() if Decimal(str(q)) > 0):
        return {"status": "HOLD", "reason": "Missing live price for existing position", "plan_id": p["plan_id"]}
    equity = cash + sum((Decimal(str(q)) * quotes[a]["price"] for a, q in positions.items()), Decimal(0))
    peak = state.get("peak_equity")
    if peak is None:
        return {"status": "HOLD", "reason": "Verified peak equity required for drawdown guard", "plan_id": p["plan_id"]}
    peak = dec(peak, "peak_equity", min_value=Decimal("0.000000000000000001"))
    if equity < peak * (Decimal(100) - MAX_DRAWDOWN_PCT) / 100:
        return {"status": "KILL", "reason": "Portfolio drawdown guard", "plan_id": p["plan_id"]}
    invested = equity - cash
    if invested > MAX_INVESTED_USDC:
        return {"status": "HOLD", "reason": "Existing exposure exceeds hard cap", "plan_id": p["plan_id"]}
    return {"status": "READY_FOR_REVIEW", "reason": "Plan and market checks passed; execution still disabled",
            "plan_id": p["plan_id"], "expires_at": plan["expires_at"],
            "current_exposure_usdc": str(invested), "equity_usdc": str(equity),
            "assets_checked": sorted(quotes)}


def main():
    parser = argparse.ArgumentParser(description="V2 PAPER-only read-only preflight")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--market", type=Path, required=True, help="Verified Kraken public market snapshot")
    parser.add_argument("--state", type=Path, default=ROOT / "state.json")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    snapshot = json.loads(args.market.read_text(encoding="utf-8"))
    state = json.loads(args.state.read_text(encoding="utf-8"))
    print(json.dumps(plan_status(plan, state, snapshot), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
