#!/usr/bin/env python3
"""V2 PAPER cycle. Never calls a Kraken private endpoint or places a real order.

Input snapshots must be sourced and verified externally. Output is a candidate
file, never an automatic publication. This module is deterministic under tests.
"""
import argparse
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

from plan_contract import validate_plan, InvalidPlan, dec, guardrails, ALLOWED_ASSETS, utc
from paper_executor import apply_cycle, RejectedCycle

ROOT = Path(__file__).resolve().parent
SOURCE = "grokbot_verified"
REASONS = ("CAP_2000", "ASSET_40PCT", "INSUFFICIENT_DEPTH", "SPREAD", "STALE_DATA",
           "KILL_SWITCH", "BELOW_MIN", "RATE_LIMIT", "PLAN_EXPIRED", "INELIGIBLE",
           "NO_MARKET", "NO_FEE", "NO_LIQUIDITY", "INSUFFICIENT_CASH")


class MarketRejected(ValueError):
    pass


def market_snapshot(snapshot, now=None, limits=None):
    now = now or datetime.now(timezone.utc)
    limits = limits or guardrails()
    if not isinstance(snapshot, dict) or snapshot.get("source") != "kraken_public":
        raise MarketRejected("Verified public Kraken snapshot required")
    try:
        ts = utc(snapshot["ts"], "market timestamp")
    except (KeyError, InvalidPlan) as exc:
        raise MarketRejected("Invalid market timestamp") from exc
    if abs((now - ts).total_seconds()) > limits["max_clock_skew_seconds"] and ts > now:
        raise MarketRejected("STALE_DATA: clock skew")
    if ts > now or now - ts > timedelta(seconds=limits["max_market_age_seconds"]):
        raise MarketRejected("STALE_DATA")
    quotes = snapshot.get("quotes")
    if not isinstance(quotes, dict) or not quotes:
        raise MarketRejected("No quotes")
    result = {}
    for asset, quote in quotes.items():
        if asset not in ALLOWED_ASSETS or not isinstance(quote, dict):
            raise MarketRejected("Unsupported quote")
        if quote.get("pair") != asset + "/USDC":
            raise MarketRejected("Only XXX/USDC")
        if not isinstance(quote.get("endpoint"), str) or not quote["endpoint"].startswith("https://api.kraken.com/0/public/"):
            raise MarketRejected("Public Kraken provenance required")
        try:
            fields = {key: dec(quote[key], key, min_value=Decimal("0.000000000000000001") if key in ("price", "min_order_usdc", "median_volume_30d_usdc") else Decimal(0))
                      for key in ("price", "spread_pct", "depth_usdc", "maker_fee_pct", "taker_fee_pct", "min_order_usdc", "median_volume_30d_usdc")}
        except (KeyError, InvalidPlan) as exc:
            raise MarketRejected(f"Missing or invalid {asset} liquidity/fee data") from exc
        if fields["maker_fee_pct"] <= 0 or fields["taker_fee_pct"] <= 0:
            raise MarketRejected("NO_FEE")
        if type(quote.get("eligible_eee")) is not bool:
            raise MarketRejected("Missing EEE compliance result")
        book = quote.get("asks"), quote.get("bids")
        if any(not isinstance(side, list) or not side for side in book):
            raise MarketRejected("Missing order book")
        for side in book:
            for level in side:
                if not isinstance(level, list) or len(level) != 2:
                    raise MarketRejected("Malformed book")
                dec(level[0], "book price", min_value=Decimal("0.000000000000000001"))
                dec(level[1], "book qty", min_value=Decimal("0.000000000000000001"))
        result[asset] = {**fields, "eligible_eee": quote["eligible_eee"],
                         "asks": quote["asks"], "bids": quote["bids"],
                         "endpoint": quote["endpoint"]}
    return result


def walk_book(side, qty):
    remaining = qty
    total = Decimal(0)
    for price, available in ((Decimal(str(x[0])), Decimal(str(x[1]))) for x in side):
        fill = min(remaining, available)
        total += fill * price
        remaining -= fill
        if remaining <= 0:
            return total / qty
    return None


