# Kraken Sim V1.2 — état de livraison technique (25 octobre 2026)

**Branche** : `strategy/v1.2` ; **PR** : #7 EN BROUILLON vers `develop`. **AUCUNE FUSION, aucun cycle V1.2 activé (uniquement des cycles synthétiques en tests locaux/CI), aucun ordre réel, aucun workflow V1.2 sur main.**

## Versions et préproduction

- Moteur V1.1 : `VERSION_ENGINE=V1.2` inchangé, `sim.yml` et `sim.db` intacts.
- Moteur expérimental V1.2 : `VERSION_ENGINE_V12=V1.3`, stratégie `STRATEGY_VERSION=V1.2`. Aucune confusion des ordres.
- Etat préprod : branche `state-v12` du dépôt `kraken-sim-preprod`, sans portefeuille fictif inventé.
- `sim_v12.yml` présent **uniquement dans la PR**, manuel, sans cron, code SHA à épingler après accord de Cyril, calcul sans secret, publication séparée vers `state-v12`, host key GitHub épinglée.
- `cycle_v12.py --cycle` demeure **bloqué par conception**. `--dry-run --out <chemin externe>` exécute seulement un scénario de 30 jours synthétiques sans aucun réseau ni ordre réel.
- `render_preprod.py` ne sélectionne le template V1.2 que si `PREPROD_V12_READY=1` et si la source est réellement V1.2. Le site actuel reste V1.1 en lecture seule par défaut.

## Fonctionnalités développées dans la PR

1. Paramètres indépendants et signaux des quatre candidats A Donchian, B dual momentum, C BTC/ETH tendance et D V1.1 hebdomadaire.
2. D réutilise les indicateurs d'origine `backtest.ind` de V1.1, notamment ATR14, EMA et momentum ; **le replay complet V1.1 ne l'est pas**.
3. Gestion PAPER cash/positions spot sans levier ni short, frais, spread, slippage, stop, kill-switch, Maker partiel / Taker et réduction de positions.
4. Univers point-in-time sur chandelles journalières réelles clôturées ; rejet des chandelles imputées, des positions valorisées avec prix périmés, et traitement conventionnel des délistages documentés.
5. Import des CSV Kraken OHLCVT et contrôle SHA-256. Mode officiel refuse tout manifeste n'attestant pas explicitement la couverture historique des actifs listés et délistés.
6. Protocole de backtest hors ligne : fenêtre 12 mois IS / 3 mois OOS, grille IS, OOS combinées, sensibilité aux paramètres et critères de rejet `v12_acceptance.py`.
7. Baselines séparées : BTC buy-and-hold, portefeuille BTC/ETH/XRP mensuel et cash, en tenant compte des frais.
8. Export V1.2 avec les clés du contrat, données inconnues à `null`, source et horodatage UTC/Paris ; template V1.2 indépendant testable localement, sans réseau.
9. Tests sur l'isolation et tous les fichiers `state/**`, version moteur, boucle de comptes, remises en cash, invariance aux données futures des quatre candidats, sécurité du workflow.

