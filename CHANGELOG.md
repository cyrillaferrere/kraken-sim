# Journal des modifications — Kraken Sim (paper trading, aucun ordre réel)

> **Convention d'ajout (obligatoire, vérifiée par `guard.yml`)**
> - Trois versions **indépendantes** :
>   - **Moteur** : `VERSION_ENGINE` reste réservé au moteur partagé V1.1 ; `VERSION_ENGINE_V12` est la source indépendante du moteur expérimental V1.2. Chaque flux expose uniquement sa propre version. Pour la V1.2, GPT-6 code avec revue technique Kraken Bot.
>   - **Stratégie** : la V1.1 est définie par `strategy/params.json` ; les hypothèses expérimentales V1.2 sont isolées dans `strategy/v1_2/params.json` avec `STRATEGY_VERSION=V1.2`. Spécification et revue par Kraken Bot, implémentation déléguée à GPT-6. Les résultats de backtest non encore calculés doivent être explicitement indiqués comme tels.
>   - **UX/UI** : constante `const VERSION_UX = "Vx.y";` dans `dashboard_template.html`. Incrémentée **uniquement par GPT6** à chaque PR `ux/*`.
> - Toute modification ajoute une entrée **en tête** du fichier, dans la même PR :
>   `## [Moteur Vx.y] — JJ/MM/AAAA HHhMM (Paris) — Kraken Bot`, `## [Stratégie Vx.y] — … — Kraken Bot` ou `## [UX Vx.y] — JJ/MM/AAAA HHhMM (Paris) — GPT6`
>   puis les sections utiles : **Fonctionnel / UX-UI / Infra / Corrections**, une ligne par changement (fichier + impact sur les décisions, « aucun » si visuel).
> - Les commits automatiques « état sim … » ne sont pas journalisés.
> - Versions sur `develop` : **moteur partagé V1.2 · stratégie V1.1 · UX/UI V1.1.2**. En PR expérimentale seulement : **moteur V1.3 (`VERSION_ENGINE_V12`) · stratégie V1.2**, sans fusion ni cycle.


## [Moteur V1.6.5] — 26/10/2026 01h55 (Paris) — Kraken Bot (VERSION_ENGINE_V12, moteur expérimental V1.2)

**Fonctionnel**
- `strategy/v1_2/params.json` : plafond d'exposition crypto porté de 1 500 à 2 000 USDC (coût investi, frais inclus) à la demande de Cyril ; diversification inchangée (40 % max par actif, 25 % du plafond max par achat). Backtest non recalculé.
- État V1.2 remis à zéro (6 605,10 USDC), ancien état archivé dans `archive/2026-10-26-run1/` sur state-v12.

## [Stratégie V1.2] — 26/10/2026 01h55 (Paris) — Kraken Bot

**Fonctionnel**
- Plafond 2 000 USDC ; résultats de backtest non encore calculés.

## [Moteur V1.6.4] — 26/10/2026 01h15 (Paris) — Kraken Bot (VERSION_ENGINE_V12, moteur expérimental V1.2)
### Fonctionnel
- `v12_autonomy.py` : plafond par actif `max_per_asset_share=0.40` (600 USDC de coût investi + achats en attente par crypto, refus `ASSET_SHARE_CAP`) et plafond par achat `max_buy_share_per_cycle=0.25` (375 USDC, refus `BUY_ABOVE_PER_CYCLE_SHARE`). Position au-dessus du plafond : aucune vente forcée, seuls les nouveaux achats sont bloqués.
- `v12_cycle.py` : budget d'achat = min(poids × equity, budget restant, 375, 600 − coût de l'actif) ; actifs au-dessus de 40 % listés `ASSET_SHARE_CAP_NO_NEW_BUY`.
### Corrections
- `v12_autonomy.py` : un spread > 0,3 % sur une paire hors BTC/ETH ne bloque plus tous les achats (`EXCESSIVE_SPREAD` global) ; la paire seule est exclue (`PAIR_EXCLUDED_SPREAD`). BTC/ETH au-delà de 0,3 % bloquent toujours globalement.
- `v12_paper_engine.py` : `pending_buy_usd_by_asset` dans l'état de risque.
- `tests/test_v12_exposure_cap.py` : 7 tests V1.6.4.

