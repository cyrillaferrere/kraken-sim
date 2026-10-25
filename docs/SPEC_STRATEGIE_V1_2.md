# Spécification Stratégie V1.2 — Kraken Sim (simulation papier)

Auteur : Kraken Bot (Grok Bot). Implémentation : GPT-6 (`strategy/v1_2/params.json`, `cycle_v12.py`, `backtest_v12.py`).
Références : `docs/v1_2/` (pack d'instructions), audit V1.2 §4, `docs/SPEC_FONCTIONNELLE.md` (V1.1).

## 1. Statut

- **Tous les paramètres ci-dessous sont des hypothèses expérimentales.** Aucune rentabilité n'est démontrée.
- Aucun ordre réel, aucune clé privée : API publique Kraken uniquement (OHLC, Ticker, Depth).
- V1.1 reste seule en production. V1.2 n'est déployée en préprod que si un candidat survit aux critères du §5, figés avant tout résultat.
- Capital de référence : **C0 = 6 605,10 USD, 100 % cash**, quote USD.
- Frais modélisés (deux niveaux, tous deux obligatoires) : **F1** maker 0,25 % / taker 0,40 % ; **F2** maker 0,40 % / taker 0,80 %. Plus spread (demi-spread payé à chaque taker) et slippage (§4.5).

## 2. Conventions communes à tous les candidats

- **Bougies** : journalières closes, clôture 00:00 UTC. Une bougie en cours n'est jamais utilisée.
- **Décision** à la clôture J, **exécution** à l'ouverture J+1 (backtest) ou au cycle suivant (préprod).
- **Univers point-in-time** (recalculé à chaque date de décision t, avec données ≤ t uniquement) :
  - paires `XXX/USD` spot Kraken existant à t ; exclues : stablecoins, tokens indexés/wrappés (USDT, USDC, DAI, PYUSD, WBTC, etc.), fiat ;
  - historique ≥ 120 bougies journalières à t (date de cotation) ;
  - volume médian quotidien en USD sur 30 j ≥ 5 M USD ;
  - top **N_univ = 20** par ce volume médian ; un actif delisté sort de l'univers à sa dernière bougie (position liquidée au dernier cours connu, pénalité de slippage ×3).
- **Indicateurs** : ATR(20) Wilder ; vol réalisée σ20 = écart-type des rendements log quotidiens sur 20 j, annualisée ×√365.
- **Ordres** : maker d'abord (limite au meilleur bid pour un achat / ask pour une vente) ; non rempli dans le cycle → annulé puis **taker** au cycle suivant (backtest : maker rempli seulement si le low (achat) / high (vente) de J+1 traverse le prix limite ; sinon taker à l'open J+2 + demi-spread + slippage). Sorties sur stop et kill-switch : **taker** directement.
- **Taille minimale** : ordre ignoré si < max(minimum Kraken de la paire, 25 USD). Ajustements de poids < 2 % de l'equity ignorés (bande de non-transaction).
- **Cash** : tout ce qui n'est pas alloué reste en USD, rendement nul.

## 3. Candidats

### A — Breakout Donchian 55/20, suivi de tendance, sizing volatilité
- Univers : §2 (top 20).
- Régime : BTC close > SMA200(BTC) → entrées autorisées ; sinon aucune nouvelle entrée (sorties normales).
- Entrée : close_t > plus haut des 55 bougies précédentes (t-55..t-1).
- Sortie : close_t < plus bas des 20 bougies précédentes, **ou** stop suiveur.
- Stop : suiveur à 3 × ATR(20) sous le plus haut close depuis l'entrée ; évalué sur close journalier, exécution taker J+1.
- Sizing : poids_i = risque_cible / (k_ATR × ATR_i / close_i), risque_cible = 0,5 % d'equity (perte théorique au stop initial, hors gap), plafonné à 15 %/actif. Calculé à l'entrée, pas réajusté.
- Exposition max 80 % ; si dépassée, nouvelles entrées classées par force du breakout (close/plus haut 55 j) et refusées au-delà ; max 8 positions.
- Fréquence : évaluation quotidienne ; pas de rééquilibrage des positions existantes.
- Défauts : entrée 55, sortie 20, ATR×3, risque 0,5 %.
- Grille : entrée {40, 55, 70} × sortie {10, 20, 30} × ATR {2,5 ; 3 ; 4} (27 points).

