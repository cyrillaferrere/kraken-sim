#!/usr/bin/env python3
"""Conservative PAPER fill primitives. Trade tape is NOT a guaranteed queue fill."""
from decimal import Decimal
from v12_accounting import d

def passive_crossing_qty(side, limit_price, requested_qty, placed_at, trades, participation=0.5):
    """Strict after-placement crossing; fraction of public trade volume as model hypothesis.
    A limit buy requires trade BELOW bid limit, sell requires trade ABOVE ask limit.
    Return an upper-bound PAPER filled quantity; not an actual exchange execution.
    """
    price, wanted, share = d(limit_price), d(requested_qty), d(participation)
    if side not in ("buy", "sell") or price <= 0 or wanted <= 0 or not 0 < share <= 1:
        raise ValueError("invalid maker order")
    eligible = Decimal("0")
    for trade in trades:
        if trade["ts"] <= placed_at:
            continue
        px, qty = d(trade["price"]), d(trade["qty"])
        if px <= 0 or qty < 0:
            raise ValueError("invalid trade tape")
        crossed = (px < price) if side == "buy" else (px > price)
        if crossed:
            eligible += qty
    return min(wanted, eligible * share)

def taker_estimate(side, qty, bid, ask, fee_rate, slippage):
    """Bid/ask + adverse slip. No depth guarantee; caller must check order book."""
    q, b, a, f, s = map(d, (qty, bid, ask, fee_rate, slippage))
    if side not in ("buy", "sell") or q <= 0 or b <= 0 or a < b or a <= 0 or not 0 <= f < 1 or s < 0:
        raise ValueError("invalid taker quote")
    price = a * (1 + s) if side == "buy" else b * (1 - s)
    if price <= 0: raise ValueError("invalid slippage")
    fee = q * price * f
    cash_delta = -(q * price + fee) if side == "buy" else q * price - fee
    return {"side": side, "qty": q, "price": price, "fee": fee, "cash_delta": cash_delta}
