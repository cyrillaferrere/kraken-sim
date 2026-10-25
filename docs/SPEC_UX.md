# Spécification UX — Dashboard (UX/UI V1.1.1)

Fichier unique : `dashboard_template.html`. Version : `const VERSION_UX = "V1.1.1";`. Propriétaire : **GPT6** (PR `ux/*` vers `develop`, fusionnées par GPT6 dès guard vert ; jamais sur `main`). Contrat d'interface : `GARDE_FOUS.md`.

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

## 2b. Préproduction
- URL : https://cyrillaferrere.github.io/kraken-sim-preprod/ — publiée à chaque push sur `develop` par `preprod.yml`.
- Rendu par `render_preprod.py` : template de `develop` + `state/public_state.json` **public de prod** (lecture seule) ; backtests et leçons depuis les fichiers statiques du dépôt.
- À la publication seulement : bandeau rouge permanent « PRÉPRODUCTION — NE PAS CONFONDRE AVEC LA SIMULATION OFFICIELLE », titre préfixé [PRÉPROD], `STATE_URL` réécrit vers le state de prod (raw GitHub). Le JS live lit donc le state de prod et les prix Kraken, comme en prod. Le template n'est pas modifié : le bandeau n'apparaît jamais en prod.

## 3. Responsive, thème, langue
- Points de rupture CSS : 1150 / 850 / 600 px ; `prefers-reduced-motion` respecté ; tableaux défilables horizontalement sur mobile.
- Thème sombre uniquement.
- Français partout ; montants en `$` (format fr : `6 605,10 $`), pourcentages signés, heures en Europe/Paris.

## 4. Ids et clés `D` (contrat, voir `tests/contract.json`)
**Ids (69)** : `accountCaption`, `accountChange`, `accountChangePct`, `accountValue`, `activity`, `alloc`, `allocationVisual`, `analysis`, `bchart`, `briefCash`, `briefDd`, `briefExposure`, `briefFees`, `briefPnl`, `briefTrades`, `btcRegime`, `cmp`, `compareVisual`, `corePos`, `cycleElapsed`, `cycleNext`, `dd`, `dec`, `dot`, `drawdownVisual`, `equityChartNote`, `equityPeriods`, `equityPlot`, `equityRangeLabel`, `head`, `ind`, `inddot`, `indsrc`, `indst`, `jr`, `kill`, `lch`, `lchart`, `lessons`, `lessonsCard`, `live`, `lp`, `lst`, `market`, `metrics`, `mobileToggle`, `navToggle`, `orderCount`, `ordersVisual`, `overview`, `periodNote`, `pnl`, `portfolio`, `pos`, `rail`, `rules`, `sellConditions`, `signalBars`, `signals`, `split`, `splitNote`, `splitTable`, `stateSrc`, `strat`, `ts`, `uptime`, `ver`, `versions`, `wf`

**Clés de `D` utilisées (51)** : `C0`, `allocation`, `as_of`, `atr_mult`, `backtest`, `basket_return_pct`, `btc_regime`, `btc_regime_state`, `btc_return_pct`, `btc_series`, `cash`, `core`, `cur_dd_pct`, `curve`, `dd_series`, `decisions`, `equity`, `exposure_pct`, `fees`, `fees_tier`, `ind_btc_pair`, `ind_live`, `indicators`, `indicators_src`, `invested_pct`, `journal`, `keep_rank`, `killed`, `last_cycle_iso`, `lessons`, `max_dd_pct`, `min_hold_h`, `n_cycles`, `n_trades`, `net_return_pct`, `orders`, `pnl_by_asset`, `pnl_gross`, `pnl_net`, `positions`, `snapshot`, `start_iso`, `start_paris`, `total`, `trade_stats`, `universe`, `version`, `version_engine`, `vs_btc_pct`, `walkforward`, `win_rate_pct`


## 5. UX V1.1.1 — cockpit et replay en consultation
- Le solde et la variation nette gardent leur priorité ; les périodes incomplètes restent signalées. La comparaison au socle est accessible sur demande.
- Le panneau `#uxExplainer` reformule le régime BTC **du dernier cycle** depuis `D.btc_regime_state`, comme information **sur clôture**, sans créer de nouveau signal.
- Le journal `#ordersVisual` propose recherche libre `#uxOrderSearch` et filtre achat/vente/autres `#uxOrderFilter`. Aucun ordre n'est modifié.
- Typographie agrandie, écrans étroits améliorés, détails techniques préservés ; tous les identifiants contractuels sont maintenus.
- Le bloc `#replay` charge à la demande le **schéma 1** de `docs/HISTORY_SCHEMA.md` : index puis fichier JSON mensuel public sélectionné.
- Source historique : `https://raw.githubusercontent.com/cyrillaferrere/kraken-sim/main/state/history/` (production officielle, lecture seule). Aucun moteur, cycle, calcul d'ordre ou écriture n'est déclenché.
- La lecture d'un cycle passé est délimitée dans un panneau nommé **REPLAY**, qui n'affiche **pas de prix LIVE historique**. Le reste de la page continue de montrer l'état courant. `Retour au direct` ferme le détail historique et remonte à la vue d'ensemble.
- Les cycles incomplets (`complete:false`), les champs absents (`missing`) et les historiques non encore publiés sont explicitement signalés : « Donnée non enregistrée », jamais des valeurs inventées.
- Impact sur les décisions de trading, les stops, le capital et l'état moteur : **aucun**.