## Étapes données / rejeu engagées (25/10/2026)
- `fetch_kraken_history_v12.py` ajouté : liste officielle des cinq parties SHA-256 épinglées, CLI manuel avec option `--download` obligatoire, reprise sur interruption, assemblage ZIP avec checksum officiel, possibilité d'associer le T3 en conservant son statut de hash local non attesté indépendamment ; **aucune archive de plusieurs Go téléchargée**.
- Vérifications complémentaires : domaine et chemin d'origine Kraken exacts, valeurs OHLC non finies rejetées, timestamp entier et ZIP trimestriel valide ; tests négatifs dédiés.
- [Mode d'emploi pour préparer les archives sur un disque externe](TELECHARGEMENT_KRAKEN_V1_2.md). Le `MANIFEST.json` officiel validé est toujours absent, car la vérification des listings historiques est requise.

- `prepare_kraken_history_v12.py` et tests : fusion/déduplication des CSV officiels après téléchargement sur un stockage externe, vérification SHA-256 et contrôle des paires. Le résultat demeure `MANIFEST.draft.json` tant que la couverture historique n'est pas prouvée.
- `v12_v11_replay.py` et tests : reproduction déterministe du comportement réel du moteur V1.1 sur une fixture d'API synthétique, sans réseau ni écriture vers la production. **Ce n'est pas une baseline historique**.
- [Procédure sources et contraintes](DONNEES_ET_REPLAY_V1_2.md), y compris les limites d'une comparaison OHLC quotidienne.

## Nouvelle orientation produit — autonomie et apprentissage Grok Bot
Cyril confirme que la finalité est de démontrer la fiabilité de Grok Bot, qui doit prendre des décisions de trading autonome en PAPER et apprendre avec des données d'exécution réelles et historisées, avant tout accès éventuel à son portefeuille réel aujourd'hui en USDC.

La [vision d'architecture autonomie et apprentissage](VISION_AUTONOMIE_APPRENTISSAGE.md) distingue **agent décideur**, **contrôleur de risque non modifiable par l'agent**, **moteur d'exécution paper**, et **évaluateur / promotion de nouvelles politiques**. Les stratégies A/B/C/D deviennent des comparateurs ; elles ne limitent pas Grok à une simple rotation automatique entre quatre algorithmes.

**Changement de priorité (non déployé)** : finaliser d'abord la boucle de décision autonome PAPER, le suivi des USDC, la couche de risque, les journaux et la preuve d'intégration Grok ; conserver les archives massives et les backtests rétrospectifs exhaustifs en chantier complémentaire. Aucune décision de commencer un cycle ou d'activer un workflow n'est prise par le présent document.

## Développement du contrôle autonome PAPER (nouvelle orientation)
- Le contrat de décision Grok est lié aux quatre candidats **A/B/C/D de la SPEC V1.2**, et non à une stratégie libre inventée en cours de route.
- `v12_autonomy.py` refuse les décisions qui ne passent pas les signaux ou les limites de risque. `v12_grok_gateway.py` enregistre les résultats sans jamais envoyer d'ordre. `v12_learning.py` stocke des événements pour comparer rétrospectivement les décisions et proposer des politiques shadow.
- **Grok n'est pas encore connecté** à ces modules, le compte PAPER autonome ne tourne pas, aucune boucle d'apprentissage n'est activée. Documentation : [GROK_AUTONOME_V12_ETAPE1.md](GROK_AUTONOME_V12_ETAPE1.md).
- La première exécution restera soumise à l'accord distinct de Cyril après tests de l'exécuteur et contrôles de sécurité.

## Revue Grok Bot : six P1 livrées en DRY-RUN, pas en fonctionnement autonome réel
- **P1-A** : séparation admission de l'IT et exécution au cycle suivant, avec quotes récentes réévaluées et TTL compatible avec le cron espacé.
- **P1-B** : exécuteur PAPER persistant indépendant, idempotence des décisions et cycles, maker/taker, sorties déterministes A/B/C/D et liquidation d'urgence.
- **P1-C** : limites, pic d'equity, kill-switch et politiques actifs **chargés de la base du moteur**, jamais du document Grok.
- **P1-D** : référence USDC HOLD sur quotes USDC/USD observées (pas de peg imposé).
- **P1-E** : outcomes J+1/J+7/J+30 (MAE, PnL net portefeuille, frais, USDC, BTC) calculés depuis les marks par le moteur.
- **P1-F** : candidate C soumise au plafond global 90 % ; test explicite.
- [Procédure, limites et commande `--dry-run`](REVIEW_GROK_P1_30J_V12.md). **Ni Grok Bot, ni Kraken public, ni GitHub Issues ne sont encore connectés au moteur autonomisé.** Les données de 30 jours sont inventées exclusivement pour les tests techniques.
- La refonte UX de préprod reste un chantier distinct après finalisation du contrat de données.

## Raccordement API Kraken publique / issues Grok (code non activé)
- Collecteur `v12_kraken_public.py` : API publiques Kraken uniquement, quote USDC/USD, historique OHLC journalier clos, préfiltre volume avant filtres V1.2.
- Lecteur `v12_grok_issues.py` : auteur vérifié par ID numérique, label, JSON, SHA. `v12_live_bridge.py` raccorde la lecture avec `PaperEngine`; les protections de risque tournent avant toute requête GitHub et ne dépendent pas de Grok.
- Tests déterministes hors réseau `tests/test_v12_real_bridge.py`. **Aucun cron, aucune IT Grok programmée, aucun test effectif sur cours live n'ont été exécutés par la CI.**
- [Préparation avant activation](BRANCHEMENT_KRAKEN_GROK_V12.md). Le dashboard V1.2 préprod est toujours à revoir.

## Blocages à traiter avant tout backtest OFFICIEL

- **Historique exhaustif manquant** : aucun dossier contenant tous les CSV Kraken USD historiques, leur manifeste SHA-256, le catalogue de cotation et les cryptos délistées n'a été fourni à la PR. Impossible de produire honnêtement un bilan financier validé.
- **Baseline V1.1 non reproduite** sur les mêmes données et conditions de coûts. La parité d'indicateurs D n'est pas la parité complète des cycles V1.1, positions initiales et ordres en attente. Le moteur refuse la sélection d'une stratégie sans cette preuve.
- **Stress tests et vérification finale d'exécution** à mener sur de vraies données 2021, 2022, 2024 et récentes, y compris coûts de maker non rempli, slippage et actifs délistés. Les prix du dernier trade en cas de delisting constituent une hypothèse pouvant surestimer la valeur réellement récupérable.
- **Moteur de cycles V1.2 durable** non intégré : avant d'activer `cycle_v12.py`, il faut satisfaire les critères d'acceptation, confirmer les résultats et obtenir l'autorisation de Cyril.
- **Décisions séparées de Cyril** : (1) première fusion `strategy/v1.2` vers `develop` après revue Grok Bot, (2) ajout du workflow sur `main`, (3) premier cycle V1.2, (4) activation éventuelle d'un cron.

## Commandes de contrôle hors ligne

```bash
python3 -m unittest discover -s tests -p 'test_v12_*.py' -v
python3 -m unittest discover -s tests -p 'test_v11_nonregression.py' -v
python3 tests/check_template.py
```

Ces tests vérifient le **code et ses hypothèses**, pas une performance financière réelle. Les tests CI actuellement verts ne constituent ni un bon pour fusion ni un bon pour déploiement.

Voir la revue de Grok Bot dans la PR #7 et la spécification `docs/SPEC_STRATEGIE_V1_2.md`.
