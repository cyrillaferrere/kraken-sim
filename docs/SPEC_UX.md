# Spécification UX — Dashboard (UX/UI V1.1)

Fichier unique : `dashboard_template.html`. Version : `const VERSION_UX = "V1.1";`. Propriétaire : **GPT6** (PR `ux/*`). Contrat d'interface : `GARDE_FOUS.md`.

## 1. Structure
- **En-tête** (`app-top`) : marque, statut, bandeau `#versions` « Moteur : Vx · Stratégie : Vy · UX/UI : Vz » (obligatoire), heures de cycle / live.
- **Rail de navigation** (mobile : `#mobileToggle`).
- Sections (ancres) : `#split` (portefeuille vs socle conservé), `#market` (vue marché, BTC live, total), `#portfolio` (positions, socle de départ, allocation), `#activity` (ordres, ordres en attente, journal), `#signals` (régime BTC, indicateurs, conditions de vente), `#analysis` (performance, drawdown, frais, ablation, walk-forward).

## 2. Live vs sur clôture
| Donnée | Nature | Rafraîchissement |
|---|---|---|
| Prix BTC/USD (ticker) | LIVE Kraken | 5 s |
| Valorisation positions, P&L, total, exposition, socle, distance aux stops | LIVE (bid Kraken) | 20 s |
| État du moteur (`state/public_state.json`) | dernier cycle | 60 s |
| Indicateurs BTC recalculés (OHLC 1440, bougies clôturées) | sur clôture + prix live indicatif | 60 s |
| Indicateurs de sortie des positions | sur clôture | 300 s |
| Régime BTC, signaux, rang, décisions | **sur clôture** (décision 01h10 Paris) | au cycle |
| Ordres, journal, courbes, statistiques | figés au cycle | au cycle |

Règles : chaque bloc live affiche « LIVE : prix Kraken (bid) à HH:MM:SS » ; si l'API échoue → « valeurs FIGÉES du cycle du … ». Jamais de valeur figée présentée comme live. Les indicateurs quotidiens portent la mention « sur clôture ».

## 3. Responsive, thème, langue
- Points de rupture CSS : 1150 / 850 / 600 px ; `prefers-reduced-motion` respecté ; tableaux défilables horizontalement sur mobile.
- Thème sombre uniquement.
- Français partout ; montants en `$` (format fr : `6 605,10 $`), pourcentages signés, heures en Europe/Paris.

## 4. Ids et clés `D` (contrat, voir `tests/contract.json`)
**Ids (69)** : `accountCaption`, `accountChange`, `accountChangePct`, `accountValue`, `activity`, `alloc`, `allocationVisual`, `analysis`, `bchart`, `briefCash`, `briefDd`, `briefExposure`, `briefFees`, `briefPnl`, `briefTrades`, `btcRegime`, `cmp`, `compareVisual`, `corePos`, `cycleElapsed`, `cycleNext`, `dd`, `dec`, `dot`, `drawdownVisual`, `equityChartNote`, `equityPeriods`, `equityPlot`, `equityRangeLabel`, `head`, `ind`, `inddot`, `indsrc`, `indst`, `jr`, `kill`, `lch`, `lchart`, `lessons`, `lessonsCard`, `live`, `lp`, `lst`, `market`, `metrics`, `mobileToggle`, `navToggle`, `orderCount`, `ordersVisual`, `overview`, `periodNote`, `pnl`, `portfolio`, `pos`, `rail`, `rules`, `sellConditions`, `signalBars`, `signals`, `split`, `splitNote`, `splitTable`, `stateSrc`, `strat`, `ts`, `uptime`, `ver`, `versions`, `wf`

**Clés de `D` utilisées (51)** : `C0`, `allocation`, `as_of`, `atr_mult`, `backtest`, `basket_return_pct`, `btc_regime`, `btc_regime_state`, `btc_return_pct`, `btc_series`, `cash`, `core`, `cur_dd_pct`, `curve`, `dd_series`, `decisions`, `equity`, `exposure_pct`, `fees`, `fees_tier`, `ind_btc_pair`, `ind_live`, `indicators`, `indicators_src`, `invested_pct`, `journal`, `keep_rank`, `killed`, `last_cycle_iso`, `lessons`, `max_dd_pct`, `min_hold_h`, `n_cycles`, `n_trades`, `net_return_pct`, `orders`, `pnl_by_asset`, `pnl_gross`, `pnl_net`, `positions`, `snapshot`, `start_iso`, `start_paris`, `total`, `trade_stats`, `universe`, `version`, `version_engine`, `vs_btc_pct`, `walkforward`, `win_rate_pct`