def depth_near_mid(q, side):
    mid = q["price"]
    low, high = mid * Decimal("0.995"), mid * Decimal("1.005")
    return sum((Decimal(str(qty)) * Decimal(str(price)) for price, qty in q[side]
                if low <= Decimal(str(price)) <= high), Decimal(0))


def market_eligibility(q, asset, limits):
    if not q["eligible_eee"] or q["median_volume_30d_usdc"] < Decimal("1000000"):
        return "INELIGIBLE"
    if q["spread_pct"] > limits["max_spread_pct"]:
        return "SPREAD"
    return None


def maker_fill(q, side, limit, later_trades, *, placed_at=None, timeout_min=30):
    """Maker fill requires a timestamped independent trade AFTER placement and BEFORE timeout."""
    if not isinstance(later_trades, list) or placed_at is None:
        return False
    for trade in later_trades:
        if not isinstance(trade, dict) or "ts" not in trade or "price" not in trade:
            continue
        trade_time = utc(trade["ts"], "maker trade time")
        if not placed_at < trade_time <= placed_at + timedelta(minutes=timeout_min):
            continue
        p = dec(trade["price"], "subsequent trade", min_value=Decimal("0.000000000000000001"))
        if (side == "BUY" and p <= limit) or (side == "SELL" and p >= limit):
            return True
    return False


