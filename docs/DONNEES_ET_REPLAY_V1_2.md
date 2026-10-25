# Kraken Sim V1.2 — sources historiques et rejeu V1.1

**Statut : préparation technique uniquement.** Aucune archive historique de grande taille n'a été téléchargée dans notre environnement, aucun backtest financier officiel n'a été effectué, aucun cycle V1.2 n'a été lancé.

## Sources Kraken vérifiées le 25 octobre 2026

Documentation officielle : https://support.kraken.com/fr/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data (mise à jour du 12 octobre 2026).

Kraken propose une archive OHLCVT complète depuis la première transaction de chaque paire jusqu'au **30 juin 2026**, en cinq parties `Kraken_OHLCVT_Full.zip.part00` à `part04`. Somme SHA-256 de l'archive ZIP reconstituée publiée par Kraken :

`bc273e9027470b07d790a7fa4df9bb43f0dfc527c20c6ecae48402e123e7b1c7`

Archive complémentaire **2026 T3** : https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_2026Q3.zip

Les archives contiennent des CSV sans en-tête `timestamp,open,high,low,close,volume,trades` et un manifeste Kraken. Les jours sans échange peuvent être absents ; ce ne sont pas forcément des erreurs de téléchargement.

Données de transactions détaillées (*time and sales*) : https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales- ; les transactions ne prouvent pas l'état historique complet du carnet d'ordres.

## Outil d'import local, sans clé Kraken

`prepare_kraken_history_v12.py` :

1. Après téléchargement **extérieur au dépôt**, reconstituer le ZIP avec `cat Kraken_OHLCVT_Full.zip.part* > Kraken_OHLCVT_Full.zip` et vérifier SHA-256 avec `sha256sum`.
2. Renseigner `ARCHIVES.json` avec pour chaque archive les champs `file` (chemin absolu), `sha256` vérifié, `source_url` officiel et `retrieved_utc`.
3. Exécuter `python3 prepare_kraken_history_v12.py scan --archives ARCHIVES.json --out /data/kraken-v12/inventory.json`. L'inventaire recense les noms de paires USD effectivement présents, sans inventer leur statut de cotation.
4. Renseigner `PAIR_REVIEW.json` : `{"pairs":{"XXBTZUSD":{"asset":"BTC","status":"unknown","listed_at":null,"delisted_at":null,"evidence_url":null},"USDTUSD":{"exclude":true,"reason":"stablecoin"}}}` ; **toutes** les paires trouvées doivent figurer avec leur traitement explicite.
5. Exécuter `python3 prepare_kraken_history_v12.py build --archives ARCHIVES.json --mapping PAIR_REVIEW.json --output /data/kraken-v12/normalized`.

Le build vérifie les empreintes ZIP, refuse les paires oubliées, les exclusions non motivées, les collisions d'actifs et les révisions contradictoires entre archives. Il extrait seulement les bougies 1 440 minutes, fusionne les doublons identiques et produit `INVENTORY.json` ainsi que **`MANIFEST.draft.json`**.

**Ce manifeste reste volontairement NON CERTIFIÉ** (`all_historical_usd_spot_pairs_verified=false`). Les dates de première/dernière transaction ne sont pas, à elles seules, des dates officielles de cotation/délistage. L'intégrité d'un ZIP ne prouve pas la complétude de l'univers historiquement tradable.

Ne pas placer les ZIP ni les CSV massifs dans GitHub. Ne pas transformer le manifeste brouillon en manifeste officiellement validé sans preuve documentaire distincte.

## Rejeu du moteur de production V1.1

`v12_v11_replay.py` exécute **le fichier d'origine `cycle_v11.py`, inchangé**, sur des snapshots d'API publiques dans un environnement de test hors ligne.

Le fichier SQLite et l'historique sont créés dans un répertoire temporaire externe ; tout accès réseau est interdit. Les réponses API absentes invalident le rejeu même si le moteur V1.1 ignore certaines exceptions dans son fonctionnement normal. Les tests utilisent des snapshots **synthétiques** et vérifient la reproductibilité ainsi que les positions initiales BTC/ETH/XRP.

Cela valide un *banc technique déterministe*, **pas** les performances V1.1 de 2021 à 2026.

Une comparaison historique exacte exige aussi, à chaque horaire de cycle, les paires disponibles, les quotes/spreads/volumes, les transactions après placement d'ordres et la profondeur de carnet utilisée pour les sorties. Les chandelles OHLCVT journalières ne reconstituent pas ces éléments.

Un replay simplifié fondé sur OHLCVT peut être considéré comme **proxy**, jamais comme `REPRODUCED_V11` sans revue méthodologique explicite de Grok Bot et accord de Cyril.

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_v12_archive_preparation.py' -v
python3 -m unittest discover -s tests -p 'test_v12_v11_offline_replay.py' -v
```

Ni l'importeur ni le rejeu n'exécutent `cycle_v12.py --cycle`, ne publient le dashboard ou ne touchent à `main`.