## [Stratégie V1.2] — 26/10/2026 01h15 (Paris) — Kraken Bot (paramètres expérimentaux, accompagne Moteur V1.6.4)
### Fonctionnel
- `strategy/v1_2/params.json` : `RISK.max_per_asset_share=0.40`, `RISK.max_buy_share_per_cycle=0.25`. Backtest **non recalculé** avec ces plafonds.

## [Moteur V1.6.3] — 26/10/2026 00h59 (Paris) — Kraken Bot (VERSION_ENGINE_V12, moteur expérimental V1.2)
### Fonctionnel
- `v12_autonomy.py` : plafond absolu d'exposition crypto `RISK.max_crypto_exposure_usdc` (1 500 USDC) sur le **coût investi frais inclus** (Σ qty × avg_cost) + ordres en attente ; refus `CRYPTO_EXPOSURE_CAP_USDC` à l'admission et à l'exécution.
- `v12_cycle.py` (nouveau) + `cycle_v12.py --cycle --state-dir` : cycle PAPER déterministe moteur (pas une IT Grok) repris sur l'état existant (pas de réinitialisation), taille des ordres et contrôle de profondeur calculés sur le budget restant sous plafond ; HOLD motivé sinon. Aucun ordre réel, aucune clé.
- `render_v12_page.py`, `dashboard_v12_cockpit_template.html` : affichage plafond, montant investi, budget restant et USDC restant ; ordres PAPER exécutés listés.
### Corrections / tests
- `tests/test_v12_exposure_cap.py` (8 tests) ; fixtures synthétiques pré-V1.6.3 exécutées plafond désactivé (`crypto_cap_disabled`, jamais en cycle).

## [Stratégie V1.2] — 26/10/2026 00h59 (Paris) — Kraken Bot (paramètres expérimentaux, accompagne Moteur V1.6.3)
### Fonctionnel
- `strategy/v1_2/params.json` : `RISK.max_crypto_exposure_usdc=1500`, `crypto_exposure_basis=COST_INVESTED_INCL_FEES` (consigne Cyril : capital réel suivi, 1 500 USDC max investis en crypto). Backtest **non recalculé** avec ce plafond.

## [Stratégie V1.2] — 26/10/2026 01h00 (Paris) — Kraken Bot (paramètres expérimentaux, accompagne Moteur V1.6.2)
### Fonctionnel
- `strategy/v1_2/params.json` : `UNIVERSE.min_median_daily_usdc_volume_30d` = 1 000 000 (ex-`min_median_daily_usd_volume` = 5 000 000) + bloc `LIQUIDITY` (garde-fous Depth, alerte, repli 5 M documenté non automatisé). STRATEGY_VERSION reste V1.2 (stratégie expérimentale non sélectionnée).
- Backtest : **non recalculé** pour ce seuil (résultats de backtest existants obtenus à 5 M ; à relancer avant toute sélection). Aucun cycle avec ordres lancé.