### B — Dual momentum, rotation hebdomadaire, filtre absolu cash
- Univers : §2 (top 20).
- Fréquence : décision chaque **lundi** sur la clôture de dimanche (00:00 UTC lundi), exécution lundi.
- Momentum relatif : R_i = rendement 90 j (close_t / close_{t-90} − 1), saut des 7 derniers jours exclu : close_{t-7}/close_{t-97} − 1.
- Filtre absolu : un actif n'est éligible que si R_i > 0 **et** close_t > SMA100_i. Régime BTC : si R_BTC ≤ 0, portefeuille entièrement cash.
- Sélection : top **K = 4** éligibles ; si moins de 4, la part non pourvue reste en cash.
- Sizing : inverse de la vol, w_i ∝ 1/σ20_i, puis mise à l'échelle pour une vol cible de portefeuille 40 % annualisée (vol estimée sans corrélation, approche conservatrice : Σ w_i σ_i), plafonds 30 %/actif, 90 % au total.
- Rétention : un actif détenu reste s'il est dans le top K+2 et éligible (réduit le turnover).
- Stop : catastrophe à 4 × ATR(20) sous le prix d'entrée, évalué quotidiennement (taker J+1). Pas de rachat avant la rotation suivante.
- Défauts : lookback 90, skip 7, K 4, vol cible 40 %.
- Grille : lookback {60, 90, 120} × K {3, 4, 5} × vol cible {30 %, 40 %, 50 %} (27 points).

### C — BTC/ETH tendance + ciblage de volatilité (turnover minimal)
- Univers : BTC/USD et ETH/USD uniquement (pas de filtre de liquidité).
- Signal par actif : long si EMA50 > EMA200 **et** close > EMA50 ; sortie si close < EMA200 **ou** EMA50 < EMA200 (hystérésis : entre les deux, état inchangé).
- Sizing : w_i = min(plafond, 0,5 × vol_cible / σ20_i), vol cible 30 % par actif, plafond 50 %/actif, total ≤ 100 %.
- Rééquilibrage : **hebdomadaire** (lundi) pour les poids ; changement de signal appliqué au plus tôt le cycle suivant. Bande de non-transaction 5 % (au lieu de 2 %).
- Stop : aucun stop intrajournalier ; la sortie de signal fait office de stop. Kill-switch §6.
- Défauts : EMA 50/200, vol cible 30 %, bande 5 %.
- Grille : EMA rapide {30, 50, 70} × lente {150, 200, 250} × vol cible {20 %, 30 %, 40 %} (27 points).

### D — V1.1 corrigée (rotation hebdomadaire)
- Identique à V1.1 (`strategy/params.json` : régime EMA50 BTC à hystérésis, top-5 momentum, stops 3×ATR, taille 33 %) **sauf** :
  - décision hebdomadaire (lundi) au lieu de quotidienne ; univers point-in-time §2 ;
  - taille max 20 %/actif, exposition max 80 % ; détention minimale 48 h supprimée (remplacée par la rotation hebdo) ; kill-switch §6.
- But : isoler l'effet de la fréquence et du sizing sur V1.1.
- Grille : top {3, 5, 7} × ATR {2,5 ; 3 ; 4} × taille {15 %, 20 %, 25 %} (27 points).

## 4. Protocole de backtest

