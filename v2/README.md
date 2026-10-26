## Rapport Kraken vérifié — préparation suite à la revue GrokBot

Le collecteur `v2/collect_market_report.py` interroge uniquement les endpoints publics Kraken Ticker, OHLC (60 et 1440 minutes) et Depth (500 niveaux) pour BTC/USDC, ETH/USDC, SOL/USDC et XRP/USDC. Il exclut les bougies non clôturées et calcule EMA20/50, RSI14, ATR14, hauts/bas 30 bougies et liquidité bid/ask ±0,5 % du mid. Il conserve toutes les réponses Kraken brutes avec URL et horodatage UTC dans `v2/reports/AAAA-MM-JJ.kraken.json` et écrit le rapport Markdown correspondant. Aucune clé privée ni ordre réel.

Commande **manuelle** sur un runner avec accès réseau : `python v2/collect_market_report.py --date AAAA-MM-JJ`. La date est une **étiquette de rapport**, les données sont celles de l'instant de collecte, jamais un historique reconstruit. Avant dépôt en PR, vérifier la présence des deux fichiers, les erreurs Kraken, les frais, l'éligibilité EEE et les volumes médians. La collecte n'est pas activée en routine et n'a pas été exécutée dans cette session (réseau inaccessible).

## Routines préparées (non activées)

Le rôle GPT-6 est de préparer les routines et les contrôles, pas de choisir les ordres à la place de Kraken - Bot Crypto. L'issue #33 distingue trois cadences :

| Routine | Cadence prévue | Responsable | État |
|---|---|---|---|
| Rafraîchissement des cotations du dashboard | 10 secondes | Frontend / Kraken public | Déjà en place |
| Rapport d'analyse sourcé | Quotidien avant 18h30 Europe/Paris | GPT-6 | Gabarit + CI prêts, automatisation de rédaction non activée |
| Plan stratégique | Vers 8h et 19h Europe/Paris | Kraken - Bot Crypto | En attente de GrokBot ; jamais généré par le moteur |
| Exécution PAPER | Chaque heure à :40 UTC | GitHub Actions V2 | Routine hors ligne prête, cron désactivé |
| Publication du résultat | Après cycle accepté | Déploiement dédié `state-v2` | Non raccordée, pas de publication |
| Incident, données absentes ou périmées | À chaque tentative | Routine V2 | Rejet et conservation de l'état précédent |

### Routine PAPER `v2/run_cycle.py`

Préconditions bloquantes : plan validé, snapshot Kraken public avec provenance et frais, portefeuille initial vérifié par GrokBot et dernier état validé. En absence d'un seul de ces éléments, le cycle est rejeté sans publication. Le programme génère uniquement un **fichier candidat inédit**, écrit de manière atomique, et ne remplace ni `v2/state.json` ni une branche GitHub. La protection de rejeu et l'intervalle minimal de 45 minutes sont appliqués par le moteur.

```bash
python v2/run_cycle.py \
  --plan /chemin/plan-grokbot.json \
  --market /chemin/snapshot-kraken.json \
  --state /chemin/etat-valide.json \
  --output /tmp/v2-candidate-unique.json
```

Ce n'est pas encore une routine **autonome** : il manque la collecte Kraken V1.2 conforme EEE, la récupération du dernier état `state-v2`, l'archivage des plans et la publication avec clé de déploiement dédiée, puis une validation bout en bout. Il est interdit de remplacer ces entrées par des données de démonstration.

### Routine d'analyse GPT-6

- `v2/reports/TEMPLATE.md` : six sections obligatoires, séparation des faits et opinions, provenance et horodatages UTC, valeurs inconnues `null`.
- `v2/check_report.py` et `.github/workflows/v2_report.yml` : validation des rapports datés soumis en PR, sans rédaction automatique ni données inventées.
- Le rapport doit être produit **avant 18h30 Paris**, sur une branche `reports/*` ou via PR ; le moteur n'en tient jamais compte directement.
- Le plan est créé uniquement par Kraken - Bot Crypto, vers 8h et 19h, après relecture éventuelle du rapport.

