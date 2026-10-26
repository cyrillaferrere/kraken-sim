#!/usr/bin/env python3
"""V2 PAPER execution adapter. No exchange keys, no network, no real orders.

Input is an independently verified GrokBot cycle. Never generates strategy
signals, starting capital, execution prices, quantities, or fees.
"""
import argparse
import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

SOURCE = "grokbot_verified"
ASSET_RE = re.compile(r"^[A-Z0-9]{2,16}$")
CYCLE_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")


class RejectedCycle(ValueError):
    pass


def decimal(value, name, *, positive=False):
    if isinstance(value, bool) or value is None or not isinstance(value, (str, int, float, Decimal)):
        raise RejectedCycle(f"{name}: numeric value required")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise RejectedCycle(f"{name}: invalid decimal") from None
    if not d.is_finite() or d < 0 or (positive and d == 0):
        raise RejectedCycle(f"{name}: must be {'positive' if positive else 'nonnegative'} and finite")
    return d


def number(value):
    f = float(value)
    if not math.isfinite(f):
        raise RejectedCycle("Result is not finite")
    return f


def timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RejectedCycle("ts must be ISO-8601 UTC with Z")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise RejectedCycle("Invalid ts") from None
    if d.tzinfo is None:
        raise RejectedCycle("ts must be UTC")
    if d > datetime.now(timezone.utc):
        raise RejectedCycle("Future cycle timestamp")
    return d


def validate_asset(asset):
    if not isinstance(asset, str) or not ASSET_RE.fullmatch(asset):
        raise RejectedCycle("Invalid asset code")
    return asset