### 4.1 Données
- Historique : fichiers officiels Kraken **OHLCVT** (CSV trimestriels/complets, support.kraken.com), complétés par l'API publique `/0/public/OHLC` (interval=1440) pour la période récente.
- Provenance : pour chaque fichier, URL, date de téléchargement, SHA-256 dans `data/v12/MANIFEST.json`. Datasets **figés** (pas de rechargement silencieux) ; toute mise à jour = nouveau manifeste versionné.
- Contrôles : trous de bougies (remplis par close précédent, volume 0, signalés), doublons, prix ≤ 0, raccord CSV/API (écart close > 0,5 % le même jour → alerte).
- Biais déclarés : survivance (paires délistées incomplètes), pas d'historique de carnet (spread modélisé), paliers de frais historiques approximés.

### 4.2 Univers et look-ahead
- Univers recalculé à chaque date de décision (§2). Interdits : volume, prix ou cotation futurs. Test `test_v12_lookahead.py` : tronquer les données après t ne change aucune décision ≤ t.

### 4.3 Walk-forward glissant
- Fenêtres : **12 mois in-sample (IS), 3 mois out-of-sample (OOS)**, pas de 3 mois, depuis le 1er jour où l'univers compte ≥ 5 actifs et préchauffage de 250 bougies.
- IS : choisir le point de grille au meilleur Calmar IS ; l'appliquer tel quel sur l'OOS suivant. Les OOS concaténés forment la courbe officielle.
- Aussi publié : run « défauts fixes » sur toute la période (sans optimisation).

### 4.4 Fenêtres de stress (rapportées séparément)
Mai 2021 ; juin 2022 ; novembre 2022 (FTX) ; août 2024 ; les 90 derniers jours disponibles.

### 4.5 Coûts
- F1 et F2 (§1), toujours les deux.
- Spread : demi-spread forfaitaire 0,02 % (BTC/ETH), 0,08 % (autres) par ordre taker ; slippage taker = 0,05 % (BTC/ETH), 0,15 % (autres) ; ×3 sur stops et kill-switch.