def execute_plan(plan, previous, snapshot, *, now=None, limits=None):
    """Returns candidate state; caller must review and publish separately."""
    now = now or datetime.now(timezone.utc)
    limits = limits or guardrails()
    p = validate_plan(plan, now, limits)
    quotes = market_snapshot(snapshot, now, limits)
    if previous.get("data_source") != SOURCE:
        raise RejectedCycle("Verified initial portfolio required; no fabricated capital")
    ledger = previous.get("_ledger") or {}
    initial = dec(ledger.get("initial", previous.get("initial")), "initial", min_value=Decimal("0.000000000000000001"))
    if initial != limits["reference_capital_usdc"]:
        raise RejectedCycle("Reference capital mismatch")
    cash = dec(ledger.get("cash", previous.get("cash")), "cash")
    positions = {a: dec(v, "position") for a, v in (ledger.get("positions", previous.get("positions")) or {}).items()}
    if any(a not in quotes for a, qty in positions.items() if qty):
        raise MarketRejected("NO_MARKET for held position")
    equity = cash + sum((qty * quotes[a]["price"] for a, qty in positions.items()), Decimal(0))
    peak = dec(previous.get("peak_equity"), "peak_equity", min_value=Decimal("0.000000000000000001"))
    peak = max(peak, equity)
    prior_kill = bool(previous.get("kill_switch"))
    fresh_ack = p["ack_kill_switch"] and p["plan_id"] != previous.get("kill_ack_plan_id") and p["plan_id"] != previous.get("plan_active", {}).get("id")
    killed = (prior_kill and not fresh_ack) or (peak - equity >= limits["kill_drawdown_usdc"])
    # Acknowledgement clears a prior kill only after drawdown is recovered.
    if fresh_ack and peak - equity < limits["kill_drawdown_usdc"]:
        killed = False
    prior_orders = previous.get("orders") or []
    last24 = [o for o in prior_orders if o.get("ts") and
              now - timedelta(hours=24) < utc(o["ts"], "order.ts") <= now]
    max_count = min(p["max_orders_per_cycle"], limits["max_orders_per_cycle"],
                    max(0, limits["max_orders_24h"] - len(last24)))
    orders, rejects = [], []
    envelope = limits["max_invested_usdc"]
    cost_basis = {a: dec(v, "cost basis") for a, v in (previous.get("cost_basis") or {}).items()}
    if positions and any(a not in cost_basis for a in positions):
        raise RejectedCycle("Verified cost basis required for held positions")
    invested = sum(cost_basis.values(), Decimal(0))
    if invested > envelope:
        killed = True
    cycle_id = now.strftime("%Y-%m-%dT%H") + ":v2"
    if cycle_id in previous.get("processed_cycle_ids", []):
        return previous  # deterministic idempotence, no publication
    if previous.get("updated") and (now - utc(previous["updated"], "updated")) < timedelta(minutes=45):
        return previous
    simulated_cash = cash
    simulated_positions = dict(positions)

    def reject(asset, side, reason):
        rejects.append({"asset": asset, "side": side, "reason": reason})

    # SELL before BUY; stop-loss uses externally verified average entry.
    entry_prices = previous.get("entry_prices") or {}
    for side in ("SELL", "BUY"):
        for asset in sorted(set(p["targets"]) | set(positions)):
            if asset == "USDC":
                continue
            qty = simulated_positions.get(asset, Decimal(0))
            q = quotes.get(asset)
            if not q:
                reject(asset, side, "NO_MARKET")
                continue
            price = q["price"]
            target = envelope * p["targets"].get(asset, Decimal(0))
            current = qty * price
            stop = False
            take = False
            if qty:
                entry = dec(entry_prices[asset], "entry") if asset in entry_prices else cost_basis[asset] / qty
                if asset in p["stop_loss_pct"]:
                    stop = price <= entry * (1 - p["stop_loss_pct"][asset])
                if asset in p["take_profit_pct"]:
                    take = price >= entry * (1 + p["take_profit_pct"][asset])
            delta = target - current
            if side == "SELL":
                if not qty or (not (stop or take or p["regime"] == "cash") and delta >= -envelope * Decimal("0.02")):
                    continue
                notional = current if stop or take or p["regime"] == "cash" else -delta
                notional = min(notional, current)
            else:
                if p["expired"]:
                    reject(asset, side, "PLAN_EXPIRED")
                    continue
                if killed:
                    reject(asset, side, "KILL_SWITCH")
                    continue
                if delta <= envelope * Decimal("0.02"):
                    continue
                notional = delta
            zone = p["buy_zones" if side == "BUY" else "sell_zones"].get(asset)
            if zone and not zone[0] <= price <= zone[1] and not stop and not take:
                continue
            reason = market_eligibility(q, asset, limits)
            if reason:
                reject(asset, side, reason)
                continue
            if len(orders) >= max_count:
                reject(asset, side, "RATE_LIMIT")
                continue
            notional = min(notional, current if side == "SELL" else simulated_cash)
            if side == "BUY":
                cap_room = envelope - invested
                asset_room = envelope * limits["max_asset_fraction"] - cost_basis.get(asset, Decimal(0))
                minimum = max(limits["min_order_usdc"], q["min_order_usdc"])
                if cap_room < minimum:
                    reject(asset, side, "CAP_2000")
                    continue
                if asset_room < minimum:
                    reject(asset, side, "ASSET_40PCT")
                    continue
                notional = min(notional, cap_room, asset_room)
            if notional < max(limits["min_order_usdc"], q["min_order_usdc"]):
                reject(asset, side, "BELOW_MIN")
                continue
            book_side = "asks" if side == "BUY" else "bids"
            if depth_near_mid(q, book_side) < notional * limits["min_depth_multiple"]:
                reject(asset, side, "INSUFFICIENT_DEPTH")
                continue
            style = p["execution"]["style"]
            # Maker orders only fill when independently supplied subsequent trades cross limit.
            if style == "maker_first":
                later = snapshot.get("subsequent_trades", {}).get(asset)
                if not maker_fill(q, side, price, later, placed_at=utc(snapshot['ts'], 'market timestamp'), timeout_min=p['execution']['maker_timeout_min']):
                    reject(asset, side, "MAKER_TIMEOUT")
                    continue
                execution_price = price
                fee_pct = q["maker_fee_pct"]
            else:
                # Iteratively account for the execution book and fees, never free fills.
                fee_pct = q["taker_fee_pct"]
                if side == "BUY":
                    notional = min(notional, simulated_cash / (1 + fee_pct / 100))
                execution_price = walk_book(q[book_side], notional / price)
                if execution_price is None:
                    reject(asset, side, "INSUFFICIENT_DEPTH")
                    continue
            quantity = notional / execution_price
            gross = quantity * execution_price
            fee = gross * fee_pct / 100
            if side == "BUY":
                if gross + fee > simulated_cash:
                    reject(asset, side, "INSUFFICIENT_CASH")
                    continue
                if invested + gross + fee > envelope:
                    reject(asset, side, "CAP_2000")
                    continue
                if cost_basis.get(asset, Decimal(0)) + gross + fee > envelope * limits["max_asset_fraction"]:
                    reject(asset, side, "ASSET_40PCT")
                    continue
                simulated_cash -= gross + fee
                simulated_positions[asset] = qty + quantity
                cost_basis[asset] = cost_basis.get(asset, Decimal(0)) + gross + fee
                invested += gross + fee
            else:
                if quantity > qty:
                    quantity = qty
                    gross = quantity * execution_price
                    fee = gross * fee_pct / 100
                simulated_cash += gross - fee
                simulated_positions[asset] = qty - quantity
                reduction = cost_basis.get(asset, Decimal(0)) * quantity / qty
                cost_basis[asset] = cost_basis.get(asset, Decimal(0)) - reduction
                invested -= reduction
            orders.append({"asset": asset, "side": side, "qty": str(quantity),
                           "price": str(execution_price), "fee": str(fee),
                           "slippage_pct": str((execution_price / price - 1) * 100),
                           "style": style})
    ts = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    cycle = {"data_source": SOURCE, "cycle_id": cycle_id, "ts": ts,
             "prices": {a: str(q["price"]) for a, q in quotes.items()},
             "decisions": [{k: o[k] for k in ("asset", "side", "qty", "price", "fee")} for o in orders],
             "signals": previous.get("signals") or []}
    candidate = apply_cycle(previous, cycle)
    candidate["cost_basis"] = {a: str(v) for a, v in cost_basis.items() if v > 0}
    candidate["peak_equity"] = float(max(peak, Decimal(str(candidate["equity"]))))
    candidate["kill_switch"] = killed
    candidate["kill_ack_plan_id"] = p["plan_id"] if fresh_ack else previous.get("kill_ack_plan_id")
    candidate["plan_active"] = {"id": p["plan_id"], "regime": p["regime"],
                                "rationale": p["rationale"], "expires_at": plan["expires_at"]}
    candidate["active_plan"] = {**candidate["plan_active"], "plan_id": p["plan_id"],
                                "targets": {a: float(v) for a, v in p["targets"].items()},
                                "expired": p["expired"]}
    candidate["rejections"] = rejects
    candidate["liquidity"] = {a: {"spread_pct": float(q["spread_pct"]),
                                  "depth_usdc": float(q["depth_usdc"])} for a, q in quotes.items()}
    candidate["data_provenance"] = {"market_source": "kraken_public", "market_ts": snapshot["ts"],
                                    "endpoints": {a: q["endpoint"] for a, q in quotes.items()}}
    candidate["engine"] = "V2.0.1"
    return candidate


def main():
    parser = argparse.ArgumentParser(description="V2 PAPER candidate generator (no publication)")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--market", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=ROOT / "state.json")
    parser.add_argument("--output", type=Path, help="Candidate JSON output, never live state")
    args = parser.parse_args()
    if args.output and args.output.resolve() == args.state.resolve():
        parser.error("Refusing direct publication")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    snapshot = json.loads(args.market.read_text(encoding="utf-8"))
    state = json.loads(args.state.read_text(encoding="utf-8"))
    candidate = execute_plan(plan, state, snapshot)
    if args.output:
        args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps({"status": "PREVIEW", "cycle_id": candidate.get("last_cycle_id"),
                          "new_orders": len(candidate.get("orders") or []) - len(state.get("orders") or []),
                          "rejections": candidate.get("rejections")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
