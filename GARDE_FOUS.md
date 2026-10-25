# GARDE-FOUS — contrat d'interface GPT6 ↔ Kraken Bot

**Rôles** : Kraken Bot = moteur, données, règles (`VERSION_ENGINE`). GPT6 = UX/UI (`VERSION_UX` dans `dashboard_template.html`). Paper trading uniquement, aucun ordre réel.

## 1. Contrat technique du template (à ne jamais casser)
1. Une seule ligne d'injection, exactement : `const D = __DATA__;` (remplacée par `render_page.py`).
2. Exactement **deux** blocs `<script` dans le fichier.
3. Une seule ligne `const VERSION_UX = "Vx.y";` et le bandeau `#versions` affichant `Moteur : ${D.version_engine} · UX/UI : ${VERSION_UX}`.
4. Tous les ids listés ci-dessous restent présents (on peut en **ajouter** ; en supprimer = demande fonctionnelle + mise à jour de `tests/contract.json` par Kraken Bot). Tout id référencé en JS doit exister.
5. Seules les clés de `D` listées ci-dessous (ou ajoutées par Kraken Bot) sont lues ; jamais de clé inventée.
6. Sources live conservées : `STATE_URL` + `fetch(STATE_URL…)` sur `state/public_state.json`, API Kraken `Ticker` et `OHLC`.
7. Aucune donnée d'exemple codée en dur (`D = {…}`, `D = JSON.parse(…)`, lorem ipsum, « données fictives / mock »). Aucun « undefined », « NaN », « [object Object] » visible.
8. Libellés « LIVE » / « sur clôture » / « valeurs FIGÉES » conformes à `docs/SPEC_UX.md`.

## 2. Périmètre
- GPT6 modifie **uniquement** `dashboard_template.html` (+ `CHANGELOG.md`, `docs/SPEC_UX.md`). **Jamais** `cycle_v11.py`, `cycle.py`, `backtest.py`, `page_data.py`, `render_page.py`, `sim.db`, `state/`, `.github/workflows/`, `VERSION_ENGINE`, `tests/`.
- GPT6 travaille sur une branche `ux/<sujet>` et ouvre une PR vers `main` ; **jamais de push direct sur main**.
- Chaque PR UX **incrémente `VERSION_UX`** et ajoute en tête de `CHANGELOG.md` une entrée `## [UX <nouvelle version>] — date — GPT6`.
- Chaque modif moteur/données **incrémente `VERSION_ENGINE`** + entrée `## [Moteur <version>]` (Kraken Bot).
- Besoin d'une donnée ou d'une règle nouvelle → issue GitHub avec l'étiquette **`fonctionnel`** (Kraken Bot l'ajoute dans `page_data.py`, puis le contrat).

## 3. Ce que bloque `guard.yml` (PR et push sur main)
- **perimetre-ux** (PR depuis `ux/*`) : échoue si un fichier hors `dashboard_template.html`, `CHANGELOG.md`, `docs/SPEC_UX.md` est modifié.
- **versions** (toute PR) : template modifié sans changement de `VERSION_UX`, sans `CHANGELOG.md` ou sans entrée `## [UX <version>]` → échec ; fichiers moteur modifiés sans incrément de `VERSION_ENGINE` et entrée `## [Moteur <version>]` → échec.
- **contrat** (PR et push) : `tests/check_template.py` (points 1 à 7 ci-dessus, rendu réel avec `render_page.py` puis Chrome sans interface : zéro erreur JS, zéro undefined/NaN, versions affichées).

## 4. Procédure de test (avant chaque PR)
```bash
git checkout -b ux/mon-sujet
# éditer dashboard_template.html, incrémenter VERSION_UX, ajouter l'entrée CHANGELOG
python3 tests/check_template.py      # doit finir par « RÉSULTAT : contrat respecté »
SIM_NO_REMOTE=1 SIM_OUT=/tmp/prev python3 render_page.py && xdg-open /tmp/prev/dashboard.html   # vérif visuelle
git push -u origin ux/mon-sujet && gh pr create --fill
```
La PR n'est fusionnée par Cyril que si `guard` est vert.

## 5. Liste exhaustive (contrat `tests/contract.json`)
**Ids (69)** : `accountCaption`, `accountChange`, `accountChangePct`, `accountValue`, `activity`, `alloc`, `allocationVisual`, `analysis`, `bchart`, `briefCash`, `briefDd`, `briefExposure`, `briefFees`, `briefPnl`, `briefTrades`, `btcRegime`, `cmp`, `compareVisual`, `corePos`, `cycleElapsed`, `cycleNext`, `dd`, `dec`, `dot`, `drawdownVisual`, `equityChartNote`, `equityPeriods`, `equityPlot`, `equityRangeLabel`, `head`, `ind`, `inddot`, `indsrc`, `indst`, `jr`, `kill`, `lch`, `lchart`, `lessons`, `lessonsCard`, `live`, `lp`, `lst`, `market`, `metrics`, `mobileToggle`, `navToggle`, `orderCount`, `ordersVisual`, `overview`, `periodNote`, `pnl`, `portfolio`, `pos`, `rail`, `rules`, `sellConditions`, `signalBars`, `signals`, `split`, `splitNote`, `splitTable`, `stateSrc`, `strat`, `ts`, `uptime`, `ver`, `versions`, `wf`

**Clés de `D` utilisées (51)** : `C0`, `allocation`, `as_of`, `atr_mult`, `backtest`, `basket_return_pct`, `btc_regime`, `btc_regime_state`, `btc_return_pct`, `btc_series`, `cash`, `core`, `cur_dd_pct`, `curve`, `dd_series`, `decisions`, `equity`, `exposure_pct`, `fees`, `fees_tier`, `ind_btc_pair`, `ind_live`, `indicators`, `indicators_src`, `invested_pct`, `journal`, `keep_rank`, `killed`, `last_cycle_iso`, `lessons`, `max_dd_pct`, `min_hold_h`, `n_cycles`, `n_trades`, `net_return_pct`, `orders`, `pnl_by_asset`, `pnl_gross`, `pnl_net`, `positions`, `snapshot`, `start_iso`, `start_paris`, `total`, `trade_stats`, `universe`, `version`, `version_engine`, `vs_btc_pct`, `walkforward`, `win_rate_pct`
