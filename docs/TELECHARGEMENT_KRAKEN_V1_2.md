# Kraken Sim V1.2 — téléchargement sécurisé des données Kraken

**Statut : outil prêt sur la PR #7, téléchargement non lancé.** Aucune modification de `main`, aucune simulation V1.2, aucune publication de données historiques sur GitHub.

## Objectif

Préparer sur un disque dédié les données OHLCVT officielles Kraken de 2021 à septembre 2026, puis inventorier les paires historiques USD sans effacer les cryptoactifs délistés.

Source : [Kraken — Downloadable historical OHLCVT](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data), actualisée le 12 octobre 2026. Le jeu complet est distribué en **cinq fichiers d'environ 2 Go** ; un ZIP 2026 T3 complète l'historique. La taille sur disque nécessaire est supérieure au volume téléchargé, car le ZIP assemblé coexiste avec les cinq parties. **Prévoir au moins 25 Gio libres** pour démarrer, et davantage pour extraire les séries normalisées.

La documentation Kraken publie les empreintes SHA-256 des cinq parties à l'adresse :
https://assets.kraken.com/marketing/institutions/OHLCVT_Full_PARTS_SHA256SUMS.txt

| Partie | SHA-256 officielle |
|---|---|
| part00 | `12ce809a0cc12c421f9bb871434f71eca8b3c258cb194efae258318a683b9491` |
| part01 | `7086e1915e79b5157fae05978ca9603da7d7a53d03ee` |
| part02 | `880fcf84e177e50ca946f3f5cb6d57c721a4950853ca1bf6bdde526896013cc1` |
| part03 | `3fa1fdfbb94c5a3cc861068a11b5c309502a8ac8da0f4c6f091c5a2968451157` |
| part04 | `db2c8b80c92a2e09b3f71f464b0b55574bd56c645d2560169dbbe4887b9c00eb` |

SHA-256 ZIP complet recomposé : `bc273e9027470b07d790a7fa4df9bb43f0dfc527c20c6ecae48402e123e7b1c7`.

## 1. Télécharger le ZIP complet (Windows / PowerShell)

À exécuter depuis une copie du dépôt Kraken Sim sur une machine disposant de Python 3 et du stockage requis :

```powershell
# Vérification sans réseau et sans écriture : affiche seulement le plan
py -3 fetch_kraken_history_v12.py --out "D:\Kraken-History\V12"

# Téléchargement volontaire (fichiers volumineux), arrêt/reprise permis
py -3 fetch_kraken_history_v12.py --download --out "D:\Kraken-History\V12"
```

`--download` est obligatoire pour lancer les transferts. Le téléchargement utilise exclusivement les cinq URL d'archives Kraken fixées dans le code ; une partie interrompue reprend avec une requête HTTP Range, mais seule une partie dont le SHA-256 correspond exactement à l'empreinte publiée reçoit son nom définitif.

Le programme vérifie ensuite le ZIP assemblé et crée `ARCHIVES.json` pour l'outil d'inventaire. Si le fichier est déjà conforme, il est réutilisé. Une archive existante mais corrompue provoque un échec, et aucun fichier ne sera remplacé silencieusement.

**Aucune clé API Kraken nécessaire.** Les données sont publiques.

## 2. Compléter avec le trimestre 2026 T3

Télécharger le ZIP trimestriel officiel depuis :
https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_2026Q3.zip

Exemple PowerShell :

```powershell
curl.exe -fL --retry 3 -o "D:\Kraken-History\V12\Kraken_OHLCVT_2026Q3.zip" "https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_2026Q3.zip"

py -3 fetch_kraken_history_v12.py --download --out "D:\Kraken-History\V12" --q3-file "D:\Kraken-History\V12\Kraken_OHLCVT_2026Q3.zip"
```

La seconde invocation vérifie à nouveau le ZIP complet existant et **ajoute le Q3 à ARCHIVES.json sans supprimer les empreintes précédentes**. Comme aucune empreinte SHA-256 Q3 publiée indépendamment n'a été établie, l'empreinte enregistrée pour Q3 est uniquement un *fingerprint local* et **ne doit pas être présentée comme un checksum officiellement attesté**.

## 3. Inventorier et contrôler toutes les paires historiques

```powershell
py -3 prepare_kraken_history_v12.py scan --archives "D:\Kraken-History\V12\ARCHIVES.json" --out "D:\Kraken-History\V12\INVENTORY.json"
```

Cet inventaire recense toutes les paires USD avec fichier CSV journalier. Il ne garantit pas que les paires disparues n'ont pas été exclues des fichiers distribués. La validation exige une comparaison indépendante avec les registres historiques de cotation/délistage et une revue individuelle des symboles.

Après avoir créé `PAIR_REVIEW.json` en documentant **toutes** les paires (actif, inclusion/exclusion motivée, preuves de cotation, date et statut), exécuter :

```powershell
py -3 prepare_kraken_history_v12.py build --archives "D:\Kraken-History\V12\ARCHIVES.json" --mapping "D:\Kraken-History\V12\PAIR_REVIEW.json" --output "D:\Kraken-History\V12\normalized"
```

Les séries normalisées auront leur propre SHA-256 et le résultat sera **`MANIFEST.draft.json`**. Il ne passe pas automatiquement à `MANIFEST.json` « officiel ». Cette étape nécessite d'abord la preuve de complétude de l'univers USD dans le temps.

## Sécurité et garde-fous

- Rien n'est téléchargé ni décompressé par GitHub Actions ; les cinq fichiers ZIP restent **hors dépôt**, sur un volume de données.
- Aucun accès au portefeuille V1.1, à `sim.db` ou à une clé d'ordre Kraken.
- Aucun cycle V1.2 n'est déclenché ; `cycle_v12.py --cycle` reste bloqué.
- Pas de données de prix 2021–2026 ni de statistiques financières inventées.
- Le replay V1.1 historique complet nécessite des cotations intrajournalières, transactions et éventuellement profondeur de carnet ; un OHLCVT journalier ne suffit pas. Voir [DONNEES_ET_REPLAY_V1_2.md](DONNEES_ET_REPLAY_V1_2.md).

**Prochaine condition de sortie de l'étape données :** inventaire réel, inclusion documentée des actifs retirés de la cote, manifeste contrôlé et baseline V1.1 méthodologiquement validée. Ensuite seulement pourront commencer les backtests officiels.