## [Moteur V1.6.2] — 26/10/2026 01h00 (Paris) — Kraken Bot (VERSION_ENGINE_V12, moteur expérimental V1.2)
> Correctif (3e chiffre). Décision Cyril : seuil de liquidité PAPER abaissé à 1 M USDC, avec garde-fous. VERSION_ENGINE partagé V1.1 inchangé.
### Fonctionnel
- `strategy/v1_2/params.json` : `UNIVERSE.min_median_daily_usd_volume` (5 M) renommé `min_median_daily_usdc_volume_30d` = **1 000 000** ; lecture rétrocompatible de l'ancienne clé (`v12_autonomy.min_median_volume_usdc`). Nouveau bloc `LIQUIDITY` (spread ≤ 0,3 %, bande ±0,5 %, 3× l'ordre, seuils d'alerte, repli 5 M non automatisé). Impact décisions : l'univers éligible est désormais filtré par médiane 30 j ≥ 1 M USDC.
- `v12_kraken_public.py` : éligibilité = **médiane 30 j** du volume quotidien en USDC (volume × close des bougies OHLC journalières closes), et non plus le Ticker 24 h (`usd_volume` → `usdc_volume_24h`, utilisé seulement pour ordonner la présélection). Moins de 30 bougies ou donnée manquante → `null` et paire rejetée (`VOLUME_MEDIAN_30D_UNAVAILABLE`), sinon `VOLUME_MEDIAN_30D_BELOW_MIN`. BTC/ETH restent obligatoires. Lecture du carnet via l'endpoint public `/0/public/Depth` pour chaque paire éligible ; instantané `liquidity.books` (meilleur bid/ask, spread, profondeur USDC à ±0,5 %).
- Nouveau `v12_liquidity.py` + `v12_paper_engine._liquidity_gate` : avant chaque ordre PAPER taker, profondeur cumulée côté exécution à ±0,5 % du mid ≥ 3× la taille de l'ordre, sinon refus `INSUFFICIENT_DEPTH` (`DEPTH_UNAVAILABLE` si carnet absent). Slippage estimé en traversant le carnet. Sorties de sécurité forcées (kill switch, stops) jamais bloquées par un carnet mince.
- Métriques persistées dans l'état V1.2 (kv `liquidity_metrics`, `liquidity_alert`) et bloc `liquidity_monitor` publié à chaque IT dans `check_report.json` et `public_state_v12.json` (champs attendus par le dashboard de la PR #22).
- Alerte `LIQUIDITY_REVIEW` (état + logs) si ≥ 20 tentatives et (refus > 5 % ou slippage médian > 0,15 %). Repli documenté : retour à 5 M, décision manuelle de Cyril.
### Infra
- Tests : `tests/test_v12_liquidity.py` (profondeur suffisante/insuffisante, médiane 30 j, alerte, null si données manquantes, garde moteur) ; stub Depth dans `test_v12_real_bridge.py`.

