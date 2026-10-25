# GARDE-FOUS — contrat d'interface GPT6 ↔ Kraken Bot

**Rôles** : Kraken Bot supervise la stratégie et la revue technique ; GPT-6 gère l'UX, et exceptionnellement l'implémentation de la V1.2 sur `strategy/v1.2`. `VERSION_ENGINE` reste partagé avec la V1.1 et ne doit pas changer dans la PR V1.2 ; `VERSION_ENGINE_V12` versionne séparément le moteur expérimental. Paper trading uniquement, aucun ordre réel.

## Circuit de livraison (préprod → prod)
1. Branches `ux/*`, `feature/*`, `fix/*` créées **depuis `develop`** → PR vers `develop` (guard doit être vert).
2. **GPT-6 fusionne lui-même** ses PR `ux/*`, `feature/*`, `fix/*` vers `develop` dès que guard est vert, sans attendre la revue de Kraken Bot, **à condition** qu'elles ne touchent ni le moteur (`cycle_v11.py`, `cycle.py`, `backtest*.py`, `page_data.py`, `render_page.py`, `run_cycle_v11.sh`, `VERSION_ENGINE`), ni la stratégie (`strategy/*`, `params.json`), ni `.github/workflows/sim.yml`, ni `state/`, ni `sim.db` (contrôle `perimetre-gpt6` de guard).
3. Toute proposition moteur ou stratégie de GPT-6 passe par la **revue technique de Kraken Bot** avant d'atteindre `develop`.
4. Chaque push sur `develop` publie automatiquement la **préprod** : https://cyrillaferrere.github.io/kraken-sim-preprod/ (template de develop + state public de prod en lecture seule, bandeau PRÉPRODUCTION, aucun cycle).
5. **GPT-6 ne pousse ni ne fusionne jamais sur `main`.** PR `develop` → `main` fusionnée **par Cyril seulement** après guard vert + deux commentaires « OK prod » : GPT-6 (UX/fonctionnel) et Kraken Bot (technique). La **revue technique de Kraken Bot se fait à cette étape** (relecture de tout ce que develop apporte). Ces avis ne remplacent ni guard ni la décision de Cyril.
6. `strategy/*` reste réservé à Kraken Bot **sauf délégation expresse sur strategy/v1.2 à GPT-6** : moteur V1.2 en préprod séparée après revue technique et décision de Cyril. `sim.yml` reste V1.1 exclusivement ; le nouveau sim_v12.yml est manuel et demeure désactivé sur main jusqu'à validation de Cyril.
7. Retour arrière = `git revert` du commit de code sur `main` ; l'état de la simulation (`sim.db`, `state/`) n'est **jamais rembobiné**.

## 1. Contrat technique du template (à ne jamais casser)
1. Une seule ligne d'injection, exactement : `const D = __DATA__;` (remplacée par `render_page.py`).
2. Exactement **deux** blocs `<script` dans le fichier.
3. Une seule ligne `const VERSION_UX = "Vx.y";` et le bandeau `#versions` affichant `Moteur : ${D.version_engine} · Stratégie : ${D.strategy_version} · UX/UI : ${VERSION_UX}`.
4. Tous les ids listés ci-dessous restent présents (on peut en **ajouter** ; en supprimer = demande fonctionnelle + mise à jour de `tests/contract.json` par Kraken Bot). Tout id référencé en JS doit exister.
5. Seules les clés de `D` listées ci-dessous (ou ajoutées par Kraken Bot) sont lues ; jamais de clé inventée.
6. Sources live conservées : `STATE_URL` + `fetch(STATE_URL…)` sur `state/public_state.json`, API Kraken `Ticker` et `OHLC`.
7. Aucune donnée d'exemple codée en dur (`D = {…}`, `D = JSON.parse(…)`, lorem ipsum, « données fictives / mock »). Aucun « undefined », « NaN », « [object Object] » visible.
8. Libellés « LIVE » / « sur clôture » / « valeurs FIGÉES » conformes à `docs/SPEC_UX.md`.

