#!/usr/bin/env python3
"""Pure post-OOS acceptance gate from Grok Bot's frozen SPEC, section 5.
Never select from exploratory in-sample runs. Missing metrics => REJECT.
"""
from math import isfinite

REQUIRED = (
    "net_oos_f2", "net_oos_f1", "v11_net_oos_f2",
    "max_drawdown_oos_f2", "fold_returns_oos_f2",
    "fees_spread_slippage_usd_f2", "gross_profit_usd_f2",
    "neighbors_oos_f2", "closed_roundtrips_oos",
    "calmar_oos_f2", "sortino_oos_f2",
)

def _valid_number(v):
    return isinstance(v, (float, int)) and not isinstance(v, bool) and isfinite(v)

def reject_candidate(result):
    """Return (rejected, reasons) from pre-registered SPEC criteria.
    max_drawdown_oos_f2 is signed, e.g. -0.34. Returns in fractions, not percent.
    """
    if result.get("evaluation_status") != "VALIDATED_WALK_FORWARD":
        return True, ["NOT_VALIDATED_WALK_FORWARD"]
    missing = [k for k in REQUIRED if k not in result or result[k] is None]
    if missing:
        return True, ["MISSING_METRICS: " + ", ".join(missing)]
    for k in REQUIRED:
        if k in ("fold_returns_oos_f2", "neighbors_oos_f2"):
            if not isinstance(result[k], list) or not result[k] or not all(_valid_number(x) for x in result[k]):
                return True, ["INVALID_METRIC: " + k]
        elif not _valid_number(result[k]):
            return True, ["INVALID_METRIC: " + k]
    fail = []
    net, net_f1 = result["net_oos_f2"], result["net_oos_f1"]
    if net <= 0 or net <= result["v11_net_oos_f2"]:
        fail.append("NO_OOS_ADVANTAGE")
    if result["max_drawdown_oos_f2"] < -0.35:
        fail.append("EXCESSIVE_OOS_DRAWDOWN")
    folds = result["fold_returns_oos_f2"]
    if sum(x > 0 for x in folds) / len(folds) <= 0.5:
        fail.append("INSUFFICIENT_POSITIVE_FOLDS")
    gross = result["gross_profit_usd_f2"]
    if gross <= 0 or result["fees_spread_slippage_usd_f2"] > 0.4 * gross:
        fail.append("EXCESSIVE_COST_TO_GROSS_PROFIT")
    if any(x < 0 for x in result["neighbors_oos_f2"]) and net > 0:
        fail.append("SENSITIVITY_SIGN_FLIP")
    if result["closed_roundtrips_oos"] < 30:
        fail.append("INSUFFICIENT_CLOSED_TRADES")
    if net_f1 <= 0:
        fail.append("NON_POSITIVE_F1")
    return bool(fail), fail

def choose_candidate(candidates):
    """Return best *validated survivor* by Calmar then Sortino, or no deployment."""
    valid = [(name, d) for name, d in candidates.items() if not reject_candidate(d)[0]]
    if not valid:
        return None
    return max(valid, key=lambda it: (it[1]["calmar_oos_f2"], it[1]["sortino_oos_f2"], it[0]))[0]