## [Moteur V1.6.1] — 25/10/2026 23h55 (Paris) — Kraken Bot (VERSION_ENGINE_V12, moteur expérimental V1.2)
> Numérotation : désormais à 3 chiffres (x.y.z). VERSION_ENGINE partagé V1.1 inchangé.
### Fonctionnel
- Conformité UE/MiCA (demande Cyril, résident FR) : nouveau `v12_compliance.py` + `docs/CONFORMITE_UE_V1_2.md` (sources datées). Impact décisions : univers réduit aux seules paires XXX/USDC.
- `v12_kraken_public.py` : univers = XXX/USDC `online` de `AssetPairs?country_code=FR`, hors stablecoins (USDT…) et liste EEE restreinte, spread ≤ 0,3 %. Voie de conversion XXX/USD ÷ USDC/USD supprimée (`usdc_quote`, `pairs_usd`). Bougies des signaux = OHLC XXX/USDC ; < 220 bougies → `insufficient_history`, données null, exclues des entrées. Régime BTC sur BTC/USDC.
- Gateway moteur (`v12_paper_engine.admit_batch`) : rejet `REJECTED_COMPLIANCE` de toute décision hors USDC, stablecoin, actif restreint, levier/marge, vente à découvert (SELL > position), paire non éligible ou historique insuffisant. Indépendant de Grok.
- `v12_init_check.py` / `render_v12_page.py` : bloc `compliance` publié ; page `/v12/` affiche « Conformité UE/MiCA » et le nombre de paires USDC éligibles (UX V1.2.1 du cockpit V1.2, ligne d'info USDC/USD retirée).
- Portefeuille (précision Cyril) : l'USDC est compté comme une crypto. `public_state_v12.json` expose `portfolio` = ligne USDC (quantité = valeur = cash, poids %) + positions ; la page `/v12/` affiche le tableau « Portefeuille » (Actif, Quantité, Valeur USDC, Poids, Rôle) — UX V1.2.2. USDC reste devise de compte/refuge, exclu des signaux et des entrées ; `cash_usdc` conservé dans le moteur.
### Infra
- Tests : `tests/test_v12_eu_compliance.py` (USD, USDT, short, levier, historique null, univers 100 % USDC), test gateway dans `test_v12_paper_engine_30d.py` ; `test_v12_usdc_quote.py` supprimé (conversion retirée).

## [Moteur V1.6] — 25/10/2026 23h30 (Paris) — Kraken Bot (VERSION_ENGINE_V12, moteur expérimental V1.2)
### Fonctionnel
- Devise de compte du portefeuille V1.2 = **USDC** (demande Cyril) : capital de départ 6 605,10 USDC, cash, équité, PnL, frais, pic et positions en USDC (`v12_paper_engine.py` : `quote_currency` persisté, défaut historique USD pour les anciens états). Impact décisions : seuils/montants désormais exprimés en USDC.
- Valorisation (`v12_kraken_public.py`) : paire Kraken XXX/USDC directe si en ligne et spread ≤ 0,3 % ; sinon XXX/USD convertie par USDC/USD de façon prudente (bid = bid_USD / ask_USDCUSD, ask = ask_USD / bid_USDCUSD). Méthode publiée (`valuation_method`, champ `valuation` par cotation). Bougies journalières (signaux, ratios) inchangées en XXX/USD.
- Benchmark « conserver les USDC » = 6 605,10 USDC constants, rendement 0 %. USDC/USD conservé comme ligne d'information.
- `check_report.json` / `public_state_v12.json` : `"quote_currency": "USDC"`, clés `*_usdc` (plus de clés `*_usd` pour le portefeuille).
### Infra
- Migration (`v12_init_check.py`) : un état USD hérité est réinitialisé en USDC **uniquement** si 0 ordre, 0 exécution, 0 position ; journalisé dans `check_report.json` (`migration`) et `migration_log.json` ; refus `USD_STATE_WITH_ACTIVITY_REFUSED` sinon. L'historique git de state-v12 est conservé.
### UX-UI
- `dashboard_v12_cockpit_template.html` : montants affichés en « USDC » (plus de « $ »). Impact décisions : aucun.
### Tests
- `tests/test_v12_usdc_quote.py`, migration et refus dans `tests/test_v12_init_check.py`, absence de « $ »/USD dans `tests/test_v12_page_render.py`.

## [Moteur V1.5] — 2026-10-25 (VERSION_ENGINE_V12, moteur expérimental V1.2)
- Nouveau `render_v12_page.py` : rendu de la page PREPROD V1.2 PAPER (`v12/index.html` + `v12/public_state_v12.json`) à partir du `check_report.json` réel de l'init-check, via `export_v12.normalize` ; données absentes = null (« — »). Impact décisions : aucun (lecture seule de l'état V1.2, aucun ordre).
- Nouveau `dashboard_v12_cockpit_template.html` : cockpit UX V1.2.0 (branche ux/v1.2-preprod-cockpit) avec bandeau PREPROD V1.2 PAPER et bloc contrôle init-check (décision HOLD, ordres, paires exclues, garde-fous). Impact décisions : aucun.
- Tests : `tests/test_v12_page_render.py`.

## [Moteur V1.4] — 2026-10-25 (VERSION_ENGINE_V12, moteur expérimental V1.2)
- Exclusion par paire : une cotation invalide, périmée ou au spread > 0,3 % exclut seulement cette paire pour le tick (raison journalisée `PAIRS_EXCLUDED_THIS_TICK`, `excluded_pairs` dans la synthèse). Pause globale seulement si BTC/ETH invalides ou si moins de N = max(2, min(10, ⌈paires cotées/2⌉)) paires valides (N = 10 pour 40 paires). Une position détenue à cotation invalide est conservée (valorisée au dernier bid > 0, protections maintenues) et journalisée.
- Nouveau mode `cycle_v12.py --init-check --state-dir <abs>` : init si absent (6 605,10 cash, pic 6 605,10, benchmark USDC), sans jamais écraser ; données publiques Kraken ; signaux A/B/C/D ; synthèse ; garde-fous ; décision HOLD seule via la gateway ; assertion orders == 0 et fills == 0 avant écriture de l'état et de `check_report.json`.

