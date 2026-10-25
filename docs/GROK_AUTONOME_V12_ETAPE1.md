# Kraken Sim — Phase autonome Grok sur la stratégie V1.2

**État : code préparatoire dans la PR #7 — pas de cycle ni de négociation LIVE.** Date : 25 octobre 2026.

## Principe retenu

Le moteur suit **exclusivement la stratégie V1.2 préenregistrée par Grok Bot** dans `docs/SPEC_STRATEGIE_V1_2.md` et `strategy/v1_2/params.json`. Grok est le décideur, pas un générateur de stratégies non contrôlées :

- Il choisit un candidat **A Donchian**, **B dual momentum**, **C BTC/ETH tendance** ou **D V1.1 hebdomadaire corrigée**, puis propose `BUY`, `SELL`, `HOLD` ou `CANCEL`, avec quantité, justification, version de politique et horaire.
- Le calcul des signaux et plafonds reste **déterministe et indépendant de sa réponse** ; Grok ne peut pas s'accorder de levier, augmenter le poids autorisé, ignorer les frais, contourner un kill-switch ou activer une nouvelle politique.
- `BUY` n'est autorisé que si l'actif passe les signaux du candidat, l'univers à la date considérée, les règles de calendrier, les plafonds individuels/globaux, les contrôles de corrélation A/B/D, les minima d'ordre et la disponibilité du cash.
- Une vente n'est permise que pour un actif réellement détenu et une quantité ne dépassant pas la position. `HOLD` est reconnu sans créer d'ordre. `CANCEL` reste refusé tant que le carnet des ordres en attente n'est pas relié au moteur.
- Les données de marché sont fournies **par le collecteur de confiance**, pas par Grok. Bougies quotidiennes clôturées, quotes récentes, bid/ask cohérents, spread et exposition vérifiés. Des données indisponibles impliquent le refus des achats et des ordres qui ne peuvent être vérifiés.

## Modules livrés

1. **`v12_autonomy.py`** : contrat de décision strict (aucun champ étranger autorisé), filtre A/B/C/D, risques et fenêtres horaires de la SPEC, contrôles de fraîcheur et de cash. Retourne uniquement `PREFLIGHT_ONLY_NOT_EXECUTED`, jamais un fill.
2. **`v12_grok_gateway.py`** : reçoit un JSON candidat (issu de fixture à ce stade), évalue, journalise décision refusée/acceptée, retourne clairement `model_invoked:false`, `paper_order_executed:false`, `live_order_executed:false`. Une indisponibilité de Grok est consignée comme `GROK_UNAVAILABLE_NO_TRADE`.
3. **`v12_learning.py`** : journaux d'événements SQLite séparés, IDs uniques, relances exactes idempotentes, empreintes chaînées pour détecter les altérations simples. `decision` puis `outcome` uniquement **après** l'horizon 1/7/30 jours, évaluations relatives à la conservation d'USDC et à BTC. Les propositions de nouvelle politique n'acceptent que `SHADOW_ONLY` et aucune auto-promotion ; un audit externe doit ancrer les empreintes si l'on veut une résistance à une réécriture intégrale.

## Frontière explicite entre simulation et réel

Le test peut accepter une décision et ne produit **aucun ordre**. L'exécution PAPER continue, l'orchestrateur persistant, l'API/service d'invocation vérifiable de Grok, le collecteur live Kraken, le portefeuille USDC valorisé fidèlement et les états persistants des ordres restent à **implémenter et auditer** avant le premier cycle autorisé.

La quote de référence de la SPEC initiale est **USD** et le capital PAPER conventionnel est **6 605,10 USD cash**. Le portefeuille réel de Cyril étant en **USDC**, le montant détenu et le taux USDC/USD ne doivent jamais être inventés ; l'évaluation USDC conservés sera réalisée sur les observations réelles du benchmark et les coûts de conversion, séparément du compte réel.

Le code de sécurité valide les données en mémoire sous l'hypothèse que le futur collecteur est authentifié. Une chaîne `"trusted-public-kraken"` dans un JSON **ne constitue pas une preuve d'authenticité**. Il faudra interdire à la sortie du modèle de modifier les inputs utilisés par `v12_autonomy.py`, utiliser un protocole de communication strict et revérifier les plafonds de façon atomique dans l'exécuteur PAPER.

## Apprentissage vérifiable

Grok pourra analyser les journaux par fenêtre chronologique, proposer `policy_version` suivante avec une hypothèse testable, puis faire fonctionner cette variante en shadow sur des données futures. La politique active doit être définie **par l'orchestrateur de confiance**, pas par la réponse Grok. L'apprentissage n'est pas un réentraînement implicite du modèle.

Un journal plus riche doit ensuite inclure l'action effectivement simulée, les frais payés, la différence avec `HOLD USDC`, les incidents et la perte maximale. **De bons résultats courts ne prouvent ni rentabilité future ni aptitude à gérer des fonds réels.**

## Tests hors ligne

```bash
python3 -m unittest discover -s tests -p 'test_v12_autonomy.py' -v
python3 -m unittest discover -s tests -p 'test_v12_learning.py' -v
python3 -m unittest discover -s tests -p 'test_v12_grok_gateway.py' -v
```

Tests comprenant : décision C admissible sans changement de cash, faux signal A, calendrier B, poids impossible, spread/données trop anciennes, pause/kill-switch, aucun short, tentative de nouvelle version de politique, absence Grok, journal idempotent, tentative de falsification et interdiction de promouvoir automatiquement en LIVE.

**Important** : les comptes/états de tests restent dans des répertoires temporaires hors dépôt. Ni `cycle_v12.py --cycle`, ni le workflow, ni le site n'ont été activés.

## Prochains jalons (requièrent revue Grok et décisions Cyril)

1. **Vérifier le mode d'invocation de Grok Bot** accessible dans ce projet (service/agent/API) et sa capacité à retourner une décision conforme, avec authentification de l'émetteur.
2. Créer le collecteur public Kraken en lecture seule, avec cache temporel et compteurs de pannes, séparé de la réponse Grok.
3. Ajouter l'exécuteur PAPER idempotent, prise en compte du statut `maker`/fallback `taker`, USD/USDC, stops et arrêt d'urgence, en testant les redémarrages et l'absence d'ordre doublonné.
4. Auditer la conformité des quatre candidats aux paramètres V1.2 et l'exécution PAPER sur des fixtures hostiles.
5. Après autorisation **distincte de Cyril**, seulement : premier cycle fictif, évaluation prospective, apprentissage shadow. Aucun mécanisme ne peut décider seul du passage en LIVE.
