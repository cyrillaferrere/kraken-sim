# Kraken Sim — vision cible : Grok Bot autonome et apprentissage continu

**Décision produit (25/10/2026).** La finalité de Kraken Sim est de vérifier en **paper trading** si Grok Bot peut être un gestionnaire de portefeuille crypto autonome, avant toute éventuelle délégation réelle du portefeuille aujourd'hui détenu en USDC. La fiabilité, la gestion des risques et la traçabilité comptent autant que le rendement.

**Cadence corrigée :** Grok intervient par IT, librement, **potentiellement une dizaine de fois par jour ou davantage** ; aucune IT quotidienne unique ni horaire de 02h30 n'est imposé. **Grok dispose déjà d'un connecteur Kraken** et reste l'unique décideur stratégique ; le moteur PAPER tient les comptes, contrôle les risques et vérifie indépendamment les prix. Dix IT ne signifient pas dix ordres.

Cette décision **complète** la SPEC V1.2 A/B/C/D de Grok Bot sans la réécrire. Les stratégies A/B/C/D restent des modèles de référence et de comparaison ; elles ne constituent pas nécessairement la décision autonome de l'agent.

**État d'autorisation :** aucune clé privée Kraken, aucun ordre réel, aucune mise en service V1.2 ni cycle V1.2 autorisé à ce stade. La PR #7 reste en brouillon. Cyril seul autorise, en étapes distinctes, la première fusion vers develop, l'installation/activation du workflow, le premier cycle papier, et plus tard toute mise en réel. Aucune promotion automatique de PAPER vers LIVE.

## 1. Trois fonctions qui ne doivent pas être confondues

### A. Grok Bot — décisionnaire autonome dans le cadre autorisé

- À des horaires définis, reçoit exclusivement des données de marché horodatées, clôturées ou qualifiées de temps réel (quotes, spread, profondeur si disponible), positions, cash, ordres, frais, contraintes et performance.
- Analyse le régime, décide **BUY / SELL / HOLD / CANCEL** et propose la taille, limite, horizon, confiance et justification. Il peut décider de rester à 100 % en cash : c'est une décision légitime.
- Émet un **objet de décision typé**, non du texte libre exécutable : `cycle_id`, `market_data_asof`, `model_id`, `policy_version`, `decision_id`, `asset`, `side`, `size`, `order_type`, `max_slippage`, `expected_risk`, `reason`, `confidence`, `ttl`.
- Écrit les informations nécessaires pour comprendre pourquoi il a agi, mais ne peut pas réécrire les logs historiques ni les règles de sécurité.
- La véritable autonomie exige **un planificateur externe** et une interface d'invocation persistante du moteur Grok (API ou service vérifié). Une conversation de chat seule n'exécute pas des décisions 24 h/24 ni ne conserve automatiquement un état d'apprentissage vérifiable. Les capacités et conditions d'intégration de Grok Bot restent à vérifier, sans présumer qu'une API équivalente est disponible.

### B. Contrôleur de risque déterministe — décide si l'ordre est autorisé

- Valide **avant chaque ordre** : fraicheur des prix, statut de cotation, asset allowlist/denylist, cash disponible, taille minimale, exposition par actif et globale, concentration/corrélation, drawdown, disponibilité du carnet/spread, frais et limites de liquidité, cadence, durée de vie de l'ordre et doublons.
- Rejette toute décision mal formée ou impossible, demande de données périmées, demande de levier ou de retrait, proposition dépassant les plafonds, ou tentative de Grok de modifier ses propres limites.
- Les règles, permissions, seuils critiques et coupe-circuits sont **séparés de l'agent**, versionnés, testés et ne peuvent être modifiés par son processus d'apprentissage. Arrêt d'urgence manuel, mise en pause automatique et reprise contrôlée.
- Fail-closed : si Grok, les données ou l'exécuteur sont indisponibles, **aucune nouvelle prise de risque** ; seules les actions de sécurité définies par la politique restent possibles. Chaque refus est enregistré.

### C. Exécuteur et comptable papier — reproduit les ordres

- Moteur d'ordres/idempotence indépendant : validation de `decision_id`, ordre unique, états `proposed / rejected / pending / partially_filled / filled / cancelled / expired`, restitution des espèces, frais maker/taker, spread, slippage, exceptions.
- Portefeuille PAPER et journaux append-only totalement séparés de la production V1.1. Journalisation de toutes les décisions, **y compris HOLD, refus, données manquantes et périodes d'inactivité**, afin d'éviter un bilan biaisé sur les seuls trades remplis.
- Comparateurs : (1) **USDC conservés**, (2) V1.1, (3) BTC passif, (4) stratégies A/B/C/D aux mêmes coûts et dates. Le cash papier initial de 6 605,10 USD est une hypothèse historique de simulation, **pas une preuve de quantité d'USDC actuellement détenue**. Une simulation fidèle d'un compte en USDC doit documenter la valorisation USDC/USD, la conversion et les frais éventuels ; ne pas supposer automatiquement un cours de 1,0000 USD.

## 2. Ce que signifie « apprendre au fil du temps »

Il ne s'agit **pas** d'affirmer que les poids internes du modèle Grok changent spontanément. L'apprentissage du système est rendu mesurable par des traces persistantes et par la comparaison des améliorations de sa politique décisionnelle.

