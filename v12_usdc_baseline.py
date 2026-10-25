#!/usr/bin/env python3
"""Observed USDC/USD hold baseline; never assumes one USDC equals one USD."""
from datetime import timedelta
from v12_accounting import d
from v12_autonomy import utc

def checked_rate(quote,as_of,max_age_seconds=300):
    """Trusted public-Kraken USDC/USD market quote, not model output."""
    if not isinstance(quote,dict) or quote.get("source")!="trusted-public-kraken":
        raise ValueError("USDC_QUOTE_SOURCE_NOT_TRUSTED")
    now,at=utc(as_of),utc(quote["as_of"])
    if now-at>timedelta(seconds=max_age_seconds) or at>now:
        raise ValueError("USDC_QUOTE_STALE")
    bid,ask=d(quote["bid"]),d(quote["ask"])
    if bid<=0 or ask<bid or (ask-bid)/((ask+bid)/2)>d("0.003"):
        raise ValueError("USDC_QUOTE_INVALID")
    return {"bid":bid,"ask":ask,"as_of":at.isoformat()}

def initial_units(usd_start,usdc_quote,as_of):
    """Not a trade; creates a hypothetical USDC-hold counterfactual."""
    q=checked_rate(usdc_quote,as_of)
    cash=d(usd_start)
    if cash<=0:raise ValueError("INITIAL_USD_REQUIRED")
    return cash/q["ask"]

def usd_value(units,usdc_quote,as_of):
    """Conservative mark: the observed price at which USDC can be sold."""
    q=checked_rate(usdc_quote,as_of)
    return d(units)*q["bid"]

def pnl_vs_usdc(paper_equity,units,usdc_quote,as_of):
    """Nullable only outside this helper; missing price explicitly raises."""
    value=usd_value(units,usdc_quote,as_of)
    return {"paper_usd":str(d(paper_equity)),
            "usdc_hold_usd":str(value),
            "absolute_gap_usd":str(d(paper_equity)-value),
            "rate_bid_usd":str(checked_rate(usdc_quote,as_of)["bid"])}
