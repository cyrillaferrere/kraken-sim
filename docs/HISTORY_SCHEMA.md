# Historique par cycle pour le replay — schema_version 1 (Moteur V1.2)

> **Projet, en attente de l'accord de GPT-6.** Lecture seule : le replay ne recalcule rien et ne modifie pas la simulation.

## Fichiers
- `state/history/AAAA-MM.json` : un fichier par mois UTC du cycle, au format `{"schema_version":1,"month":"AAAA-MM","cycles":[instantané,...]}`. Les cycles sont triés par `ts` et uniques par `slot` (relancer un slot remplace son instantané).
- `state/history/index.json` : `{"schema_version":1,"updated":ISO,"first_ts","last_ts","n_cycles","months":[{"month","file","n_cycles","first_ts","last_ts"}]}`. Le lecteur charge l'index, puis seulement les mois consultés.
- Écriture : `history_export.py`, appelé en fin de cycle réussi par `cycle_v11.py`. Il n'est jamais appelé en mode render. L'appel est protégé par try/except : en cas d'échec, l'erreur est journalisée et le cycle reste valide. Le commit `sim.yml` (`git add -A … state`) inclut `state/history/`.

## Instantané
| Champ | Contenu |
|---|---|
| `slot` | `AAAAMMJJHH` (UTC), clé unique |
| `ts` / `ts_paris` | ISO UTC `…Z` / `JJ/MM/AAAA HHhMM` (Europe/Paris) |
| `mode`, `status` | table `cycles` (`daily`, `intraday` ; `ok`) |
| `versions` | `{engine, strategy, ux:null}` : l'UX n'est pas connue du moteur, donc toujours `null` avec `versions.ux` dans `missing` |
| `complete` | `true` pour un cycle exporté en direct, `false` pour un cycle rattrapé |
| `portfolio` | `equity`, `cash`, `exposure_pct` (%), `btc_hold` (référence de buy & hold BTC), `net_return_pct` (vs C0), `cur_dd_pct` (vs le pic d'equity jusqu'à ce cycle), `fees_total` (frais cumulés jusqu'à ce cycle) |
| `positions[]` | `asset, pair, qty, avg_price, price, value, pnl, pnl_pct, entry_ts, high, stop` ; `price` = **bid** du cycle (valorisation identique à `equity`) |
| `regime` | `state` (`haussier`/`neutre`/`baissier` = risk-on / neutre / risk-off dur), `btc_close`, `ema50`, `band_low`, `band_high` ; **en plus** : `decided_ts`, `candle` |
| `indicators[]` | `asset, close, ema20, ema50, rsi, adx, macd_hist, vol_ratio, score (0-5), rank, trend_ok` ; **en plus** : `slot` |
| `decisions[]` | `asset, action, reason` du slot |
| `orders[]` | `id, asset, side, qty, price, notional, fee, pnl, reason, liquidity` du slot |
| `missing[]` | chemins des champs à `null` faute de donnée, par exemple `versions.ux`, `positions`, `regime.*` ou `positions.XRP.price` |

### Points à valider avec GPT-6
- Le régime et les indicateurs sont **décidés une fois par jour**, lors du cycle `daily`. Un cycle `intraday` porte donc ceux de la dernière décision quotidienne : `regime.decided_ts` / `regime.candle` et `indicators[].slot` indiquent leur origine. Ces champs s'ajoutent au schéma et ne remplacent aucun champ prévu.
- `rank` provient du classement momentum de la décision quotidienne. Il vaut `null` pour un actif hors classement.
- Aucune valeur n'est inventée : une donnée absente vaut `null` et son chemin figure dans `missing`.

## Rattrapage (`complete:false`)
`python3 history_export.py [sim.db] [racine]`, ou automatiquement au premier cycle si `index.json` n'existe pas. Pour chaque cycle `ok` absent de l'historique, le script remplit seulement `portfolio`, `decisions` et `orders`. `positions`, `regime` et `indicators` valent `null` et figurent dans `missing`. `versions.engine` provient de la version enregistrée sur les ordres du slot quand elle existe ; sinon il vaut `null`. Le script est idempotent : il ne remplace jamais un instantané existant.

Taille indicative : environ 4 ko par instantané complet (10 indicateurs, 3 positions), soit environ 1 Mo par mois à 10 cycles/jour.