Boucle d'apprentissage :
1. **Décision** : conserver l'état du marché à `t`, l'information réellement disponible, la prévision/hypothèse, les contraintes et l'action proposée.
2. **Observation** : constater à `t+1`, puis à des horizons définis, l'ordre réellement rempli, la performance nette, le drawdown, les erreurs d'exécution et la trajectoire **sans transaction**.
3. **Évaluation** : attribuer sans regarder le futur ce qui relevait du signal, du risque, des coûts, du timing et des refus ; comparer à la politique précédente et aux benchmarks.
4. **Proposition d'amélioration** : produire une nouvelle **version candidate de politique** (instructions, priorités, tailles autorisées dans une plage non critique, critères de filtre ou paramètres) et sa justification. Les propositions sont archivées ; **aucune réécriture automatique des garde-fous ni du code de trading**.
5. **Challenge** : tester la candidate sur des observations hors entraînement, puis en *shadow trading* parallèle sur des marchés futurs. Mesurer stabilité, sensibilité, frais, incidents, gain et risque.
6. **Promotion** : la politique candidate peut devenir la nouvelle politique **PAPER** uniquement si elle passe des critères de promotion préfixés et reproductibles. Un mécanisme d'approbation explicite par Grok Bot + Cyril sera défini pour les changements sensibles ; toute promotion vers LIVE exige **toujours l'autorisation explicite de Cyril**.
7. **Retour arrière** : conserver les versions antérieures, métriques, décision de promotion et capacité de rollback de la politique après toute dégradation.

Le système peut collecter de l'expérience en continu, mais il ne doit **pas** optimiser uniquement sur les trades gagnants ni laisser les mêmes observations servir simultanément à l'entraînement et à la validation. Une période trop courte ou trop favorable n'établit pas la fiabilité.

## 3. Indicateurs de fiabilité (observable par Cyril)

- Équité nette PAPER et rendement net **après frais**, comparés aux USDC conservés, à V1.1, BTC et aux autres candidats, à dates et conditions identiques.
- Drawdown courant et maximal, volatilité, risque de concentration, exposition moyenne, turnover, coût des ordres et coûts de conversion éventuels USDC/USD.
- Nombre de décisions proposées / validées / rejetées / exécutées, refus et raisons ; données périmées ; erreurs, downtime, doublons empêchés ; taux de décisions sans trade.
- Qualité de la décision : résultat selon horizon choisi, impact des coûts, prévisions vs résultats et comparaison à l'alternative HOLD.
- Versions d'agent/politique, modifications proposées, régressions, périodes indépendantes, tests de marché baissier ou de forte volatilité.
- Un statut non ambigu : `NE PAS DÉLÉGUER`, `PAPER EN COURS`, `PAPER ÉVALUÉ`, `CANDIDAT LIVE SOUMIS À CYRIL` ; **aucun badge « prêt pour le réel » automatique**.

## 4. Étapes de réalisation compatibles avec la PR #7

**Phase 1 — Banc paper autonome (non autorisé à démarrer encore).** Finaliser l'invocation réelle de Grok (disponibilité API/service à vérifier), schéma de décision, contrôleur de risque déterministe, exécuteur paper idempotent, log append-only, portfolio USDC et dashboard de fiabilité. Vérifier ces fonctions sur fixtures sans lancer le bot.

**Phase 2 — Expérience prospective.** Après l'accord explicite de Cyril pour le premier cycle, lancer Grok en PAPER, avec les stratégies A/B/C/D comme *challengers*, la même date de départ et des coûts communs. Pas de gros téléchargement historique préalable obligatoire ; récupérer assez de bougies publiques récentes pour les indicateurs et les mettre en cache. Le volume disponible via l'API doit être vérifié pour chaque fenêtre requise.

**Phase 3 — Apprentissage contrôlé.** Générer les bilans périodiques, versions candidates, tests shadow, promotions PAPER tracées selon une politique de changement validée ; mesurer la dérive, les régimes de marché, les risques et le gain véritablement hors échantillon.

**Phase 4 — Préparation d'un éventuel réel.** **Pas automatique** : seulement si preuves prospectives solides, contrôles de risques audités, journal des incidents satisfaisant et consentement de Cyril. Déploiement progressif avec accès exchange limité au trading, **sans permission de retrait**, limite de capital réellement autorisé, supervision et coupe-circuit indépendant. Autorisation transactionnelle répétitive possible *uniquement à l'intérieur de ce mandat borné* ; aucune autorisation générale de déplacer le patrimoine.

## 5. Contrats impératifs pour le développement

- Séparer **signal IA**, **validation du risque**, **exécution** et **évaluation**. Une réponse LLM n'a jamais accès directement à une commande de trading ou à une clé.
- Toute interface d'ordre est en PAPER par défaut ; le LIVE sera un module distinct, absent ou entièrement désactivé tant que le passage en réel n'aura pas été approuvé.
- Les garde-fous existants dans `GARDE_FOUS.md` restent prioritaires ; le présent document ne modifie ni `docs/SPEC_STRATEGIE_V1_2.md`, ni `strategy/params.json`, ni `VERSION_ENGINE` partagé, ni `main`, ni les conditions d'approbation déjà définies.
- Ajouter des tests de rejet sur données manquantes, décisions illégales, doublons d'ordres, tentatives d'augmenter le risque, absence de modèle disponible, source de données expirée, reprise après panne, et impossibilité de transformer une promotion PAPER en ordre LIVE.
- Les quatre candidats quantitatifs ne remplacent pas Grok ; ils servent de **comparateurs et garde-fous d'évaluation**. Les variantes Grok ne peuvent pas être déclarées rentables sur la seule base d'une optimisation rétrospective.

**Décision centrale : autonomie de Grok pour les choix de trading PAPER et apprentissage observable, sans autonomie pour modifier les protections financières ni pour autoriser l'accès à l'argent réel.**
