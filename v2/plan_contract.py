"""Kraken Sim V2 plan contract, fractions of the 2000 USDC envelope (not percentages)."""
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALLOWED_ASSETS = frozenset({"BTC", "ETH", "BNB", "XRP", "SOL"})
MAX_PLAN_AGE = timedelta(hours=36)


class InvalidPlan(ValueError):
    pass


def dec(v, field, *, min_value=Decimal("0"), max_value=None):
    if isinstance(v, bool) or not isinstance(v, (int, float, str, Decimal)):
        raise InvalidPlan(f"{field}: invalid number")
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise InvalidPlan(f"{field}: invalid number") from None
    if not d.is_finite() or d < min_value or (max_value is not None and d > max_value):
        raise InvalidPlan(f"{field}: outside permitted range")
    return d


def guardrails(path=None):
    raw = json.loads(Path(path or ROOT / "guardrails.json").read_text(encoding="utf-8"))
    keys = ("reference_capital_usdc", "max_invested_usdc", "max_asset_fraction",
            "kill_drawdown_usdc", "max_spread_pct", "min_depth_multiple", "min_order_usdc")
    result = {k: dec(raw[k], k) for k in keys}
    for k in ("max_orders_per_cycle", "max_orders_24h", "max_market_age_seconds", "max_clock_skew_seconds"):
        if type(raw.get(k)) is not int or raw[k] <= 0:
            raise InvalidPlan(f"Invalid guardrail {k}")
        result[k] = raw[k]
    if raw.get("schema") != "v2-guardrails-1":
        raise InvalidPlan("Unknown guardrail schema")
    return result


def utc(v, field):
    if not isinstance(v, str) or not v.endswith("Z"):
        raise InvalidPlan(f"{field}: UTC ISO-8601 timestamp required")
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        raise InvalidPlan(f"{field}: invalid timestamp") from None


def validate_plan(plan, now=None, limits=None):
    limits = limits or guardrails()
    if not isinstance(plan, dict):
        raise InvalidPlan("Plan must be a JSON object")
    now = now or datetime.now(timezone.utc)
    if not isinstance(plan.get("plan_id"), str) or not plan["plan_id"].strip() or len(plan["plan_id"]) > 128:
        raise InvalidPlan("plan_id required")
    if plan.get("author") != "kraken-bot-crypto":
        raise InvalidPlan("Only Kraken Bot Crypto can author a plan")
    created, expires = utc(plan.get("created_at"), "created_at"), utc(plan.get("expires_at"), "expires_at")
    if created > now or expires <= created or expires - created > MAX_PLAN_AGE:
        raise InvalidPlan("Invalid plan lifetime")
    if plan.get("regime") not in ("risk_on", "neutral", "risk_off", "cash"):
        raise InvalidPlan("Invalid regime")
    targets = plan.get("targets")
    if not isinstance(targets, dict) or "USDC" not in targets:
        raise InvalidPlan("targets must include USDC")
    if any(a not in ALLOWED_ASSETS and a != "USDC" for a in targets):
        raise InvalidPlan("Unsupported asset")
    weights = {a: dec(v, f"targets.{a}", max_value=Decimal("1") if a == "USDC" else limits["max_asset_fraction"]) for a, v in targets.items()}
    if abs(sum(weights.values()) - Decimal("1")) > Decimal("0.001"):
        raise InvalidPlan("Target fractions must sum to 1 ± 0.001")
    if plan["regime"] == "cash" and (weights["USDC"] != 1 or len([a for a in weights if a != "USDC" and weights[a] > 0])):
        raise InvalidPlan("Cash regime must allocate 100% USDC")
    zones = {}
    for name in ("buy_zones", "sell_zones"):
        raw = plan.get(name, {})
        if not isinstance(raw, dict) or any(a not in ALLOWED_ASSETS for a in raw):
            raise InvalidPlan(f"{name}: invalid object")
        zones[name] = {}
        for a, pair in raw.items():
            if not isinstance(pair, list) or len(pair) != 2:
                raise InvalidPlan(f"{name}.{a}: [low, high] required")
            low, high = (dec(v, f"{name}.{a}", min_value=Decimal("0.000000000000000001")) for v in pair)
            if low > high:
                raise InvalidPlan(f"{name}.{a}: inverted zone")
            zones[name][a] = (low, high)
    pct = {}
    for name in ("stop_loss_pct", "take_profit_pct"):
        raw = plan.get(name, {})
        if not isinstance(raw, dict) or any(a not in ALLOWED_ASSETS for a in raw):
            raise InvalidPlan(f"{name}: invalid object")
        pct[name] = {a: dec(v, f"{name}.{a}", max_value=Decimal("1")) for a, v in raw.items()}
    execution = plan.get("execution", {"style": "taker", "maker_timeout_min": 30})
    if not isinstance(execution, dict) or execution.get("style") not in ("taker", "maker_first"):
        raise InvalidPlan("Invalid execution")
    timeout = execution.get("maker_timeout_min")
    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise InvalidPlan("Invalid maker timeout")
    max_orders = plan.get("max_orders_per_cycle", limits["max_orders_per_cycle"])
    if type(max_orders) is not int or not 1 <= max_orders <= limits["max_orders_per_cycle"]:
        raise InvalidPlan("Invalid order limit")
    if type(plan.get("ack_kill_switch", False)) is not bool:
        raise InvalidPlan("Invalid kill-switch acknowledgement")
    if not isinstance(plan.get("rationale"), str) or not plan["rationale"].strip():
        raise InvalidPlan("Rationale required")
    return {"plan_id": plan["plan_id"], "author": plan["author"], "regime": plan["regime"],
            "created_at": created, "expires_at": expires, "expired": now >= expires,
            "targets": weights, "buy_zones": zones["buy_zones"], "sell_zones": zones["sell_zones"],
            "stop_loss_pct": pct["stop_loss_pct"], "take_profit_pct": pct["take_profit_pct"],
            "execution": execution, "max_orders_per_cycle": max_orders,
            "ack_kill_switch": plan.get("ack_kill_switch", False), "rationale": plan["rationale"]}


def accept_or_keep(candidate, previous, now=None):
    try:
        return validate_plan(candidate, now)
    except InvalidPlan:
        return previous