## 2. Périmètre
- GPT6 modifie **uniquement** `dashboard_template.html` (+ `CHANGELOG.md`, `docs/SPEC_UX.md`). **Jamais** `cycle_v11.py`, `cycle.py`, `backtest.py`, `page_data.py`, `render_page.py`, `sim.db`, `state/`, `.github/workflows/`, `VERSION_ENGINE`, `strategy/`, `tests/`.
- GPT6 travaille sur une branche `ux/<sujet>` (ou `feature/*`, `fix/*`) créée depuis `develop` et ouvre une PR vers `develop`, qu'il fusionne lui-même une fois guard vert (voir Circuit) ; **jamais de push direct sur develop, jamais de push ni de fusion sur main**.
- Chaque PR UX **incrémente `VERSION_UX`** et ajoute en tête de `CHANGELOG.md` une entrée `## [UX <nouvelle version>] — date — GPT6`.
- Chaque modification du moteur V1.1 impose une évolution de `VERSION_ENGINE` ; la V1.2 utilise exclusivement `VERSION_ENGINE_V12` (Moteur V1.3 en expérimentation) et ne peut modifier la version partagée.
- Chaque changement de stratégie **incrémente `STRATEGY_VERSION`** + entrée `## [Stratégie <version>]` avec paramètres avant/après, justification et **backtest** (Kraken Bot).
- Besoin d'une donnée ou d'une règle nouvelle → issue GitHub avec l'étiquette **`fonctionnel`** (Kraken Bot l'ajoute dans `page_data.py`, puis le contrat).

## 3. Ce que bloque `guard.yml` (PR et push sur main)
- **perimetre-ux** (PR depuis `ux/*`) : échoue si un fichier hors `dashboard_template.html`, `CHANGELOG.md`, `docs/SPEC_UX.md` est modifié.
- **perimetre-gpt6** (PR depuis `ux/*`, `feature/*`, `fix/*`) : échoue si la PR modifie le moteur, `VERSION_ENGINE`, `strategy/`, `params.json`, `.github/workflows/sim.yml`, `state/` ou `sim.db`. Ces changements passent par une branche Kraken Bot avec revue technique.
- **perimetre-strategie** (toute PR `strategy/*`) : bloque `state/**`, `sim.db`, `VERSION_ENGINE` partagé et fichiers moteur/stratégie V1.1 ; tests négatifs inclus.
- **versions** (toute PR) : template modifié sans changement de `VERSION_UX`, sans `CHANGELOG.md` ou sans entrée `## [UX <version>]` → échec ; `strategy/` modifié sans incrément de `STRATEGY_VERSION`, sans entrée `## [Stratégie <version>]` ou sans backtest → échec ; fichiers moteur modifiés sans incrément de `VERSION_ENGINE` et entrée `## [Moteur <version>]` → échec.
- **preprod-isole** (PR et push) : `preprod.yml` / `render_preprod.py` ne doivent référencer ni la base de la sim, ni les scripts de cycle/rendu prod, ni l'écriture d'état, ni un push vers `kraken-sim` (seul `kraken-sim-preprod`).
- **contrat** (PR et push) : `tests/check_template.py` (points 1 à 7 ci-dessus, rendu réel avec `render_page.py` puis Chrome sans interface : zéro erreur JS, zéro undefined/NaN, versions affichées).

## 4. Procédure de test (avant chaque PR)
```bash
git fetch origin && git checkout -b ux/mon-sujet origin/develop
# éditer dashboard_template.html, incrémenter VERSION_UX, ajouter l'entrée CHANGELOG
python3 tests/check_template.py      # doit finir par « RÉSULTAT : contrat respecté »
SIM_NO_REMOTE=1 SIM_OUT=/tmp/prev python3 render_page.py && xdg-open /tmp/prev/dashboard.html   # vérif visuelle
git push -u origin ux/mon-sujet && gh pr create --base develop --fill
```
La PR vers `develop` est fusionnée par GPT-6 dès que `guard` est vert ; la PR `develop` → `main` reste fusionnée par Cyril seul.

