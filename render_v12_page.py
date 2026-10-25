#!/usr/bin/env python3
"""Render the PREPROD V1.2 PAPER page from a REAL init-check report.

Reads check_report.json (written by cycle_v12.py --init-check), builds
public_state_v12.json via export_v12.normalize and renders
dashboard_v12_cockpit_template.html into <out>/index.html.
Read-only on the V1.2 state; never touches V1.1. Missing data -> null.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from export_v12 import normalize  # noqa: E402

TEMPLATE = ROOT / "dashboard_v12_cockpit_template.html"


def _f(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_state(report):
    if report.get("mode") != "INIT_CHECK_HOLD_ONLY":
        raise ValueError("unexpected report mode")
    if report.get("strategy_version") != "V1.2":
        raise ValueError("foreign strategy rejected")
    ts = report.get("generated_at")
    equity, cash = _f(report.get("equity_usd")), _f(report.get("cash_usd"))
    guards = report.get("guardrails") or {}
    peak = _f(guards.get("engine_peak_usd"))
    positions = [
        {"asset": k, "qty": _f((v or {}).get("qty")), "value": _f((v or {}).get("value_usd"))}
        for k, v in sorted((report.get("positions") or {}).items())
    ]
    signals = {}
    for key in "ABCD":
        s = (report.get("signals") or {}).get(key)
        if s is None:
            signals[key] = None
            continue
        ent = s.get("entries") or []
        txt = f"{s.get('evaluated', '—')} évaluées · {len(ent)} entrée{'s' if len(ent) > 1 else ''}"
        signals[key] = txt + (" : " + ", ".join(ent) if ent else "")
    decisions = []
    for dec in report.get("decisions") or []:
        reason = dec.get("reason") or ""
        action = "HOLD" if "HOLD" in reason or "hold" in str(dec.get("decision_id", "")) else None
        decisions.append({"action": action, "asset": "Portefeuille", "created_at": ts,
                          "reason": f"{reason} · {dec.get('decision_id')} · acceptée={dec.get('accepted')}",
                          "decision_id": dec.get("decision_id"), "accepted": dec.get("accepted")})
    bench = report.get("benchmark") or {}
    data = report.get("data") or {}
    raw = {
        "equity": equity, "cash": cash, "C0": _f(report.get("initial_capital_usd")),
        "positions": positions, "orders": [], "pending_orders": [],
        "pending_count": report.get("orders"),
        "decisions": decisions, "as_of": ts, "last_cycle_iso": ts,
        "usdc_hold_usd": _f(bench.get("usdc_hold_usd")),
        "btc_hold_usd": _f(bench.get("btc_hold_usd")),
        "cur_dd_pct": (peak - equity) / peak * 100 if peak and equity is not None else None,
        "fees_paid_usd": None,
        "risk": {"risk_lock": guards.get("risk_lock"), "paused": None,
                 "kill_count": guards.get("kill_count")},
        "candidate_signals": signals,
        "grok": {"status": "Décision HOLD (init-check moteur, pas une IT Grok)",
                 "last_action": "HOLD — 0 ordre, 0 exécution, 0 trade"},
        "init_check": {
            "mode": report.get("mode"), "decisions": decisions,
            "orders": report.get("orders"), "fills": report.get("fills"),
            "trades": report.get("trades"), "api_keys_used": report.get("api_keys_used"),
            "pairs_quoted": data.get("pairs_quoted"), "pairs_valid": data.get("pairs_valid"),
            "usdc_usd": data.get("usdc_usd"), "excluded_pairs": report.get("excluded_pairs"),
            "guardrails": guards, "tick": report.get("tick"),
            "synthesis_sha256": report.get("synthesis_sha256"),
            "engine_version_report": report.get("engine_version"),
        },
    }
    return normalize(raw)


def render(state, template=TEMPLATE, state_url="public_state_v12.json"):
    html = Path(template).read_text(encoding="utf-8")
    payload = json.dumps(state, ensure_ascii=False, allow_nan=False).replace("</", "<\\/")
    if "__DATA__" not in html or "__STATE_SOURCE__" not in html:
        raise ValueError("template placeholders missing")
    return html.replace("__DATA__", payload, 1).replace("__STATE_SOURCE__", state_url, 1)


def main(argv=None):
    p = argparse.ArgumentParser(description="Rendu page PREPROD V1.2 PAPER")
    p.add_argument("--report", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    state = build_state(json.loads(Path(a.report).read_text(encoding="utf-8")))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "public_state_v12.json").write_text(
        json.dumps(state, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
    (out / "index.html").write_text(render(state), encoding="utf-8")
    print(f"V1.2 page: equity={state['equity']} orders={len(state['orders'])} -> {out}")


if __name__ == "__main__":
    main()
