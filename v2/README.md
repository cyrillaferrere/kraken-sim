# Kraken Sim V2 — Passation GrokBot

**État au 26/10/2026 : préparation technique, PAS de simulation autonome active.**
Le dashboard V2 est publié, les prix publics Kraken sont visibles. Le moteur `v2/engine.py` reste volontairement HOLD. Le workflow V2 est manuel, sans cron. Aucun ordre réel autorisé.

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

**Important :** l'exemple est structurel et n'est pas directement exécutable. Les valeurs `<...>` doivent être remplacées par des données vérifiées. Pour un cycle HOLD, `decisions: []`. `closed_trades_summary` et `closed_trades_history` peuvent être omis tant que GrokBot n'a pas de bilan validé. Au-delà du premier cycle, `initial_usdc` est ignoré ; le capital initial reste immuable. Fournir un prix `prices` pour **toutes les positions détenues** à chaque cycle, même sans ordre.

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
- `last_cycle_id` : identifiant du dernier cycle pour la protection anti-doublon.

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
- Les montants sont calculés en `Decimal` pendant un cycle, mais l'état public expose des nombres JSON pour compatibilité dashboard : **valider la précision multi-cycle et la comptabilité de bout en bout avant activation**.
- La protection contre les doublons vérifie le dernier cycle et l'ordre chronologique. Une publication concurrente nécessite aussi une protection transactionnelle côté orchestrateur.
- Le backtest, le kill-switch de l'orchestrateur, le contrôle de fraîcheur des données, le suivi des ordres clôturés et les tests end-to-end restent à finaliser/valider.
- **Aucun automatisme ni ordre réel ne doit être déclenché par la présence de ces fichiers.**

## 6. Liens

- Production : https://cyrillaferrere.github.io/kraken-sim/v2/
- Préproduction : https://cyrillaferrere.github.io/kraken-sim-preprod/v2/
- Dépôt : https://github.com/cyrillaferrere/kraken-sim