## [Stratégie V1.2] — 25/10/2026 — correction de cadrage IT / connecteur Kraken — Cyril / GPT-6
### Fonctionnel
- **Précision utilisateur (sans modification de stratégie)** : Grok Bot réalise ses analyses **par IT à fréquence variable, possiblement 10 fois par jour ou davantage**. La recommandation d'IT quotidienne vers 02h30 n'est **pas une exigence utilisateur** et ne doit plus guider l'ordonnanceur.
- Grok dispose **déjà d'un connecteur Kraken**. Il analyse le marché, prend les décisions de gestion fictive selon la V1.2 et apprend de ses résultats ; le moteur PAPER est un système d'exécution, de comptabilité, de risques et de vérification indépendante des cours.
- **Correctif technique multi-IT** : `v12_grok_issues.py` traite désormais les issues récentes en lot, dans l'ordre, et `v12_live_bridge.py` soumet toutes les IT valides au moteur (idempotence par `decision_id`) au lieu de ne retenir que la dernière. Test de 12 IT sur une seule collecte. Ce correctif ne change ni les paramètres V1.2, ni le cron, ni V1.1, ni la production.

## [Stratégie V1.2] — 25/10/2026 — Kraken Bot (SPEC) / GPT-6 (paramètres expérimentaux)
### Fonctionnel
- Spécification et critères de rejet pre-enregistrés par Grok Bot avant backtest ; `strategy/v1_2/params.json` fige les hypothèses des candidats A Donchian, B dual momentum, C BTC/ETH tendance, D V1.1 hebdomadaire.
- Les scénarios frais F1 et F2, l'univers point-in-time, les limites d'exposition et le kill-switch de la SPEC sont documentés séparément de la stratégie V1.1.
### Backtest
- **Non exécuté / aucun résultat** au moment de ce commit : le backtest V1.2 sera implémenté et évalué hors échantillon avant toute sélection ou mise en fonctionnement.

## [Moteur V1.3] — 25/10/2026 — GPT-6 (préprod V1.2, infrastructure)
### Corrections P1-A à P1-F de Grok Bot (fonctionnement par IT, sans activation)
- `v12_autonomy.py` : admission de la décision sur la synthèse de son IT puis revalidation sur quotes fraîches au cycle suivant ; TTL jusqu'à 26 h (A/C/D) et 7 jours (B). Refus des signaux incompatibles et des montants qui dépassent le cash réservé, les positions ou le risque.
- `v12_paper_engine.py` : exécuteur PAPER SQLite **hors réseau et hors production**, ordres idempotents par `decision_id`, maker initial puis éventuel fill partiel et repli taker, contrôle répété du risque avant tout fill, liquidations, stops déterministes A/B/C/D sans IT Grok, état moteur persistant (pic, pause, kill-switch, modèles/politiques autorisés).
- `v12_usdc_baseline.py` : comparaison contre les USDC conservés sur bid/ask observés, sans parité 1 USD inventée. `v12_paper_engine.py` calcule lui-même les outcomes à J+1/7/30, MAE et écarts USDC/BTC ; les sorties Grok ne peuvent pas écrire ces résultats.
- Exposition candidate C plafonnée à **min(90 % global, plafond spécifique)** ; test de dépassement explicite.
- `cycle_v12.py --dry-run --out ...`, `v12_synthetic_30d.py` : simulation locale accélérée de 30 jours **100 % synthétiques**, double livraison, IT manquantes, décision expirée, fill et kill-switch, résultat écrit uniquement hors dépôt. **`--cycle` demeure interdit**.
- `tests/test_v12_paper_engine_30d.py`, `tests/test_v12_cli_dry_run.py` : couverture du flux à blanc, garde-fous, sortie C indépendante de Grok et refus d'activation. Voir `docs/REVIEW_GROK_P1_30J_V12.md`.
- **Aucun résultat historique réel, aucun ordre réel, aucune fusion ni IT Grok lancée**. Le collecteur Kraken et le canal authentifié GitHub Issue ne sont pas branchés.

### Connexion Grok IT ↔ marché Kraken — code prêt, AUCUNE activation
- `v12_kraken_public.py` : collecte Kraken REST **publique** (AssetPairs, Ticker, OHLC clos), top spot USD préfiltré par volume, bid/ask et USDC/USD, sans identifiants de trading ni fichiers d'archives volumineux. Préfiltre 24 h non exhaustif ; contrôles de fraîcheur obligatoires.
- `v12_grok_issues.py` : lecture d'issues `IT V1.2` labellisées `it-decision` avec ID numérique d'auteur autorisé ; vérification JSON strict et SHA de synthèse avant admission indépendante.
- `v12_live_bridge.py` : raccord code collecteur → contrôles/positions PAPER → décision issue → validation, avec protections exécutées avant lecture GitHub ; aucun ordre en cas d'IT manquante. CLI de **vérification seulement** `--check-market`, sans démarrage de cycles.
- `tests/test_v12_real_bridge.py` : simulateurs réseau Kraken et GitHub, refus de mauvaises issues/SHA, données OHLC ouvertes, pannes GitHub ; aucune transaction réelle.
- [Procédure et prérequis restants](docs/BRANCHEMENT_KRAKEN_GROK_V12.md). Ni cron IT, ni collecte récurrente, ni merge, ni publication/déploiement, ni nouveau site.

