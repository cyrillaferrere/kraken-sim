"""Strict V2 GrokBot strategic plan validation. PAPER only; no trading API."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation

ALLOWED_ASSETS = frozenset({"BTC", "ETH", "BNB", "XRP", "SOL"})
MAX_PLAN_AGE = timedelta(hours=36)
MAX_ASSET_PCT = Decimal("40")
MAX_INVESTED_USDC = Decimal("2000")
REFERENCE_CAPITAL_USDC = Decimal("6605.10")
MAX_DRAWDOWN_PCT = Decimal("15")
MIN_DEPTH_MULTIPLE = Decimal("3")
DEPTH_BAND_PCT = Decimal("0.5")
MAX_SPREAD_PCT = Decimal("0.3")


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


def utc(v, field):
    if not isinstance(v, str) or not v.endswith("Z"):
        raise InvalidPlan(f"{field}: UTC ISO-8601 timestamp required")
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        raise InvalidPlan(f"{field}: invalid timestamp") from None


def validate_plan(plan, now=None):
    if not isinstance(plan, dict):
        raise InvalidPlan("Plan must be a JSON object")
    now = now or datetime.now(timezone.utc)
    if not isinstance(plan.get("plan_id"), str) or not plan["plan_id"].strip() or len(plan["plan_id"]) > 128:
        raise InvalidPlan("plan_id required")
    created, expires = utc(plan.get("created_at"), "created_at"), utc(plan.get("expires_at"), "expires_at")
    if created > now:
        raise InvalidPlan("Plan created in the future")
    if expires <= created or expires - created > MAX_PLAN_AGE:
        raise InvalidPlan("Plan lifetime must be at most 36 hours")
    targets = plan.get("targets")
    if not isinstance(targets, dict) or not targets:
        raise InvalidPlan("targets must be nonempty")
    if any(a not in ALLOWED_ASSETS and a != "USDC" for a in targets):
        raise InvalidPlan("Unsupported asset or quote currency")
    weights = {a: dec(v, f"targets.{a}", max_value=Decimal("100") if a == "USDC" else MAX_ASSET_PCT)
               for a, v in targets.items()}
    if sum(weights.values()) > 100:
        raise InvalidPlan("Target allocation exceeds 100%")
    floor = dec(plan.get("usdc_floor_pct"), "usdc_floor_pct", max_value=Decimal("100"))
    if 100 - sum(v for a, v in weights.items() if a != "USDC") < floor:
        raise InvalidPlan("Targets violate USDC floor")
    zones = {}
    for name in ("buy_zones", "sell_zones"):
        raw = plan.get(name)
        if not isinstance(raw, dict):
            raise InvalidPlan(f"{name} must be an object")
        if any(a not in ALLOWED_ASSETS for a in raw):
            raise InvalidPlan(f"{name}: unsupported asset")
        zones[name] = {}
        for a, pair in raw.items():
            if not isinstance(pair, list) or len(pair) != 2:
                raise InvalidPlan(f"{name}.{a}: [low, high] required")
            low, high = (dec(v, f"{name}.{a}", min_value=Decimal("0.000000000000000001")) for v in pair)
            if low > high:
                raise InvalidPlan(f"{name}.{a}: inverted zone")
            zones[name][a] = (low, high)
    stops = plan.get("stop_loss_pct")
    if not isinstance(stops, dict) or any(a not in ALLOWED_ASSETS for a in stops):
        raise InvalidPlan("stop_loss_pct: object with supported assets required")
    stops = {a: dec(v, f"stop_loss_pct.{a}", max_value=Decimal("100")) for a, v in stops.items()}
    if not isinstance(plan.get("rationale"), str) or not plan["rationale"].strip():
        raise InvalidPlan("Nonempty rationale required")
    return {"plan_id": plan["plan_id"], "created_at": created, "expires_at": expires,
            "expired": now >= expires, "targets": weights, "usdc_floor_pct": floor,
            "buy_zones": zones["buy_zones"], "sell_zones": zones["sell_zones"],
            "stop_loss_pct": stops, "rationale": plan["rationale"]}


def accept_or_keep(candidate, previous, now=None):
    """Invalid plan never displaces the last validated plan."""
    try:
        return validate_plan(candidate, now)
    except InvalidPlan:
        return previous