## 5. Liste exhaustive (contrat `tests/contract.json`)
**Ids (69)** : `accountCaption`, `accountChange`, `accountChangePct`, `accountValue`, `activity`, `alloc`, `allocationVisual`, `analysis`, `bchart`, `briefCash`, `briefDd`, `briefExposure`, `briefFees`, `briefPnl`, `briefTrades`, `btcRegime`, `cmp`, `compareVisual`, `corePos`, `cycleElapsed`, `cycleNext`, `dd`, `dec`, `dot`, `drawdownVisual`, `equityChartNote`, `equityPeriods`, `equityPlot`, `equityRangeLabel`, `head`, `ind`, `inddot`, `indsrc`, `indst`, `jr`, `kill`, `lch`, `lchart`, `lessons`, `lessonsCard`, `live`, `lp`, `lst`, `market`, `metrics`, `mobileToggle`, `navToggle`, `orderCount`, `ordersVisual`, `overview`, `periodNote`, `pnl`, `portfolio`, `pos`, `rail`, `rules`, `sellConditions`, `signalBars`, `signals`, `split`, `splitNote`, `splitTable`, `stateSrc`, `strat`, `ts`, `uptime`, `ver`, `versions`, `wf`

**Clés de `D` utilisées (51)** : `C0`, `allocation`, `as_of`, `atr_mult`, `backtest`, `basket_return_pct`, `btc_regime`, `btc_regime_state`, `btc_return_pct`, `btc_series`, `cash`, `core`, `cur_dd_pct`, `curve`, `dd_series`, `decisions`, `equity`, `exposure_pct`, `fees`, `fees_tier`, `ind_btc_pair`, `ind_live`, `indicators`, `indicators_src`, `invested_pct`, `journal`, `keep_rank`, `killed`, `last_cycle_iso`, `lessons`, `max_dd_pct`, `min_hold_h`, `n_cycles`, `n_trades`, `net_return_pct`, `orders`, `pnl_by_asset`, `pnl_gross`, `pnl_net`, `positions`, `snapshot`, `start_iso`, `start_paris`, `total`, `trade_stats`, `universe`, `version`, `version_engine`, `vs_btc_pct`, `walkforward`, `win_rate_pct`

## Dérogation V1.2 — approuvée pour le travail de branche seulement
- GPT-6 travaille sur la branche `strategy/v1.2` issue de develop, en exception explicite de `perimetre-gpt6`. Les contrôles `perimetre-strategie`, `isolation-v12`, `versions` et `contrat` restent obligatoires.
- La protection de `cycle_v11.py`, `cycle.py`, `sim.yml`, `sim.db`, `state/`, `strategy/params.json`, `page_data.py`, `render_page.py` et du template est **intacte** pour toutes les branches.
- Etat V1.2 dans `kraken-sim-preprod/state-v12` seulement. Aucun moteur V1.2 ne peut écrire dans `kraken-sim` ou `kraken-sim-state`.
- `sim_v12.yml` : workflow manuel, pas de cron, code figé à un SHA validé, calcul sans secret et publication séparée. Présence du workflow sur main, activation des cycles et activation ultérieure du cron : décisions distinctes de Cyril.
- La SPEC de stratégie provient de Grok Bot ; première fusion de `strategy/v1.2` vers develop soumise à Cyril et à une revue technique Grok Bot.
- Le site préprod continue temporairement à afficher V1.1 jusqu'à un état V1.2 réel et testé ; ne jamais présenter ses données V1.1 comme les résultats du moteur V1.2.
- Numérotations indépendantes : moteur V1.3, stratégie V1.2 et UX propre.

### Revue Grok Bot du 25 octobre 2026 — résolution du P0
- La regex précédente de `perimetre-strategie` contenait le motif `state/` ancré de fin, qui ne détectait aucun fichier sous `state/`.
- La nouvelle règle interdit `^state/` et les chemins V1.1 exacts, notamment `VERSION_ENGINE`.
- `tests/test_v12_protected_paths.py` teste explicitement les chemins `state/public_state.json`, `state/history/index.json`, `state/x.json` ainsi que les autres fichiers protégés.
- `VERSION_ENGINE_V12` est distinct : toute révision du moteur expérimental ne peut plus ré-étiqueter les ordres V1.1.