### 4.6 Baselines (mêmes périodes, mêmes coûts)
1. **V1.1** telle que spécifiée (reproduire d'abord : +39,7 % optimiste, ~+5 % WF à 0,4 %, ~−7 % à 0,8 %, MDD ~−59,9 % ; écart > 5 points → enquêter avant tout).
2. **BTC buy-and-hold** (achat taker J0).
3. **Panier BTC/ETH/XRP équipondéré**, rééquilibré le 1er de chaque mois.
4. **Cash** (0 %).

## 5. Critères de rejet (figés avant résultats, mécaniques)

Évalués sur la courbe OOS concaténée au niveau de frais **F2** (0,40/0,80 %). Un candidat est **rejeté** si l'un est vrai :
1. Rendement net OOS ≤ cash (0 %) **ou** ≤ V1.1 sur la même période.
2. Max drawdown OOS pire que **−35 %**.
3. Rendement net positif dans **un seul** pli OOS (ou moins) ; exigé : > 50 % des plis positifs.
4. Frais + spread + slippage > **40 %** du profit brut (ou profit brut ≤ 0).
5. Sensibilité : sur la grille (run défauts fixes), un voisin direct (un paramètre décalé d'un cran) donne un rendement net de signe opposé à celui du point par défaut.
6. Moins de **30 trades** (allers-retours clos) en OOS.
7. Rendement net OOS à F1 ≤ 0 (cohérence).

**Sélection parmi les survivants** : meilleur **Calmar** OOS F2, départage par **Sortino** ; jamais le rendement brut.
**Si aucun survivant : V1.2 n'est pas déployée** ; le rapport `backtest_v12_results.json` et le CHANGELOG le disent explicitement.

## 6. Règles de risque communes

- **Kill-switch** : equity ≤ 75 % du pic d'equity (−25 %) → liquidation taker de tout, passage cash, **prioritaire sur toute détention minimale ou rotation**. Reprise seulement après 14 jours et régime BTC favorable (close > SMA200), avec pic réinitialisé.
- **Exposition max** : 90 % (A : 80 %, C : 100 % autorisé car 2 actifs majeurs).
- **Max par actif** : 30 % (A 15 %, D 20 %, C 50 %).
- **Corrélation** : aucune nouvelle position si sa corrélation 60 j (rendements quotidiens) avec une position détenue > 0,85 et que la somme des poids du groupe corrélé dépasserait 40 % ; on garde la plus forte selon le signal du candidat. (Non appliqué à C.)
- **Données périmées / panne API** : si la dernière bougie close date de > 26 h, si un appel API échoue après 3 essais, ou si le carnet est vide/incohérent → **aucun trade** dans le cycle, état et raison journalisés ; positions conservées.
- **Gap** : un stop n'est **pas garanti** ; exécution au premier prix disponible (open J+1), avec slippage ×3. Les pertes au-delà du stop sont comptées, jamais plafonnées.
- Comptabilité : equity = cash + Σ positions ; cash jamais négatif ; pas de levier, pas de short.

## 7. Métriques à rapporter

Par candidat et baseline, à F1 et F2, en OOS concaténé, par pli, par fenêtre de stress et en run défauts fixes :
- rendement net total, CAGR (si ≥ 1 an), rendement brut ;
- max drawdown et durée, volatilité annualisée ;
- Sharpe, Sortino, Calmar ;
- nombre de trades et d'ordres (maker/taker, % de makers non remplis), win rate, gain/perte moyens ;
- turnover annualisé, frais + spread + slippage en USD et en % du profit brut ;
- exposition moyenne, nombre moyen de positions, jours en cash, déclenchements kill-switch ;
- % de plis positifs, carte de sensibilité de la grille ;
- résultat de chaque critère du §5 (passe/échoue, valeur) et décision finale.
Sortie machine-lisible : `backtest_v12_results.json` (hash du manifeste de données, commit, versions).

## 8. Contraintes zone euro et devise (ajout du 25/10/2026)
Demande de Cyril (résident français, zone euro). Mises en œuvre dans le Moteur V1.6.1 : `v12_compliance.py`, sources détaillées dans [CONFORMITE_UE_V1_2.md](CONFORMITE_UE_V1_2.md).
- **Devise de compte : USDC.** Tous les montants (equity, cash, valeurs, frais, P&L) sont exprimés en USDC. Il n'y a aucune conversion depuis l'USD.
- **Univers :** uniquement les paires **XXX/USDC** `online` et accessibles en France (`AssetPairs?country_code=FR`), avec un spread ≤ 0,3 %. Signaux et bougies sont calculés sur l'OHLC XXX/USDC.
- **MiCA :**
  - USDT est exclu, car Kraken l'a retiré du trading pour les clients EEE. Les autres stablecoins non conformes et les actifs restreints dans l'EEE (dont XMR) sont exclus aussi.
  - **Spot long uniquement** : ni levier, ni marge, ni futures, ni vente à découvert. C'est un choix de prudence du projet, appliqué par la gateway moteur (`REJECTED_COMPLIANCE`), indépendamment de Grok.
- **L'USDC compte comme une crypto du portefeuille :**
  - il apparaît toujours comme une ligne (actif, quantité, valeur en USDC, poids %) sur la page `/v12/` et dans `public_state_v12.json`, à côté des positions ;
  - il reste la devise de compte et l'actif refuge, et il est exclu des signaux et des entrées.
- **Données manquantes :** une donnée absente ou un historique insuffisant (< 220 bougies journalières closes) est publié à `null`, jamais imputé. La paire est marquée `insufficient_history` et exclue des entrées. Le régime BTC utilise BTC/USDC.
- **Versions en 3 chiffres (x.y.z) :** le troisième chiffre est réservé aux correctifs, le deuxième à une vraie mise à jour (ex. ce changement = Moteur V1.6.1, UX V1.2.2). Le `VERSION_ENGINE` partagé de la V1.1 n'est pas concerné.
