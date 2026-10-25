# Pré-enregistrement — protocole de liquidité V1.2 (sans modification de stratégie)

Décision de Cyril : **GO pour lancer l'étude**, pas pour changer le seuil actif. Développement dans `feature/v12-liquidity-protocol`, isolé de la simulation en cours. Le filtre actif reste **5 M** et toutes les transactions PAPER / états de préproduction restent inchangés.

## Comparaison figée avant résultats

- **A** : médiane glissante de volume quotidien XXX/USDC ≥ **5 M** (référence).
- **B** : identique avec seuil **2 M, 1 M, 500 k**.
- **C** : somme quotidienne point-in-time des volumes XXX/USD, XXX/EUR, XXX/USDC, **convertis vers USDC aux taux observés au jour du volume**, puis médiane 30 jours ≥ **5 M** ; volume global **uniquement** pour l'éligibilité. Toute paire doit être légalement accessible en France et exécutée exclusivement sur XXX/USDC. En absence d'une cotation/taux historique fiable, C est non évaluable, pas réputé validé.

À chaque scénario, on conserve le spread USDC maximal **0,3 %**, l'historique minimum **220 bougies closes**, les contraintes UE/MiCA, aucune marge ni short. Une paire qui ne franchit pas les contrôles d'exécution ne peut générer d'ordre même si son volume global est élevé.

**À trancher avec Grok avant d'exécuter le walk-forward** : pour C, le seuil de volume global retenu ici est 5 M (référence constante) ; si un autre seuil devait être comparé, il faut le pré-enregistrer comme scénario supplémentaire.

## Exigences de données

- Les historiques XXX/USDC, USD et EUR doivent être horodatés et provenir de leur disponibilité réelle à chaque date (listings/delistings compris), avec conversion en valeur USDC au taux **de cette date**, sans donnée future. Idéalement fournir le prix médian ou une référence FX exploitable indépendante des cours postérieurs.
- **Carnet XXX/USDC et trades** échantillonnés aux moments des ordres : bid, ask, profondeur sur la taille cible (ordre = 2 % de l'equity), estimation documentée du slippage, échecs de remplissage et fallback maker→taker. Les bougies OHLC ne permettent **pas** de reconstruire rétrospectivement ces coûts ; si les observations manquent, le critère est indéterminé.
- Backtest A/B/C/D sur les **mêmes périodes**, frais F1 et F2, walk-forward **12 mois réglage / 3 mois hors échantillon** sans reparamétrage OOS ni découverte d'actifs futurs. Les scores financiers et remplissages sont produits par la chaîne de backtests validée, **pas** par `research_liquidity_v12.py` seul.

## Conditions d'acceptation (fixées AVANT résultats)

Toutes requises sur l'univers **XXX/USDC réellement exécutable** :

1. Spread médian ≤ **0,30 %** ET slippage estimé ≤ **0,15 %** sur un ordre de **2 % de l'equity**. Attention : le spread médian seul n'autorise pas à ignorer un spread instantané >0,30 % ; l'ordre reste refusé.
2. Ordres refusés ou non remplis ≤ **5 %** (dénominateur = l'ensemble des tentatives d'ordres, rejets de liquidité inclus ; compter les fallback selon la définition pré-enregistrée, sans exclure les cas pénalisants).
3. Ne pas dégrader **max drawdown ni Calmar OOS** par rapport au filtre A, à stratégie et frais identiques. Une métrique manquante ou un Calmar indéfini n'est **pas** une réussite.
4. Moyenne ≥ **4 paires** réellement éligibles sur les dates de décision, **pas** seulement listées chez Kraken.

En cas d'égalité, choisir la solution la plus simple ; si aucune nouvelle option ne passe, conserver **A (5 M)**. Les résultats sont transmis à Grok pour revue et soumis à Cyril pour accord **avant tout changement de stratégie**.

## Outil livré à ce jalon

`python3 research_liquidity_v12.py --input /chemin/observations.json --output /chemin/rapport.json`

Format : `{"observations":[{"asof":"2026-08-01","asset":"BTC","quote":"USDC","daily_volume_quote":10000000,"fx_to_usdc":1,"bid":100,"ask":100.1,"closed_daily_bars":250}, ...]}`. Le taux `fx_to_usdc` est propre à la paire et à la date ; le contenu peut comprendre USD/EUR/USDC. La sortie est un **diagnostic de couverture, pas un résultat de trading**. Le script échoue plutôt que de combler une journée manquante, n'utilise jamais des observations futures, et signale explicitement que **les critères d'exécution et OOS ne sont PAS vérifiés**.

**État au 25 octobre 2026 :** pas de fichier d'observations historiques attestées USD/EUR/USDC, pas de captures de carnets représentatives et pas de backtests OOS exécutés dans cette livraison. Aucun résultat de rendement ou recommandation chiffrée de nouveau seuil n'est donc présenté.
