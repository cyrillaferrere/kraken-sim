# Spécification fonctionnelle — Moteur V1.1 (paper trading, aucun ordre réel)

Version moteur : fichier `VERSION_ENGINE` (actuellement **V1.1**). Propriétaire : **Kraken Bot**. Version stratégie : `STRATEGY_VERSION` dans `strategy/params.json` (actuellement **V1.1**), source unique des paramètres ci-dessous, lue par `cycle_v11.py`.
- Moteur (code, infra, données) → incrément `VERSION_ENGINE` + `## [Moteur Vx.y]`.
- Stratégie (règles, paramètres) → incrément `STRATEGY_VERSION` + `## [Stratégie Vx.y]` avec paramètres avant/après, justification et backtest.
- Chaque ordre, décision et cycle enregistre `strategy_version` (comparaison des performances : `perf_by_strategy`).

## 1. Règles V1.1 (`cycle_v11.py`)
| Paramètre | Valeur |
|---|---|
| Capital initial C0 | 6 605,10 $ (cash simulé) |
| Emplacements / poids cible | 3 × 33 % du total (`TOP_N`, `W`) |
| Stop suiveur | 3 × ATR14 sous le plus haut depuis l'entrée, intraday, taker |
| Coupe-circuit | total ≤ C0 × (1 − 30 %) → tout vendre taker, arrêt |
| Spread max / ordre min / glissement | 0,3 % / 25 $ / 0,05 % (taker) |
| Hystérésis régime | k = 0,15 |
| Tampon de rang / détention min / challenger | 4 / 48 h / +10 pts de momentum |
| Pas d'achat | dans les 60 min avant 00:00 UTC |
| Sortie B maker → taker | après 3 cycles non remplis |

**Frais** (palier selon le volume 30 j, maker / taker) : ≥50 k$ 0,15/0,30 % · ≥25 k$ 0,20/0,35 % · ≥10 k$ 0,22/0,38 % · ≥2,5 k$ 0,30/0,60 % · sinon 0,40/0,80 %.

**Univers** : paires Kraken `country_code=FR` (repli : exclure XMR), cotées USD, hors stablecoins, spread ≤ 0,3 %, top 10 par volume 24 h.

**Régime BTC (3 états, sur clôture quotidienne)** : `on` si clôture > EMA50 + 0,15×ATR14 ; `off` si clôture < EMA50 − 0,15×ATR14 ; sinon `neutral` (aucun achat, pas de vente forcée).

**Signal d'entrée** : tendance (clôture > EMA50 et EMA20 > EMA50) + ≥ 4/5 confirmations : tendance, MACD > signal, RSI 50–75, ADX > 20 avec +DI > −DI, volume 7 j > 30 j. Classement momentum = ½ perf 30 j + ½ perf 7 j.

**Sorties (ordre de priorité)** :
1. Régime `off` → vente immédiate taker de tout.
2. Stop 3×ATR touché (intraday) → taker.
3. Sortie B : clôture < EMA50 → vente post-only, taker après 3 cycles. Différée 48 h après l'achat pour le socle, 24 h pour une position test.
4. Rotation C : rang > 4 **et** détenue ≥ 48 h **et** challenger avec momentum supérieur de +10 pts.

**Entrées** : uniquement régime `on`, achat post-only au bid, taille W × total. Une position < ½·W n'occupe pas d'emplacement (renforçable).

**Remplissage post-only (prudent)** : rempli seulement si des trades publics postérieurs croisent strictement la limite, pour un volume ≥ quantité.

**Socle de départ** : 500 $ BTC, 300 $ ETH, 200 $ XRP achetés une fois, puis positions normales (vendables). Référence « socle conservé » dans la table `core`.

## 2. Ordonnancement
- Cron GitHub `10 * * * *` (UTC), filtré par `PARIS_HOURS="01 04 08 10 12 14 16 18 20 22"` (heures de Paris).
- **Décision quotidienne** : premier cycle après 00:00 UTC (01h10 Paris), sur bougies clôturées, une seule fois par jour UTC (`snapshot.day`).
- **Cycles intraday** : stops, coupe-circuit, suivi des ordres maker, valorisation. Créneau = heure UTC, idempotent.
- `workflow_dispatch` : `mode=cycle` (cycle complet) ou `mode=render` (régénère la page sans trader). Concurrence `kraken-sim`.