### Suite aux corrections P1 de Grok Bot (branche, sans cycles)
- **Étape autonomie Grok V1.2 (sur PR, sans cycle)** : `v12_autonomy.py` reçoit une décision structurée et rejette tout signal/poids A/B/C/D non conforme, avec données Kraken fraîchement clôturées, frais F2, sans short ni levier, limite de corrélation et kill-switch indépendants. La politique/modèle actifs sont imposés par le futur orchestrateur, jamais par Grok.
- `v12_grok_gateway.py` : mode **prévalidation uniquement** et journalisation d'une proposition Grok ou indisponibilité, sans appel effectif au modèle ni exécution d'ordre.
- `v12_learning.py` : journal SQLite isolé, append-only au niveau applicatif, idempotence et chaîne d'empreintes, évaluation des horizons 1/7/30 jours et propositions de politique uniquement shadow (aucune auto-promotion).
- `tests/test_v12_autonomy.py`, `tests/test_v12_learning.py`, `tests/test_v12_grok_gateway.py` : refus de faux signaux, sur-exposition, mauvais modèle/politique, quote expirée, tentative de LIVE, collisions d'identifiants et altération de log.
- `docs/GROK_AUTONOME_V12_ETAPE1.md` : frontière entre les modules de préflight testés et les composants **encore manquants** (invocation Grok authentifiée, collecte public Kraken, exécuteur PAPER, USDC/USD). Aucun cycle V1.2 ni trading réel.

- `docs/VISION_AUTONOMIE_APPRENTISSAGE.md` : décision produit de Cyril : Grok Bot devra devenir le décideur autonome PAPER, avec apprentissage mesurable, mémoire persistante, contrôle de risque déterministe indépendant, journalisation et évaluation prospective. Les quatre stratégies A/B/C/D sont aussi des comparateurs ; aucune autorisation de cycle ou de trading LIVE n'est donnée.
- `fetch_kraken_history_v12.py` : outil en lecture réseau publique **uniquement sur action explicite** (`--download`), avec source Kraken verrouillée, 5 SHA-256 officiels, reprise HTTP Range, ZIP réassemblé vérifié, garde disque et sortie hors dépôt. Une relance n'écrase pas le manifeste et permet l'ajout Q3 sans effacer les preuves archivées.
- `prepare_kraken_history_v12.py`, `v12_data.py` : URL d'origine contrôlée par `scheme/hostname/path` exact, rejet des OHLC NaN/infini et des dates fractionnaires ; contrôle des archives Q3 conteneur ZIP. 
- `tests/test_v12_downloader.py` + tests de données : aucun accès réseau pendant les tests, reprise interrompue, serveur ignorant `Range`, SHA erroné, contenu trimestriel invalide, tentative d'URL mimant Kraken et manifeste inchangé au second passage.
- `docs/TELECHARGEMENT_KRAKEN_V1_2.md` : procédure locale Windows/PowerShell étape par étape et rappel du blocage sur listing/delisting historique. **Aucun téléchargement historique réel exécuté** sur GitHub ni depuis cet échange.

- `prepare_kraken_history_v12.py` : inventaire hors ligne des ZIP Kraken complets et 2026 T3, contrôle SHA-256, revue explicite des paires USD, dédoublonnage strict et `MANIFEST.draft.json` non certifié. Tests négatifs ZIP, paires inconnues et contradictions inter-archives.
- `v12_v11_replay.py` : rejeu du moteur `cycle_v11.py` original à l'aide de snapshots d'API synthétiques, dans SQLite + historique isolés hors dépôt et sans réseau ; toute API manquante fait échouer la référence, même si le moteur enregistre un cycle. Aucun historique 2021–2026 n'est revendiqué.
- `docs/DONNEES_ET_REPLAY_V1_2.md` : provenance Kraken, somme SHA-256 de l'archive complète, procédures de staging et distinction entre tests déterministes et véritable baseline V1.1.