**Ne pas activer** le cron V2, les publications, la rédaction quotidienne ou les décisions sans les raccordements, la revue GrokBot et le GO de Cyril. La CI et les tests utilisent des données synthétiques **uniquement en test**, jamais dans l'état public.

# Kraken Sim V2 — Passation GrokBot

**État au 26/10/2026 : préparation technique, PAS de simulation autonome active.**
Le dashboard V2 est publié, les prix publics Kraken sont visibles. Le moteur `v2/engine.py` reste volontairement HOLD. Le workflow V2 est manuel, sans cron. Aucun ordre réel autorisé.

## Cadence et données marché — exigence V2 (26/10/2026)

**Cadence demandée : 10 secondes, pas 5.** Les cinq cotations BTC/USDC, ETH/USDC, BNB/USDC, XRP/USDC, SOL/USDC proviennent du flux public Kraken WebSocket v2 en continu ; le dashboard rafraîchit les cours affichés **toutes les 10 secondes**. Le dashboard recharge aussi `v2/state.json` **toutes les 10 secondes**. Les courbes 24 h proviennent de bougies OHLC Kraken (5 min + 1 min), mises à jour périodiquement, et des ticks réellement reçus.

**À intégrer par GrokBot :** la cadence de rafraîchissement du dashboard est **10 secondes**, tandis que l'exécution PAPER est prévue **à :40 chaque heure**, après GO, après validation de la faisabilité, des limites API et de la fraîcheur des sources. Chaque cycle doit utiliser les prix Kraken les plus récents et sourcés ; le dashboard ne doit pas servir de source d'exécution. Chaque état publié doit porter son horodatage réel `updated`, et le moteur doit refuser les données trop anciennes. Aucune extrapolation de prix, d'ordre, de portefeuille ou de rendement.

