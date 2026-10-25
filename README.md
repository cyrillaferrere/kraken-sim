> **Collaboration GPT6 (UX/UI) ↔ Kraken Bot (moteur)** — versions : **Moteur `VERSION_ENGINE`** · **Stratégie `strategy/params.json`** · **UX/UI `VERSION_UX`** (template).
> GPT6 ne modifie que `dashboard_template.html` sur une branche `ux/*` + PR (jamais de push sur main), incrémente `VERSION_UX` et ajoute une entrée au `CHANGELOG.md`. Contrat : une seule ligne `const D = __DATA__;`, 2 blocs script, ids et clés `D` du contrat, données live (state.json + API Kraken), aucune donnée d'exemple. Stratégie : Kraken Bot seul (incrément + CHANGELOG avec backtest). Demandes fonctionnelles → issue `fonctionnel`.
> Détails : [GARDE_FOUS.md](GARDE_FOUS.md) · [CHANGELOG.md](CHANGELOG.md) · [docs/SPEC_FONCTIONNELLE.md](docs/SPEC_FONCTIONNELLE.md) · [docs/SPEC_UX.md](docs/SPEC_UX.md) · test : `python3 tests/check_template.py`.

# Kraken Sim — paper trading (no real orders, public Kraken API only)
Files: cycle.py (engine), sim.db (sqlite ledger: meta, cycles, orders, positions, equity, decisions, prices), page_data.py (dashboard JSON), page_template.tsx + render_page.py (Page contents), refresh_page.md.
- Run one cycle: `python3 /workspace/kraken-sim/cycle.py` (slot = UTC YYYYMMDDHH; rerun in same slot is a no-op).
- Dashboard JSON: `python3 page_data.py`
- C0 = 6605.10 USD frozen (fallback value; connector has no real balance tool).
- Strategy: top-10 USD pairs by 24h volume (no stables, spread<=0.30%); momentum = 0.5*30d + 0.3*7d + 0.2*(42x4h) returns; hold top 3 that are above 50d and 50x4h SMA, 35% max each, else cash; 3xATR(4h) trailing stop; 24h min hold; 10% rebalance band; kill-switch at 30% DD from C0.
- Fills: buy ask*(1+0.05%), sell bid*(1-0.05%), fee 0.40%, Depth check (top 25 levels).
- Benchmarks: BTC buy-and-hold from C0 (with entry fee), cash = C0.
- Reset: delete sim.db.

## Stratégie actuelle (B, depuis le 24/10/2026)
Régime BTC > EMA50 journalière ; entrée si tendance EMA20>EMA50 et close>EMA50 (obligatoire) + ≥4/5 confirmations (tendance, MACD>signal, RSI 50–75, ADX>20 avec +DI>−DI, volume 7j>30j). Top 3 par momentum, 33 % chacun. Sortie : stop suiveur 3×ATR, close<EMA50 ou régime baissier. Backtest : `python3 backtest.py` -> backtest_results.json. Ancienne version : cycle_v1_backup.py.

## V1.01 (24/10/2026)
- cycle.py : table `indicators` (5 indicateurs + score + régime par crypto et par cycle), prix ETH toujours enregistré (panier 50/50), correctif poids cible `w` (33 %) qui n'était pas défini — logique B inchangée. Sauvegarde : cycle_v1_00_backup.py.
- page_data.py : prix BTC, panier 50/50 BTC/ETH, drawdown, brut vs frais, temps investi, P&L par crypto, stats de trades, journal en phrases, indicateurs, leçons, durée de service.
- render_page.py -> page_contents.txt + dashboard.html (template : dashboard_template.html ; BTCUSD en direct via REST Ticker/OHLC Kraken toutes les 5 s + WebSocket v2, CORS vérifié).
- lecons.md : leçons hebdomadaires.
- V1.03 (24/10/2026) : indicators + colonnes vol_ratio, macd_hist (ALTER auto dans db()) ; backtest.ind expose vr/mh (logique inchangée) ; tableau chiffré Page/HTML ; dashboard.html recalcule les 5 indicateurs en direct (OHLC 1440, bougies clôturées) toutes les 60 s, repli sur l'instantané.

## V1.04 (24/10/2026)
- Nouveau design (version GPT), état public JSON publié à chaque cycle : https://raw.githubusercontent.com/cyrillaferrere/kraken-sim-state/main/state.json (voir refresh_page.md 1b).
- Sauvegardes : dashboard_template_v1_03_final.html, page_data_v1_03_final_backup.py, render_page_v1_03_final_backup.py.