- `v12_signals.py` : rejette bougies imputées, passe le sizing A par paramètres ; D récupère les indicateurs V1.1 historiques.
- `v12_rebalance.py`, `v12_backtest_core.py` : ventes partielles, rétention top K+2 de B, risque BTC quotidien, limites de corrélation et d'exposition, fills maker partiels et fallback taker, frais/spread/slippage distincts, kill-switch et délistage conventionnel, refus de valorisation gelée.
- `v12_data.py` : manifeste SHA-256 avec vérification de couverture des paires USD historiques et délistées exigée pour le mode officiel ; données historiques exhaustives encore absentes.
- `v12_walkforward.py`, `v12_acceptance.py` : 12 mois IS / 3 mois OOS, grille sélectionnée sur IS, critères de rejet figés, aucune sélection sans baseline V1.1 auditée ; `v12_baselines.py` modélise BTC, panier BTC/ETH/XRP mensuel et cash aux deux niveaux de frais.
- `export_v12.py`, `dashboard_v12_template.html`, `render_preprod.py` : données absentes à null, 51 clés du contrat, horodatages UTC/Paris et rendu V1.2 autonome uniquement sur activation explicite.
- `sim_v12.yml` : clé hôte SSH GitHub épinglée selon documentation officielle et nettoyage de la clé de déploiement même en échec ; workflow toujours uniquement en PR.
- `tests/test_v12_*.py` : nouveaux tests delisting/staleness, confluence V1.1, invariance A/B/C/D, manifeste, baselines, OOS, export local et sécurité du workflow.
- **Aucun résultat financier officiel, aucune simulation V1.2 lancée** : données exhaustives et replay V1.1 complet restent bloquants. Détails dans `docs/ETAT_AVANCEMENT_V1_2.md`.

### Corrections P0/P1 (revue Grok Bot PR #7)
- `.github/workflows/guard.yml` : contrôle exhaustif de `state/**` et gel de `VERSION_ENGINE` dans les branches `strategy/*` ; tests négatifs de chemin protégés.
- `VERSION_ENGINE_V12` : **V1.3 réservé au moteur V1.2** ; `VERSION_ENGINE` reste à V1.2 comme sur `develop`. Les exports V1.2 n’utilisent que `VERSION_ENGINE_V12`.
- `v12_isolation.py` : refus des clones V1.1 et des ancêtres contenant `.git`/ `sim.db` ; exceptions contrôlées au checkout d'état `kraken-sim-preprod`.
### Infrastructure
- Branche strategy/v1.2 depuis develop + state-v12 dans kraken-sim-preprod. Aucune exécution de cycle ni modification main.
- cycle_v12.py bloqué en l'attente de SPEC et accord ; v12_isolation.py refuse les chemins d'état production ; export_v12.py impose la source V1.2 et des données réelles.
- Workflow sim_v12.yml manuel, pas de cron, pin SHA requis, calcul sans secret, publication distincte et limitée à preprod/state-v12.
- guard.yml : exception explicite strategy/v1.2 pour GPT-6, périmètre stratégie protégeant la V1.1, tests isolation-v12. GARDE_FOUS.md mis à jour.
### Tests et limites
- Tests infrastructure : chemin de stockage, idempotence, export minimal, look-ahead des bougies, intégrité statique du code V1.1. Tests trading/risque/backtest non encore implémentés.
- `v12_acceptance.py` : sept critères de rejet OOS §5 pré-encodés ; refus explicite des métriques absentes ou des runs exploratoires, choix Calmar/Sortino seulement parmi les survivants. `tests/test_v12_acceptance.py` couvre les rejets.
- Aucune performance ni validation économique revendiquée. Première fusion develop et tout workflow sur main soumis à Cyril.

