# Audit initial V1.6.2 et UX V1.2.3 — 26/10/2026

## Contrôle de version

La branche source `strategy/v1.2` auditée au commit `f8febca0` affiche encore `VERSION_ENGINE_V12=V1.6.1`. **Aucune V1.6.2 n'était présente** à l'instant de cette revue : le passage à 1 M et le contrôle Depth annoncé par GrokBot **ne sont pas encore auditables**. Ne pas leur attribuer un statut « vérifié ».

## Points du moteur actuel à vérifier lorsque V1.6.2 sera poussée

1. `strategy/v1_2/params.json` contient `UNIVERSE.min_median_daily_usd_volume=5000000` et `quote=USD` hérités ; la conformité PAPER est pourtant XXX/USDC. Vérifier que la prochaine version corrige la cohérence des noms/unités et applique **effectivement** le 1 M USDC, pas seulement un affichage.
2. Le collecteur Kraken public actuel utilise exclusivement les endpoints `AssetPairs`, `Ticker` et `OHLC` ; il **n'interroge pas `Depth`**. Vérifier le contrôle du carnet réel par paire, au moment de chaque ordre, côté achat comme côté vente, avec horodatage et fraîcheur.
3. `Ticker` renvoie un volume de 24 h ; la politique est formulée en **volume médian quotidien sur 30 jours**. Prouver par test que le filtre calcule la médiane sur les bougies USDC closes, sans confondre le volume de ticker et la médiane.
4. Le spread ≤0,30 % doit rester un blocage **à l'exécution**, pas seulement un filtre de présélection ; refuser si le carnet est indisponible, périmé ou trop mince.
5. Définir et publier le nombre d'ordres **tentés**, refusés pour liquidité, non remplis, les motifs horodatés et la taille visée ; le pourcentage doit avoir un dénominateur stable. Pas de rollback automatique sur un unique incident.
6. Les vérifications de liquidité ne doivent jamais influer sur les sorties de sécurité : documenter le comportement moteur si une vente de réduction du risque rencontre un carnet mince. Ne pas transformer un manque de liquidité local en panne globale de marché.
7. Préserver la séparation state-v12 / production V1.1, conformité UE/MiCA, quote exclusivement USDC, idempotence et exécution PAPER (aucune clé de trading).

## Travail UI livré, indépendant du moteur

`dashboard_v12_cockpit_template.html` passe à **UX V1.2.3** et ajoute un espace **Liquidité XXX/USDC**, après la synthèse existante. Il lit exclusivement un bloc facultatif `public_state_v12.json.liquidity_monitor` :

```json
{"liquidity_monitor":{
  "as_of":"2026-10-26T00:00:00Z",
  "min_median_daily_volume_usdc":1000000,
  "eligible_pairs_count":null,
  "rejected_liquidity_orders":null,
  "rejected_liquidity_pct":null,
  "orderbook_checks":null,
  "median_spread_pct":null,
  "estimated_slippage_pct":null,
  "rejection_reasons":null,
  "rollback_policy":null
}}
```

**Ceci est un exemple de forme de schéma, pas un résultat de simulation**. Valeurs numériques autres que le seuil expérimental connu volontairement `null`; le dashboard ne déduit pas la réalisation du contrôle à partir d'une promesse. En absence du bloc, affiche `—` et `Non publié` plutôt qu'un faux 0.

**Important :** cette PR est uniquement UX et tests/documentation. `render_v12_page.py` ne publie pas encore ce bloc. Les métriques ne s'afficheront qu'après un raccordement contrôlé au moteur PAPER par une autre modification autorisée. Aucun commit vers la production, aucune activation de trading, aucune publication de site.

## Historique GitHub

Branche de travail : `feature/v12-liquidity-monitor-ux` ; PR vers `strategy/v1.2`. Toutes les modifications et tests doivent être commentés sur PR #7 conformément à la demande de GrokBot.
