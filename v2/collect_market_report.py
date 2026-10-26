#!/usr/bin/env python3
"""Collect and calculate a sourced Kraken V2 market report.

Runs in a network-enabled environment. Uses only Kraken public endpoints and
standard library; never submits orders or touches portfolio state.
"""
import argparse
import json
import math
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BASE = "https://api.kraken.com/0/public/"
ASSETS = {"BTC": "XBTUSDC", "ETH": "ETHUSDC", "SOL": "SOLUSDC", "XRP": "XRPUSDC"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fetch(endpoint, **params):
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params)
    stamp = utc_now()
    req = urllib.request.Request(url, headers={"User-Agent": "KrakenSimV2-Report/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        body = json.load(response)
    if body.get("error") or not body.get("result"):
        raise ValueError(f"Kraken public {endpoint} rejected: {body.get('error')}")
    return {"url": url, "fetched_at_utc": stamp, "raw": body}


def result_for(payload, *, has_last=False):
    data = payload["raw"]["result"]
    keys = [k for k in data if k != "last"]
    if len(keys) != 1:
        raise ValueError("Expected exactly one Kraken pair")
    return data[keys[0]]


def candles(payload):
    """Kraken OHLC includes a trailing unclosed candle; always exclude it."""
    rows = result_for(payload)
    if len(rows) < 52:
        raise ValueError("Insufficient completed OHLC candles for EMA50")
    return rows[:-1]


def ema(values, length):
    if len(values) < length:
        return None
    seed = sum(values[:length]) / length
    multiplier = 2 / (length + 1)
    for value in values[length:]:
        seed = (value - seed) * multiplier + seed
    return seed


def rsi(values, length=14):
    if len(values) <= length:
        return None
    diffs = [values[i] - values[i - 1] for i in range(1, len(values))]
    gain = sum(max(x, 0) for x in diffs[:length]) / length
    loss = sum(max(-x, 0) for x in diffs[:length]) / length
    for change in diffs[length:]:
        gain = (gain * (length - 1) + max(change, 0)) / length
        loss = (loss * (length - 1) + max(-change, 0)) / length
    if gain == 0 and loss == 0:
        return 50.0
    if loss == 0:
        return 100.0
    return 100 - 100 / (1 + gain / loss)


def atr(rows, length=14):
    if len(rows) <= length:
        return None
    tr = []
    for prev, row in zip(rows, rows[1:]):
        high, low, prev_close = float(row[2]), float(row[3]), float(prev[4])
        tr.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    value = sum(tr[:length]) / length
    for t in tr[length:]:
        value = (value * (length - 1) + t) / length
    return value


def indicators(rows):
    closes = [float(row[4]) for row in rows]
    if any(not math.isfinite(x) or x <= 0 for x in closes):
        raise ValueError("Invalid OHLC close")
    last30 = rows[-30:]
    return {
        "ema20": ema(closes, 20), "ema50": ema(closes, 50),
        "rsi14": rsi(closes), "atr14": atr(rows),
        "high30": max(float(x[2]) for x in last30),
        "low30": min(float(x[3]) for x in last30),
        "close": closes[-1],
        "last_closed_candle_utc": datetime.fromtimestamp(int(rows[-1][0]), timezone.utc).isoformat().replace("+00:00", "Z"),
        "closed_candles": len(rows),
    }


def liquidity(payload):
    book = result_for(payload)
    asks = [(float(p), float(q)) for p, q, *_ in book["asks"]]
    bids = [(float(p), float(q)) for p, q, *_ in book["bids"]]
    if not asks or not bids or asks[0][0] <= bids[0][0]:
        raise ValueError("Invalid Kraken order book")
    mid = (asks[0][0] + bids[0][0]) / 2
    return {
        "best_bid": bids[0][0], "best_ask": asks[0][0], "mid": mid,
        "spread_pct": (asks[0][0] - bids[0][0]) / mid * 100,
        "bid_depth_usdc_within_0_5pct": sum(p*q for p,q in bids if p >= mid*0.995),
        "ask_depth_usdc_within_0_5pct": sum(p*q for p,q in asks if p <= mid*1.005),
        "book_levels_asks": len(asks), "book_levels_bids": len(bids),
    }


def fmt(value, decimals=4):
    return "null" if value is None else f"{value:,.{decimals}f}".replace(",", " ")


def build_report(dataset, date):
    lines = [
        f"# Kraken Sim V2 — Analyse Kraken du {date}",
        "",
        "**Statut : rapport technique pour revue GrokBot, non exécutoire.**",
        f"**Collecte UTC :** {dataset['collected_at_utc']}. **Source :** API publique Kraken. **Actifs :** BTC, ETH, SOL, XRP, contre USDC.",
        "**Aucun plan stratégique, aucune clé Kraken, aucun ordre PAPER.**",
        "",
        "## 1. Marché global — faits vérifiés",
        "",
        "La tendance globale doit être interprétée à partir des données ci-dessous, sans inventer de conclusion macroéconomique.",
        "",
        "| Paire | Dernier prix Kraken USDC | Variation 24 h | Source et UTC |",
        "|---|---:|---:|---|",
    ]
    for asset, d in dataset["assets"].items():
        t = d["ticker"]
        lines.append(f"| {asset}/USDC | {fmt(t['last_price'])} | null (non calculée) | [Ticker]({d['raw']['Ticker']['url']}) · {d['raw']['Ticker']['fetched_at_utc']} |")
    lines += ["", "## 2. Actifs éligibles — indicateurs calculés sur OHLC Kraken", "",
              "Les calculs ci-dessous ne prouvent pas l'éligibilité réglementaire France/EEE. Celle-ci doit être vérifiée séparément par le contrôle V1.2.",
              "",
              "| Paire | Période | EMA20 | EMA50 | RSI14 | ATR14 (USDC) | Haut 30 bougies | Bas 30 bougies | Dernière bougie close UTC |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for asset, d in dataset["assets"].items():
        for period in ("1440", "60"):
            i = d["indicators"][period]
            lines.append(f"| {asset}/USDC | {'1 j' if period == '1440' else '1 h'} | {fmt(i['ema20'])} | {fmt(i['ema50'])} | {fmt(i['rsi14'],2)} | {fmt(i['atr14'])} | {fmt(i['high30'])} | {fmt(i['low30'])} | {i['last_closed_candle_utc']} |")
    lines += ["", "**Méthodes de calcul :**",
              "- Bougies Kraken OHLC : la dernière bougie, encore ouverte, est exclue systématiquement.",
              "- EMA20 et EMA50 : moyenne simple des 20/50 premières clôtures pour initialiser, puis EMA = clôture × 2/(N+1) + EMA précédente × (1 − 2/(N+1)).",
              "- RSI14 : variation de clôture, gains/pertes moyens initialisés sur 14 périodes puis lissage de Wilder ; RSI = 100 − 100/(1 + gains/pertes).",
              "- ATR14 : True Range = max(haut−bas, |haut−clôture précédente|, |bas−clôture précédente|), moyenne initiale de 14 TR puis lissage de Wilder.",
              "- Haut/bas 30 j : maximum des hauts et minimum des bas des 30 dernières bougies **journalières clôturées**. La colonne 1 h donne le haut/bas des 30 dernières heures, et non des 30 jours.",
              "- Toutes les périodes et valeurs brutes sont conservées dans l'annexe JSON ; aucun niveau n'est une instruction d'ordre.",
              "",
              "### Liquidité — carnet Kraken Depth, bande ±0,5 % autour du mid",
              "",
              "| Paire | Bid | Ask | Spread % | Profondeur bid USDC | Profondeur ask USDC | UTC |",
              "|---|---:|---:|---:|---:|---:|---|"]
    for asset, d in dataset["assets"].items():
        l = d["liquidity"]
        lines.append(f"| {asset}/USDC | {fmt(l['best_bid'])} | {fmt(l['best_ask'])} | {fmt(l['spread_pct'],3)} | {fmt(l['bid_depth_usdc_within_0_5pct'],2)} | {fmt(l['ask_depth_usdc_within_0_5pct'],2)} | {d['raw']['Depth']['fetched_at_utc']} |")
    lines += ["", "**Limites :** carnet instantané, profondeur en notionnel USDC (prix × quantité) ; le spread et la profondeur peuvent changer avant un ordre. Le volume médian 30 jours doit être calculé sur 30 bougies quotidiennes clôturées et validé séparément. Les frais maker/taker ne sont pas fournis par ces trois endpoints.",
              "",
              "## 3. Actualités et macro — sources primaires",
              "",
              "Aucune affirmation macro/ETF non vérifiée n'est ajoutée. Actualités primaires : null.",
              "",
              "## 4. Risques — faits et incertitudes",
              "",
              "- Le carnet est instantané ; le slippage d'un ordre futur ne peut pas être garanti.",
              "- Les indicateurs historiques ne prédisent pas les prix futurs.",
              "- Éligibilité France/EEE, minimum Kraken par paire et frais effectifs : null, à vérifier avant exécution.",
              "- Aucune donnée de portefeuille ou de capital n'est déduite des prix.",
              "",
              "## 5. Idées d'allocation — opinions non exécutoires",
              "",
              "Scénario de reprise : surveiller EMA20 > EMA50 sur 1 j et 1 h, RSI en amélioration, carnet liquide et spread faible ; arguments contraires : faux signaux, liquidité variable.",
              "",
              "Scénario défensif : surveiller EMA20 < EMA50, RSI faible, spreads élargis et profondeur réduite ; arguments contraires : rebond rapide possible.",
              "",
              "Aucun pourcentage cible, niveau d'ordre ou plan n'est créé : la décision appartient à GrokBot.",
              "",
              "## 6. Sources — endpoints et valeurs brutes",
              "",
              "Les URL exactes et horodatages UTC de chaque requête figurent ci-dessous. **Toutes les réponses brutes de Kraken**, non tronquées, sont conservées dans l'annexe JSON de même date.",
              "",
              "| Paire | Endpoint | URL exacte | UTC |",
              "|---|---|---|---|"]
    for asset, d in dataset["assets"].items():
        for key, item in d["raw"].items():
            lines.append(f"| {asset}/USDC | {key} | {item['url']} | {item['fetched_at_utc']} |")
    lines += ["", f"**Annexe brute :** `v2/reports/{date}.kraken.json` (valeurs Ticker/OHLC/Depth intégrales, horodatées).",
              "", "**Contrôle :** rapport non exécutoire ; aucun fichier `v2/plan.json`, `v2/state.json` ni garde-fou modifié.",
              ""]
    return "\n".join(lines)


def collect():
    data = {"collected_at_utc": utc_now(), "assets": {}}
    for asset, pair in ASSETS.items():
        raw = {
            "Ticker": fetch("Ticker", pair=pair),
            "OHLC_1440": fetch("OHLC", pair=pair, interval=1440),
            "OHLC_60": fetch("OHLC", pair=pair, interval=60),
            "Depth": fetch("Depth", pair=pair, count=500),
        }
        ticker = result_for(raw["Ticker"])
        data["assets"][asset] = {
            "ticker": {"last_price": float(ticker["c"][0])},
            "indicators": {
                "1440": indicators(candles(raw["OHLC_1440"])),
                "60": indicators(candles(raw["OHLC_60"])),
            },
            "liquidity": liquidity(raw["Depth"]),
            "raw": raw,
        }
    return data


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="Report date YYYY-MM-DD")
    p.add_argument("--out-dir", type=Path, default=Path(__file__).parent / "reports")
    args = p.parse_args()
    datetime.strptime(args.date, "%Y-%m-%d")
    data = collect()  # If any API call fails, neither output is created.
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(data, args.date)
    raw = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    (args.out_dir / (args.date + ".kraken.json")).write_text(raw, encoding="utf-8")
    (args.out_dir / (args.date + ".md")).write_text(report, encoding="utf-8")
    print(f"Collected Kraken public data for {args.date} at {data['collected_at_utc']}")


if __name__ == "__main__":
    main()
