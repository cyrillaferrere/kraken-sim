# UX Kraken Sim V1.2 — Cockpit de préproduction (proposition non publiée)

**Date : 25 octobre 2026 · UX V1.2.0 · Branche : `feature/ux-v12-preprod-cockpit`.**

**Portée de l'autorisation de Cyril :** construire l'UX à partir de la préprod existante. **Aucune publication du site, aucune fusion, aucun démarrage de simulation ni aucun accès au portefeuille réel.**

## Référence visuelle effectivement consultée

Préprod V1.1.2 : `https://cyrillaferrere.github.io/kraken-sim-preprod/`, issue de `kraken-sim-preprod/main/index.html` et du template `dashboard_template.html`. L'UX V1.2 conserve ses fondements : fond `#080c14`, panneau `#101824`, séparateurs `#233247`, bleu des valeurs/graphiques, fond sombre, rail gauche repliable, métriques tabulaires, affichage mobile, cartes alignées, détails avancés repliables. Le nom souhaité est **Kraken** (rouge), **Sim PreProd** (discret), sans grand bandeau rouge.

## Ce que l'interface V1.2 doit prioriser

1. **Vue d'ensemble** : valeur totale PAPER, P&L net, variation, capital initial, liquidités, écart vs USDC conservés, exposition, drawdown et état des protections. Graphe principal PAPER vs USDC HOLD avec BTC HOLD optionnel, contrôle 7j / 30j / tout, sur la même échelle.
2. **Portefeuille** : positions ouvertes, quantités, valeurs, P&L, stratégie A/B/C/D si attribuée, allocation cash / positions, références USDC et BTC accessibles sans surcharge.
3. **Grok Bot & décisions** : situation de Grok, **IT libres et potentiellement 10 ou plus par jour**, dernier choix, tableau des ordres fictifs avec filtre, historique des IT et bloc A/B/C/D. **Grok possède déjà son connecteur Kraken**. Les signaux ne doivent pas être présentés comme des ordres exécutés.
4. **Analyse & apprentissage** : outcomes moteur à J+1/J+7/J+30, politique active, propositions shadow, historique des motifs des décisions, transparence des sources et versions. Les détails absents restent visiblement non disponibles.

## Contrat V1.2 — champs existants vs à exporter

L'interface valide strictement `strategy_id=kraken-sim-v1.2`, `environment=preprod`, `strategy_version=V1.2`. Une réponse V1.1 n'est jamais affichée. `render_preprod.py` conserve son double verrou `PREPROD_V12_READY=1` + état V1.2 effectivement disponible.

**Déjà compatibles avec `export_v12.normalize()` si publiés par le moteur :** `equity`, `cash`, `C0`, `positions[]`, `orders[]`, `decisions[]`, `as_of`, `last_cycle_iso`, `version_engine`, `exposure_pct`, `cur_dd_pct` et `fees` (plusieurs valeurs peuvent être nulles).

**Données V1.2 facultatives, à raccorder explicitement au moment de l'activation :**

| Champ de l'état public V1.2 | Source à publier, sans fiction |
|---|---|
| `usdc_hold_usd`, `btc_hold_usd` | Marques du moteur PAPER et benchmark USDC/USD observé |
| `curve_v12[]` ou `marks[]` | Marques datées `{ts, equity, usdc_hold_usd, btc_hold_usd}` |
| `risk{risk_lock,paused,active_policy_version}` | Contrôleur moteur indépendant |
| `fees_paid_usd`, `pending_orders[]` et `pending_count` | Moteur / ledger PAPER, ordres pending |
| `grok{last_it_iso,status,last_action,policy_version}` | Registre de réception des IT |
| `it_history[]` | Toutes les IT enregistrées, pas uniquement la dernière |
| `candidate_signals{A,B,C,D}` | Synthèse stricte de la stratégie V1.2 (non interprétée comme ordre) |
| `learning{outcomes_count,shadow_proposals}` | Calculs du moteur, pas auto-évaluation par Grok |

**Pas de fallback vers la V1.1.** Aucun prix ni P&L fictif présenté comme réel. Les valeurs nulles affichent `—` ou `Non publié`. Sur une source trop ancienne, le site marque les données comme figées, pas comme « live ». Le temps de cycle provient de l'horodatage V1.2 et s'affiche en Europe/Paris.

## Comportements

- Navigation desktop rail de la préprod, menu mobile ; version moteur / stratégie / UX sur la ligne supérieure.
- Histogrammes d'exposition et drawdown plafonnés uniquement pour visualisation (plafonds stratégiques restent dans le moteur).
- Filtres d'ordres `Tous / Achats / Ventes / Refusés`.
- Courbe SVG sans bibliothèque externe, durée ajustable ; référence USDC non inventée si absente.
- Rendu HTML des valeurs externes échappé, lecture seule : aucun bouton de trading, aucune intervention IA depuis le dashboard.
- Aucun nombre de jours ni heure fixe imposés à Grok ; les cycles PAPER de protection peuvent être plus fréquents que les IT.

## Procédure de recette AVANT toute publication

```bash
python3 -m unittest discover -s tests -p 'test_v12_ux.py' -v
python3 -m unittest discover -s tests -p 'test_v12_render.py' -v
```

Le test construit un site dans un dossier temporaire à partir d'un état V1.2 **de test**, vérifie le contrat, la présence des quatre espaces, le graphe, le rendu navigateur (si Chrome installé), le refus d'un état V1.1 et l'absence de chiffres fabriqués quand les données de marque manquent. Les fixtures de test ne sont jamais publiées.

**Avant de montrer une UX effectivement en ligne, Cyril doit donner un GO séparé** : il faudra disposer d'un `public_state_v12.json` réel sur `state-v12` et autoriser la bascule de la préprod. Ni cet état ni cette activation ne sont créés par la présente PR.
