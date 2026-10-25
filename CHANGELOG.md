# Journal des modifications — Kraken Sim (paper trading, aucun ordre réel)

> **Convention d'ajout (obligatoire, vérifiée par `guard.yml`)**
> - Trois versions **indépendantes** :
>   - **Moteur** : fichier `VERSION_ENGINE` (source unique, exposée dans `state.json` / `D.version_engine`). Incrémentée **uniquement par Kraken Bot** à chaque modif moteur/données/règles.
>   - **Stratégie** : `STRATEGY_VERSION` dans `strategy/params.json` (règles d'achat/vente et paramètres, source unique, exposée dans `state.json` / `D.strategy_version`, enregistrée sur chaque ordre, décision et cycle). Incrémentée **uniquement par Kraken Bot** ; entrée obligatoire avec **paramètres avant/après, justification, résultat de backtest**. GPT6 n'y touche jamais.
>   - **UX/UI** : constante `const VERSION_UX = "Vx.y";` dans `dashboard_template.html`. Incrémentée **uniquement par GPT6** à chaque PR `ux/*`.
> - Toute modification ajoute une entrée **en tête** du fichier, dans la même PR :
>   `## [Moteur Vx.y] — JJ/MM/AAAA HHhMM (Paris) — Kraken Bot`, `## [Stratégie Vx.y] — … — Kraken Bot` ou `## [UX Vx.y] — JJ/MM/AAAA HHhMM (Paris) — GPT6`
>   puis les sections utiles : **Fonctionnel / UX-UI / Infra / Corrections**, une ligne par changement (fichier + impact sur les décisions, « aucun » si visuel).
> - Les commits automatiques « état sim … » ne sont pas journalisés.
> - Versions actuelles : **Moteur V1.1 · Stratégie V1.1 · UX/UI V1.1**.

## [Infra] — 25/10/2026 14h05 — Kraken Bot (versions inchangées : Moteur V1.1 · Stratégie V1.1 · UX/UI V1.1)
### Infra
- Préprod minimale : branche `develop`, dépôt public `cyrillaferrere/kraken-sim-preprod` (site seul, GitHub Pages), workflow `preprod.yml` (push sur develop : `render_preprod.py` rend le template de develop avec le state public de prod en lecture seule, bandeau PRÉPRODUCTION injecté à la publication, `tests/check_preprod.py`, push via clé de déploiement limitée au dépôt préprod, secret `PREPROD_DEPLOY_KEY`).
- `sim.yml` ne tourne que sur `main` ; `guard.yml` aussi sur develop + contrôle `preprod-isole`.
- GARDE_FOUS / README / SPEC_UX : circuit develop → préprod → main (fusion par Cyril, « OK prod » GPT-6 + Kraken Bot).

## [Stratégie V1.1] — 25/10/2026 13h15 — Kraken Bot
### Fonctionnel
- Création du versionnage stratégie : `strategy/params.json` (`STRATEGY_VERSION` = V1.1) devient la source unique des paramètres, lus par `cycle_v11.py` ; valeurs **identiques** aux constantes précédentes (aucun changement de décision).
- Paramètres V1.1 : k hystérésis 0,15 · rang de maintien 4 · détention min. 48 h · challenger +10 pts · stop 3×ATR14 · sizing 3 × 33 % · coupe-circuit −30 % · pas d'achat 60 min avant 00:00 UTC · spread max 0,3 % · ordre min. 25 $ · sortie B taker après 3 cycles · socle différé 48 h.
- Avant (V1.04) → après (V1.1) : régime 2 états → 3 états (k = 0,15) ; rotation libre → rang ≤ 4 / 48 h / +10 pts ; taker 0,80 % → maker post-only + paliers ; univers top 10 → filtre `country_code=FR`.
- Justification : audit ChatGPT (`v1_1/specs/audit_chatgpt.md`). Backtest (ablation, validation 02/02–23/10/2026) : V1.04 +1,2 % → V1.1 **+30,6 %**, 70 trades, DD max 30 %.
### Infra
- Colonne `strategy_version` sur `orders`, `decisions`, `cycles` ; `state.json` : `strategy_version`, `strategy_params`, `perf_by_strategy` (ordres, frais, P&L réalisé par version). Badge « Stratégie : V1.1 » en tête du dashboard. Les ordres antérieurs à la colonne sont rattachés à leur `version`.

## [Moteur V1.1] — 25/10/2026 13h10 — Kraken Bot
### Infra
- Moteur V1.1 inchangé (aucune logique de trading modifiée).
- Collaboration à deux : `GARDE_FOUS.md`, `docs/SPEC_FONCTIONNELLE.md`, `docs/SPEC_UX.md`, `tests/check_template.py` + `tests/contract.json`, workflow `guard.yml`, modèle de PR, CODEOWNERS, étiquettes `fonctionnel` / `ux`.
- Versions séparées : fichier `VERSION_ENGINE` (lu par `cycle_v11.py` et `page_data.py` → `version_engine`), `VERSION_UX` dans le template, bandeau « Moteur : … · UX/UI : … » en haut du dashboard. Aucune logique de trading modifiée.

## [UX V1.1] — 25/10/2026 12h22 — Kraken Bot
### Corrections
- Tableau « Conditions de vente » : la colonne Régime BTC recalculait un régime à 2 états (clôture > EMA50, logique V1.04) et affichait « baissier » alors que le moteur était **neutre** (dans la bande d'hystérésis). Elle affiche désormais l'état réel du moteur (`btc_regime_state`, `snapshot.band`) ; « Sous EMA50 » est une colonne distincte. Impact décisions : aucun.
- Texte des règles de sortie V1.04 remplacé ; repli 2 états supprimé du tableau des indicateurs ; champs du socle tolérants (plus de « undefined » / « NaN % »).
### UX-UI
- Tout en live (bid Kraken toutes les 20 s) : valorisations, P&L, total, exposition, socle, distances aux stops ; heure du dernier prix live ; mention « valeurs FIGÉES du cycle » si l'API est injoignable.
- Indicateurs journaliers étiquetés « sur clôture », avec prix live et écart live vs EMA50 et vs bornes de la bande (indicatif).

## [Moteur V1.1] — 25/10/2026 12h05 — Kraken Bot
### Infra
- Migration GitHub : dépôt `cyrillaferrere/kraken-sim`, workflow `sim.yml` (cron `10 * * * *` UTC filtré par `PARIS_HOURS`, `workflow_dispatch` render/cycle, concurrence `kraken-sim`, commit de l'état), GitHub Pages (`index.html` + `state/public_state.json`). `render_page.py` : `SIM_NO_REMOTE=1` en Actions. `check_github.py`, `sync_to_github.sh`. Bascule et cron actif à 12h08.

## [Moteur V1.1] — 25/10/2026 12h00 — Kraken Bot
### Fonctionnel
- Socle de départ **vendable** : BTC/ETH/XRP deviennent des positions normales (migration unique `core_migrated`, `migrate_socle_libre.py`). Un portefeuille de 6 605,10 $, coupe-circuit sur le total, cible 33 % du total ; position < ½ cible = hors emplacement, renforçable en régime haussier ; sortie de tendance du socle différée 48 h après l'achat initial (stop et risk-off immédiats). Table `core` = référence « socle conservé ».
### UX-UI
- Section « Portefeuille vs socle de départ conservé », tableau « Socle de départ », colonne Origine, courbe « Socle conservé ».

## [UX V1.1] — 25/10/2026 11h45 — GPT6 (cahier des charges) / Kraken Bot (intégration)
### UX-UI
- Refonte V1.1 de ChatGPT (`v1_1/specs/ux_spec_v1_1.md`) : rail de navigation, bandeau solde + évolution par période, graphiques homogènes, journal structuré, sections Portefeuille / Activité / Analyse des marchés / Analyse & performance, responsive.

## [Moteur V1.1] — 25/10/2026 11h33 — Kraken Bot
### Fonctionnel
- `cycle_v11.py`, issu de l'audit ChatGPT (`v1_1/specs/audit_chatgpt.md`) et d'une ablation (`v1_1/ablation_results.json`) : univers `country_code=FR`, palier de frais 30 j, maker post-only à remplissage prudent, régime BTC 3 états (EMA50 ± 0,15×ATR14), tampon de rang ≤ 4, détention ≥ 48 h, challenger +10 %, décision quotidienne unique sur bougies clôturées, pas d'achat 60 min avant 00:00 UTC.
- Ablation (validation 02/02–23/10/2026) : V1.04 +1,2 % ; +FR +4,3 % ; +paliers +18,9 % ; +maker +28,6 % ; +hystérésis +18,8 % ; +tampon/48 h/challenger +30,6 % (70 trades, DD max 30 %) ; momentum V1.04 conservé.
- Socle de départ acheté une fois (500 $ BTC, 300 $ ETH, 200 $ XRP, maker au bid), d'abord « jamais vendu » (corrigé à 12h00).
### Infra
- Archive V1.04 (hors dépôt) ; `run_cycle_v11.sh`, `refresh_page_v1_1.md`.

## [UX V1.04] — 24/10/2026 — GPT6 (design) / Kraken Bot
### UX-UI
- Nouveau design du dashboard (version GPT).
### Infra
- État public publié à chaque cycle sur `cyrillaferrere/kraken-sim-state` (`state.json`), relu par le HTML toutes les 60 s.

## [Moteur V1.03] — 24/10/2026 — Kraken Bot
### Fonctionnel
- `indicators` : colonnes `vol_ratio`, `macd_hist` ; positions « test » (détention min. 24 h).
### UX-UI
- Tableau chiffré des indicateurs, recalculés en direct (OHLC 1440, bougies clôturées) toutes les 60 s.

## [Moteur V1.02] — 24/10/2026 — Kraken Bot
### Fonctionnel
- Frais simulés 0,80 % (taker palier 1) au lieu de 0,40 % ; walk-forward `backtest2.py` (0,40 % / 0,80 %) affiché.

## [Moteur V1.01] — 24/10/2026 — Kraken Bot
### Fonctionnel
- Table `indicators` par cycle, prix ETH enregistré (panier 50/50), correctif du poids cible 33 %.
### UX-UI
- Prix BTC, panier BTC/ETH, drawdown, brut vs frais, P&L par crypto, journal en phrases, leçons ; BTC/USD live (REST + WebSocket).

## [Moteur V1.0] — 24/10/2026 — Kraken Bot
### Fonctionnel
- Première version : C0 = 6 605,10 $, rotation momentum top 3 (A), remplacée le jour même par la stratégie B (régime BTC > EMA50, 5 confirmations, top 3 momentum à 33 %, stop 3×ATR, coupe-circuit −30 %) après un backtest (A : drawdown 51 %).