## [UX V1.1.2] — 25/10/2026 15h15 (Paris) — GPT6
### Correctifs critiques
- `dashboard_template.html` : suppression du code JavaScript parasite visible après la fermeture du document HTML (régression introduite avec V1.1.1). Les 2 scripts restent valides.
- `tests/check_template.py` : nouveau contrôle strict interdisant tout contenu après `</html>`. Impact sur les décisions : aucun.
### UX-UI
- `dashboard_template.html` : statut plus compact, versions déportées en deuxième ligne, descriptif technique masqué (données conservées) et graphique capital/BTC alignés sur desktop.
- `dashboard_template.html` : conditions de vente restructurées par actif ; distance au stop, durée restante et décision visibles, détails techniques accessibles à la demande sans modifier le moteur.
- `dashboard_template.html` : décisions groupées visuellement (actions prioritaires, signaux secondaires) et grille financière répartie en quatre familles.
- `dashboard_template.html` : sections backtests et walk-forward explicitement signalées comme analyses techniques avancées ; détail du socle conservé.
### Préproduction
- `render_preprod.py` : remplacement du grand bandeau rouge par l'identification discrète « Kraken Sim PreProd » en tête du site de préproduction ; aucune modification de la production.
- `tests/check_preprod.py` : contrat de marquage discret PreProd, interdiction du bandeau rouge.
### Documentation
- `docs/SPEC_UX.md` : spécifications UX V1.1.2 et registre des corrections ; le schéma HISTORY et le moteur sont inchangés.
- Impact sur moteur, stratégie, stops, positions et décisions financières : **aucun**.

## [UX V1.1.1] — 25/10/2026 15h00 (Paris) — GPT6
### UX-UI
- `dashboard_template.html` : vue d'ensemble hiérarchisée, explication du régime de dernier cycle, comparaison au socle repliable, typographie et mobile améliorés.
- `dashboard_template.html` : filtres et recherche du journal existant, sans toucher aux ordres.
- `dashboard_template.html` : replay historique en lecture seule (schéma 1), chargement mensuel différé, gestion des cycles incomplets et retour au direct.
- `docs/SPEC_UX.md` : usages, sources et limites du replay et de l'affichage UX V1.1.1. Impact trading : aucun.

## [Moteur V1.2] — 25/10/2026 14h45 — Kraken Bot
### Moteur
- `history_export.py` (nouveau) + `cycle_v11.py` : en fin de cycle réussi, ajout d'un instantané dans `state/history/AAAA-MM.json` et mise à jour de `state/history/index.json` (schema_version 1, `docs/HISTORY_SCHEMA.md`). L'appel est protégé par try/except. Impact sur les décisions : aucun.
- Rattrapage idempotent des cycles passés (`complete:false` : portefeuille, décisions, ordres), lancé automatiquement au premier cycle sans historique ou manuellement (`python3 history_export.py`).
### Tests / docs
- `tests/check_history.py` (schéma vérifié sur une copie de sim.db), `docs/HISTORY_SCHEMA.md`, `docs/SPEC_FONCTIONNELLE.md`. Schéma en attente de l'accord de GPT-6.

## [Process] — 25/10/2026 14h15 — Kraken Bot (versions inchangées : Moteur V1.1 · Stratégie V1.1 · UX/UI V1.1)
### Docs / process
- Droits GPT-6 (décision de Cyril) : GPT-6 fusionne lui-même ses PR `ux/*`, `feature/*`, `fix/*` vers `develop` dès guard vert, sans revue Kraken Bot, hors moteur, `VERSION_ENGINE`, `strategy/`, `params.json`, `sim.yml`, `state/`, `sim.db` (ces propositions restent soumises à la revue technique de Kraken Bot). GPT-6 ne pousse ni ne fusionne jamais sur `main` ; `develop` → `main` par Cyril seul après guard vert + « OK prod » GPT-6 et Kraken Bot, revue technique de Kraken Bot à cette étape.
- `GARDE_FOUS.md` (Circuit, Périmètre, guard), `README.md`, `docs/SPEC_UX.md`, modèle de PR mis à jour.
### Infra
- `guard.yml` : nouveau contrôle `perimetre-gpt6` (PR depuis `ux/*`, `feature/*`, `fix/*` : échec si chemins moteur/stratégie/sim.yml/état modifiés). Impact décisions : aucun.

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
