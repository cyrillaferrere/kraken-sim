#!/usr/bin/env python3
"""PAPER spot ledger primitives. Decimal math; long/cash only; no real order API."""
from decimal import Decimal

def d(value):
    x = Decimal(str(value))
    if not x.is_finite():
        raise ValueError("non-finite value")
    return x

class Portfolio:
    def __init__(self, cash):
        self.cash = d(cash)
        if self.cash < 0: raise ValueError("negative initial cash")
        self.positions = {}  # asset -> {qty, avg_cost} with buy fees included
        self.fees_paid = Decimal("0")
        self.realized_pnl = Decimal("0")

    def buy(self, asset, qty, price, fee_rate):
        q, p, f = d(qty), d(price), d(fee_rate)
        if not asset or q <= 0 or p <= 0 or not 0 <= f < 1:
            raise ValueError("invalid buy")
        fee = q * p * f
        total = q * p + fee
        if total > self.cash:
            raise ValueError("insufficient cash; no leverage")
        previous = self.positions.get(asset, {"qty": Decimal("0"), "avg_cost": Decimal("0")})
        new_qty = previous["qty"] + q
        new_avg = (previous["avg_cost"] * previous["qty"] + total) / new_qty
        self.cash -= total
        self.positions[asset] = {"qty": new_qty, "avg_cost": new_avg}
        self.fees_paid += fee
        return fee

    def sell(self, asset, qty, price, fee_rate):
        q, p, f = d(qty), d(price), d(fee_rate)
        holding = self.positions.get(asset)
        if q <= 0 or p <= 0 or not 0 <= f < 1 or holding is None or q > holding["qty"]:
            raise ValueError("invalid sale or forbidden short")
        fee = q * p * f
        proceeds = q * p - fee
        pnl = proceeds - q * holding["avg_cost"]
        self.cash += proceeds
        self.realized_pnl += pnl
        self.fees_paid += fee
        remaining = holding["qty"] - q
        if remaining:
            holding["qty"] = remaining
        else:
            del self.positions[asset]
        return pnl

    def equity(self, bids):
        total = self.cash
        for asset, holding in self.positions.items():
            if asset not in bids: raise ValueError("missing bid for held asset " + asset)
            p = d(bids[asset])
            if p <= 0: raise ValueError("invalid bid")
            total += holding["qty"] * p
        return total