**Important :** actualiser le navigateur toutes les 10 secondes n'implique pas que le moteur calcule ou publie effectivement un nouveau cycle toutes les 10 secondes. Le workflow V2 actuel est toujours sans cron, et la stratégie reste à brancher. Le déclenchement d'une cadence de 10 secondes exige un orchestrateur compatible (un cron GitHub Actions n'est pas adapté à une fréquence de 10 secondes), un mécanisme anti-chevauchement et un GO explicite. Ne pas activer le trading réel.

Les 12 scénarios d'acceptation du CDC §10 sont automatisés dans `v2/test_acceptance_v2.py` avec des fixtures synthétiques ; ils ne remplacent pas un essai de bout en bout sur données Kraken vérifiées.

## Revue PR #34 — correctifs demandés par GrokBot (26/10/2026)

La spécification normative est le commentaire du CDC dans l'issue #33, et non les anciens exemples du présent README. **Les allocations sont des fractions de l'enveloppe** : 0,30 signifie 30 % des 2 000 USDC, et non 30 % du portefeuille total. Le capital de référence 6 605,10 USDC est un garde-fou du CDC, **pas une initialisation automatique de `state.json`**.

- `v2/guardrails.json` contient G5/G6/G7/G10 et les autres limites du CDC. **La PR #34 modifie ce fichier et reste bloquée sans le label `cyril-approved`** et un titre commençant par `[GUARDRAILS]`. Ne pas contourner le contrôle.
- `v2/plan_contract.py` valide `author`, `regime`, `targets` (somme 1 ±0,001), zones, stops, take-profits, expiration 36 h, ordre max et régime cash. `v2/plan.schema.json` décrit le format. Le plan actif réel `v2/plan.json` doit être créé exclusivement par GrokBot.
- `v2/engine.py` calcule des **candidats PAPER hors ligne** à partir d'un plan et d'un snapshot de marché publics Kraken sourcés ; il simule la traversée du carnet en taker, les frais maker/taker non nuls et les ordres maker uniquement sur preuve de franchissement ultérieur ; il limite les achats et journalise les refus. Il exige un portefeuille vérifié et le coût de revient vérifié des positions existantes.
- Le coupe-circuit G10 est un drawdown **absolu de 300 USDC** depuis le pic d'equity. La fraîcheur G11 maximale du snapshot est **10 minutes**, distincte du rafraîchissement du dashboard **10 secondes**.
- `v2/check_pr_policy.py` bloque les modifications V1/V1.2, exige la documentation et le CHANGELOG, et protège les garde-fous. La CI `sim_v2.yml` compile et lance les tests sans appeler le moteur sans arguments ; le cron `40 * * * *` reste commenté.
- `VERSION_ENGINE_V2` et `VERSION_UX_V2` : versions indépendantes V2.0.1.

**Limites restant à lever avant activation :** le collecteur public Kraken V1.2 et la conformité EEE ne sont pas encore raccordés en lecture seule ; le snapshot est un contrat d'entrée, non une collecte automatique. Le traitement des ordres maker nécessite un vrai flux ultérieur horodaté et le timeout effectif, non une simple liste de prix ; l'archivage immuable des plans, la publication atomique sur `state-v2`, la gestion des achats en attente, la vérification CI complète et les 12 tests d'acceptation de bout en bout restent à terminer. **Aucune simulation autonome ni publication n'est activée.**

Exécution locale avec fichiers vérifiés (ne pas publier de données synthétiques) :

```bash
python -m unittest discover -s v2 -p 'test_*.py' -v
python v2/engine.py --plan /chemin/plan-grokbot.json --market /chemin/snapshot-kraken.json --state /chemin/etat-verifie.json --output /tmp/v2-candidate.json
```

## Cahier des charges GrokBot — issue #33 (26/10/2026)

Source : https://github.com/cyrillaferrere/kraken-sim/issues/33

**Architecture retenue par GrokBot :** plan libre écrit 1–2 fois/jour par GrokBot ; exécution PAPER prévue toutes les heures à **:40**, indépendante des sessions GrokBot. Le dashboard et les cotations restent actualisés **toutes les 10 secondes**. Ces deux cadences ne doivent pas être confondues.

**Garde-fous demandés dans l'issue #33 (valeurs fournies par GrokBot, non inventées par GPT-6) :** plafond investi 2 000 USDC, capital de référence déclaré 6 605,10 USDC (à confirmer contre les données réelles avant initialisation), 40 % max par actif, profondeur au moins 3× l'ordre à ±0,5 %, spread ≤0,3 %, kill-switch drawdown 15 % par défaut, spot long, USDC uniquement, pas de clé privée, aucune exécution réelle. Les valeurs de référence ne sont **pas injectées dans `v2/state.json`**.

**Préparation sur PR `feature/v2-plan-execution-issue33` :**
- `plan_contract.py` : validation stricte du plan (actifs, poids, floor USDC, zones, expiration ≤36 h) ; fonction de repli vers le dernier plan validé.
- `engine.py` : **précontrôle en lecture seule** du plan et du snapshot Kraken sourcé et récent (≤10 min), du portefeuille, du plafond et du drawdown. produit un candidat PAPER, sans publication ni appel Kraken privé.
- `test_plan_contract.py`, `test_engine_preflight.py` : tests de rejet et de sécurité.
- `index.html` : encart plan actif, justification, expiration, poids cibles/réels et écarts ; ne montre le plan que si `data_source=grokbot_verified`.
- `sim_v2.yml` : tests PR ; **pas de cron ni de publication automatique**.

**Restant indispensable avant GO :** collecteur Kraken réutilisé de V1.2 (prix/carnet/frais, vérification paires UE), calcul des décisions à partir des zones et pondérations, contrôles de profondeur et spread *par ordre*, stops, publication atomique, conservation du dernier plan valide, orchestrateur horaire, tests end-to-end. Un plan absent ou invalide ne doit jamais déclencher d'achat. La PR ne doit pas être fusionnée sans revue et CI.

## 1. Ce qui est déjà prêt

- Dashboard `v2/index.html` : cinq cours USDC, courbe Kraken 24 h dépliable, portefeuille, performance, allocations, signaux, décisions, score.
- `v2/state.json` : état public **en attente**, sans capital ni résultats inventés.
- `v2/paper_executor.py` : adaptateur PAPER **exécutable hors ligne** ; vérifie les entrées, applique les décisions, calcule cash/positions/valorisation/P&L, refuse découvert et vente à découvert, conserve les ordres et l'historique. Il ne décide pas des trades.
- `v2/test_paper_executor.py` : tests de comptabilité, garde-fous et rejets.
- `.github/workflows/sim_v2.yml` : contrôle manuel, **aucun cycle automatique**.

## 2. Contrat d'entrée : GrokBot -> adaptateur PAPER

GrokBot est l'unique fournisseur des **vraies valeurs** : capital initial (solde USDC confirmé), horodatage, prix de marché, décisions, quantités, prix d'exécution, frais, signaux et bilan des trades clôturés. Aucun chiffre ne doit être estimé par GPT-6.

Un cycle JSON doit respecter cette structure (les chaînes `<...>` sont des **placeholders**, pas des valeurs à publier) :

```json
{
  "data_source": "grokbot_verified",
  "cycle_id": "<identifiant unique>",
  "ts": "<date UTC ISO-8601 terminée par Z>",
  "initial_usdc": "<solde initial confirmé, requis seulement au premier cycle>",
  "prices": {
    "BTC": "<cours BTC/USDC confirmé>",
    "ETH": "<cours ETH/USDC confirmé>"
  },
  "decisions": [
    {
      "asset": "BTC",
      "side": "BUY",
      "qty": "<quantité PAPER décidée>",
      "price": "<prix d'exécution PAPER confirmé>",
      "fee": "<frais PAPER confirmés en USDC>"
    }
  ],
  "signals": [],
  "closed_trades_summary": {
    "source": "grokbot_verified",
    "net_wins": "<entier calculé par GrokBot>",
    "net_losses": "<entier calculé par GrokBot>",
    "net_flats": "<entier calculé par GrokBot>"
  },
  "closed_trades_history": []
}
```

**Important :** l'exemple est structurel et n'est pas directement exécutable. Les valeurs `<...>` doivent être remplacées par des données vérifiées. Pour un cycle HOLD, `decisions: []`. `closed_trades_summary` et `closed_trades_history` peuvent être omis tant que GrokBot n'a pas de bilan validé. Au-delà du premier cycle, `initial_usdc` peut être omis ; s'il est présent, il doit correspondre exactement au capital initial déjà enregistré. Fournir un prix `prices` pour **toutes les positions détenues** à chaque cycle, même sans ordre.

Le prix `price` d'une décision est un **prix d'exécution PAPER** déterminé par GrokBot, distinct du prix de valorisation `prices`. Les frais `fee` sont en USDC et doivent intégrer les hypothèses validées ; l'adaptateur n'invente ni frais ni slippage. Spot seulement, sans levier, sans short.

### Traitement local, sans publication

```bash
python -m unittest discover -s v2 -p 'test_*.py' -v
python v2/paper_executor.py --input /chemin/cycle-grokbot.json --state v2/state.json --output /tmp/kraken-v2-result.json
```

La sortie est un **candidat** d'état. L'adaptateur interdit d'écraser directement le fichier d'entrée `state.json`. GrokBot doit inspecter et valider le candidat avant toute publication atomique vers `v2/state.json` sur la branche autorisée. Pour le cycle suivant, utiliser le dernier état validé. Ne jamais publier les données des tests.

## 3. Contrat de sortie : état V2 -> dashboard

L'interface ne montre les données financières que lorsque `data_source === "grokbot_verified"`. Champs utilisés :

- `initial`, `cash`, `equity`, `pnl_pct`, `fees`, `cycles`, `updated`, `status`.
- `positions` : objet `{ "BTC": quantité }` ; `position_values` : valeurs USDC par actif.
- `orders` : tableau d'objets `{ts, side, asset, qty, price, fee}`.
- `history` : tableau `{ts, equity, cash}` pour les graphiques.
- `signals` : objets `{asset, signals: {short, medium, long}, target_pct}`. Les signaux sont des scores transmis par GrokBot, pas calculés par l'adaptateur.
- `closed_trades_summary` : `{source:"grokbot_verified", net_wins, net_losses, net_flats}` avec entiers non négatifs.
- `closed_trades_history` : `[{source:"grokbot_verified", net_pnl: ...}]` pour l'évolution du score.
- `last_cycle_id` et `processed_cycle_ids` : suivi de tous les cycles traités pour éviter les doublons.\n- `_ledger` : soldes et positions en chaînes décimales exactes pour les calculs d'un cycle à l'autre (ne pas supprimer).

La jauge de score est calculée **seulement à partir des trades clôturés** : +1 victoire nette, −2 défaite nette, 0 égalité. Aucun score inféré des BUY/SELL bruts.

## 4. Ce qui reste à GrokBot

1. Fournir les données réelles initiales, leur provenance et leur fraîcheur ; vérifier qu'aucune donnée privée ou clé API ne soit écrite dans GitHub Pages.
2. Brancher **sa stratégie opportuniste V2** (défensive en USDC si nécessaire, offensive quand les signaux le justifient), y compris choix des actifs, horizons, règles et critères de rejet ; aucune valeur de seuil n'est prédéfinie ici.
3. Produire le cycle JSON validé à chaque itération et l'exécuter avec `paper_executor.py`. Traiter toute exception comme **rejet du cycle**, sans publication.
4. Valider l'exactitude des frais, prix d'exécution, cash, equity, signaux, P&L net et trades clôturés ; tester les reprises et les rejets.
5. Installer la publication contrôlée du résultat et la cadence de cycles voulue, **seulement après GO explicite**. Ne pas toucher aux flux V1/V1.2, ne pas activer de trading réel.

## 5. Sécurité et limites à connaître

- `grokbot_verified` est un **marqueur déclaratif**, pas une preuve cryptographique. GrokBot doit réellement contrôler les sources avant de l'utiliser.
- L'adaptateur ne contacte pas Kraken et n'a besoin d'aucune clé API ; les cotations publiques du dashboard sont indépendantes du portefeuille.
- Les montants sont calculés en `Decimal` et conservés dans `_ledger` sous forme de chaînes décimales exactes ; les champs numériques publics servent au dashboard. **Valider la comptabilité de bout en bout avant activation**.
- La protection contre les doublons vérifie tous les identifiants déjà traités et l'ordre chronologique. Une publication concurrente nécessite aussi une protection transactionnelle côté orchestrateur.
- Le backtest, le kill-switch de l'orchestrateur, le contrôle de fraîcheur des données, le suivi des ordres clôturés et les tests end-to-end restent à finaliser/valider.
- **Aucun automatisme ni ordre réel ne doit être déclenché par la présence de ces fichiers.**

## 6. Liens

- Production : https://cyrillaferrere.github.io/kraken-sim/v2/
- Préproduction : https://cyrillaferrere.github.io/kraken-sim-preprod/v2/
- Dépôt : https://github.com/cyrillaferrere/kraken-sim

## Garde-fous V2 (révision du 26/10/2026, Kraken - Bot Crypto)

Plafond investi 4 000 USDC, coupe-circuit 600 USDC depuis le pic, 40 % max par actif, spread ≤0,3 %, profondeur ≥3×, 6 ordres/cycle, 20/24 h. Les tests utilisent `v2/test_guardrails_fixture.json` via `V2_GUARDRAILS_PATH`, variable interdite en production.

## Collecte automatique (26/10/2026)

Tous les jours vers 17h Paris, GitHub collecte les données publiques Kraken et les dépose sur la branche `data-v2`, dans `reports/AAAA-MM-JJ.md` et `.kraken.json`. GPT-6 part de ces fichiers et ne revérifie plus les prix lui-même.
