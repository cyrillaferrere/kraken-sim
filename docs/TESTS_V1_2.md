# Tests V1.2 — état de la PR #7 (infrastructure + fonctions pures)

Exécution dans GitHub Actions, hors ligne :

- python3 -m unittest discover -s tests -p 'test_v12_*.py' -v
- python3 -m unittest discover -s tests -p 'test_v11_nonregression.py' -v
- python3 tests/check_template.py

Couverture actuelle : chemin d'état indépendant et obligatoire ; absence de cycle effectif ; idempotence des identifiants ; comptabilité spot sans effet de levier ni short, frais maker/taker ; franchissement strict et remplissage partiel hypothétique ; gaps d'exécution ; sérialisation atomique ; bougies futures et univers point-in-time ; signaux candidats purs A/B/C/D ; lecture CSV Kraken OHLCVT 1440 à 7 colonnes sans en-tête avec vérification SHA-256 et comblement explicite des journées sans trade ; snapshots d'historique append-only ; gel statique du moteur V1.1.

**Non encore validés** : replay déterministe complet V1.1, équivalence économique avec moteur réel, intégration complète des ordres et des positions dans cycle_v12.py, backtests et grille walk-forward, univers historique point-in-time complet avec delistings, exécution maker réelle, rendement net et critères de rejet. Le green de la CI n'autorise aucun cycle et ne démontre pas la rentabilité.

La source officielle Kraken décrit les CSV OHLCVT et leurs colonnes : https://support.kraken.com/fr/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data

### Revue Grok Bot PR #7 — corrections faites
- `tests/test_v12_protected_paths.py` : tests négatifs automatiques sur `state/x.json`, `state/public_state.json`, `state/history/...`, `VERSION_ENGINE` et autres chemins V1.1 ; règle P0 du workflow réparée.
- `tests/test_v12_version_isolation.py` : export V1.2 sous `VERSION_ENGINE_V12` sans modifier `VERSION_ENGINE` (version sur develop) ; nouveaux ordres V1.1 étiquetés comme avant.
- `tests/test_v12_isolation.py` : tests supplémentaires pour clones de production, dossiers `state`, ancêtres contenant `sim.db` et checkout Git autorisé de la seule préprod.