def apply_cycle(previous, cycle):
    if not isinstance(cycle, dict) or cycle.get("data_source") != SOURCE:
        raise RejectedCycle("Cycle requires data_source=grokbot_verified")
    cid = cycle.get("cycle_id")
    if not isinstance(cid, str) or not CYCLE_RE.fullmatch(cid):
        raise RejectedCycle("Missing or invalid cycle_id")
    dt = timestamp(cycle.get("ts"))
    if not isinstance(previous, dict):
        raise RejectedCycle("Invalid previous state")
    verified = previous.get("data_source") == SOURCE
    if verified:
        if cid == previous.get("last_cycle_id"):
            raise RejectedCycle("Duplicate cycle_id: idempotency guard")
        prior_ts = previous.get("updated")
        if prior_ts and dt <= timestamp(prior_ts):
            raise RejectedCycle("Cycle must be newer than published state")
        initial = decimal(previous.get("initial"), "previous.initial", positive=True)
        cash = decimal(previous.get("cash"), "previous.cash")
        positions = {validate_asset(a): decimal(q, "position qty") for a, q in (previous.get("positions") or {}).items()}
    else:
        if previous.get("data_source") not in (None, "") or previous.get("initial") is not None:
            raise RejectedCycle("Unrecognized previous state; refusing reset")
        initial = decimal(cycle.get("initial_usdc"), "initial_usdc", positive=True)
        cash, positions = initial, {}

    prices_in = cycle.get("prices")
    if not isinstance(prices_in, dict) or not prices_in:
        raise RejectedCycle("Verified market prices are required")
    prices = {validate_asset(a): decimal(p, f"prices.{a}", positive=True) for a, p in prices_in.items()}
    decisions = cycle.get("decisions")
    if not isinstance(decisions, list):
        raise RejectedCycle("decisions must be an array, even for HOLD")
    orders = list(previous.get("orders") or []) if verified else []
    new_orders = []
    fees = decimal(previous.get("fees"), "previous.fees") if verified else Decimal(0)
    for i, item in enumerate(decisions):
        if not isinstance(item, dict):
            raise RejectedCycle(f"decisions[{i}]: object required")
        asset = validate_asset(item.get("asset"))
        side = item.get("side")
        if side not in ("BUY", "SELL"):
            raise RejectedCycle("Only spot BUY and SELL are supported")
        if asset not in prices:
            raise RejectedCycle(f"Missing market price for {asset}")
        qty = decimal(item.get("qty"), f"decisions[{i}].qty", positive=True)
        execution_price = decimal(item.get("price"), f"decisions[{i}].price", positive=True)
        fee = decimal(item.get("fee"), f"decisions[{i}].fee")
        amount = qty * execution_price
        if side == "BUY":
            debit = amount + fee
            if debit > cash:
                raise RejectedCycle(f"Insufficient USDC for {asset}: no leverage or negative cash")
            cash -= debit
            positions[asset] = positions.get(asset, Decimal(0)) + qty
        else:
            if qty > positions.get(asset, Decimal(0)):
                raise RejectedCycle(f"Insufficient {asset}: no short selling")
            if fee > amount:
                raise RejectedCycle("Sell fee exceeds proceeds")
            positions[asset] -= qty
            cash += amount - fee
        fees += fee
        new_orders.append({"cycle_id": cid, "ts": cycle["ts"], "asset": asset, "side": side,
                           "qty": number(qty), "price": number(execution_price), "fee": number(fee)})
    positions = {a: q for a, q in positions.items() if q != 0}
    missing = set(positions) - set(prices)
    if missing:
        raise RejectedCycle("Missing verified mark prices for holdings: " + ", ".join(sorted(missing)))
    position_values = {a: number(q * prices[a]) for a, q in positions.items()}
    equity = cash + sum((q * prices[a] for a, q in positions.items()), Decimal(0))
    signals = cycle.get("signals", [])
    if not isinstance(signals, list):
        raise RejectedCycle("signals must be an array")
    # Signals and closed-trade statistics are external GrokBot attestations, not inferred here.
    for signal in signals:
        if not isinstance(signal, dict) or "asset" not in signal:
            raise RejectedCycle("Malformed signal")
        validate_asset(signal["asset"])
    summary = cycle.get("closed_trades_summary")
    if summary is not None:
        if not isinstance(summary, dict) or summary.get("source") != SOURCE:
            raise RejectedCycle("Unverified closed_trades_summary")
        for key in ("net_wins", "net_losses", "net_flats"):
            v = summary.get(key)
            if type(v) is not int or v < 0:
                raise RejectedCycle(f"Invalid closed_trades_summary.{key}")
    history = list(previous.get("history") or []) if verified else []
    history.append({"ts": cycle["ts"], "equity": number(equity), "cash": number(cash)})
    result = dict(previous)
    result.update({"schema": "v2-paper-1", "engine": "V2.0.0", "strategy": "V2.0",
                   "mode": "PAPER", "data_source": SOURCE, "initial": number(initial),
                   "cash": number(cash), "equity": number(equity),
                   "pnl_pct": number((equity / initial - 1) * 100),
                   "fees": number(fees), "cycles": int(previous.get("cycles") or 0) + 1,
                   "positions": {a: number(q) for a, q in positions.items()},
                   "position_values": position_values, "orders": orders + new_orders,
                   "history": history, "signals": signals, "updated": cycle["ts"],
                   "last_cycle_id": cid, "status": "PAPER · GrokBot vérifié"})
    if summary is not None:
        result["closed_trades_summary"] = summary
    if "closed_trades_history" in cycle:
        trade_history = cycle["closed_trades_history"]
        if not isinstance(trade_history, list) or any(
            not isinstance(t, dict) or t.get("source") != SOURCE or
            isinstance(t.get("net_pnl"), bool) or not isinstance(t.get("net_pnl"), (int, float)) or
            not math.isfinite(t["net_pnl"]) for t in trade_history
        ):
            raise RejectedCycle("Invalid closed_trades_history")
        result["closed_trades_history"] = trade_history
    return result


def main():
    parser = argparse.ArgumentParser(description="Strict PAPER-only V2 cycle processor")
    parser.add_argument("--input", required=True, type=Path, help="Verified GrokBot cycle JSON")
    parser.add_argument("--state", default=Path(__file__).with_name("state.json"), type=Path)
    parser.add_argument("--output", type=Path, help="Explicit output file (never defaults to live state)")
    args = parser.parse_args()
    if args.output is None:
        parser.error("--output is required: no implicit production publication")
    if args.output.resolve() == args.state.resolve():
        parser.error("Refusing to overwrite source state: publish separately after review")
    previous = json.loads(args.state.read_text(encoding="utf-8"))
    cycle = json.loads(args.input.read_text(encoding="utf-8"))
    result = apply_cycle(previous, cycle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=args.output.parent, prefix=".paper-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
        os.replace(temp, args.output)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print(f"Validated PAPER cycle {result['last_cycle_id']} -> {args.output}")


if __name__ == "__main__":
    main()