## 3. Pipeline
`cycle_v11.py` (lit Kraken public, écrit `sim.db`) → `page_data.py` (agrège `sim.db` en JSON) → `render_page.py` (injecte dans `dashboard_template.html` → `dashboard.html` + `index.html`, écrit `state/state.json` + `state/public_state.json`, `page_contents.txt`) → commit par le workflow → GitHub Pages. Le navigateur relit `state/public_state.json` (60 s) et l'API Kraken (5–60 s).

## 4. Schéma `state.json` (champ par champ)
| Champ | Description |
|---|---|
| `version` | version enregistrée dans le cycle (ex. V1.1) |
| `strategy_version`, `strategy_params` | version et paramètres de stratégie (`strategy/params.json`) |
| `perf_by_strategy[]` | `{strategy_version, n_orders, fees, pnl_realized, first, last}` |
| `version_engine` | contenu de `VERSION_ENGINE` (affiché « Moteur : … ») |
| `C0`, `start`, `start_iso`, `start_paris`, `uptime` | capital initial, début de la sim, durée |
| `as_of`, `slot`, `last_cycle_iso`, `rendered`, `n_cycles` | horodatages du dernier cycle / rendu, nombre de cycles |
| `killed` | coupe-circuit déclenché (bool) |
| `equity`, `cash`, `total` | valeur des positions + cash ; `total` = objet de synthèse du portefeuille |
| `exposure_pct`, `invested_pct`, `cycles_invested` | exposition |
| `net_return_pct`, `pnl_net`, `pnl_gross`, `fees`, `fees_tier{vol30,maker,taker}` | performance et frais, palier courant |
| `btc_hold`, `btc_return_pct`, `vs_btc_pct`, `vs_cash_pct`, `btc_series`, `btc_last` | comparaison BTC acheté-conservé |
| `basket`, `basket_return_pct` | panier BTC/ETH 50/50 |
| `max_dd_pct`, `cur_dd_pct`, `dd_series` | drawdown |
| `n_trades`, `n_closed`, `win_rate_pct`, `trade_stats`, `pnl_by_asset` | statistiques |
| `curve[]` | `{t, iso, sim, btc, cash, core, strat, basket, exp}` par cycle |
| `positions[]` | `{asset, pair, qty, avg, price, value, pnl_pct, stop, high, entry_iso, held_h, test, origin, close, ema50}` |
| `orders`, `orders_full`, `pending` | ordres exécutés / ordres maker en attente |
| `allocation`, `decisions`, `decision_cycles`, `journal` | répartition, décisions, journal |
| `core{C0,cost,fees,value,pnl,pnl_pct,positions,bench,bench_pct,vs_bench,start}` | socle de départ conservé (référence) |
| `universe` | univers du jour |
| `indicators`, `indicators_src`, `ind_live`, `ind_btc_pair` | indicateurs sur clôture |
| `btc_regime`, `btc_regime_state` | régime BTC (état moteur on/neutral/off) |
| `snapshot{day,ts,candle,state,btc_close,btc_e50,band,universe,universe_src,rank,cands,entries,exits,params}` | décision quotidienne |
| `min_hold_h`, `atr_mult`, `keep_rank`, `schedule` | paramètres exposés |
| `ablation` | résultats de l'ablation V1.1 |

`walkforward`, `backtest`, `lessons`, `C0_source` : seulement dans `D` (page), pas dans `state.json`.

## Historique par cycle (replay, Moteur V1.2)
À la fin de chaque cycle réussi, le moteur ajoute un instantané en lecture seule dans `state/history/AAAA-MM.json` et met à jour `state/history/index.json` (schema_version 1). L'instantané contient le portefeuille, les positions, le régime BTC, les indicateurs, les décisions, les ordres et la liste `missing` des données absentes. Les cycles passés sont rattrapés en `complete:false` (portefeuille, décisions et ordres seulement). Un échec de l'export n'interrompt jamais le cycle. Schéma détaillé : `docs/HISTORY_SCHEMA.md`.
