# Conformité UE/MiCA — Kraken Sim V1.2 (Moteur V1.6.1)

Date de vérification : 25/10/2026 (Paris). Simulation **PAPER** uniquement : aucune clé, aucun ordre réel.
Profil : particulier résidant en France (EEE), client de l'entité Kraken régulée MiCA.

Code : `v12_compliance.py` (constantes versionnées) ; appliqué par `v12_kraken_public.collect` (univers)
et par la gateway moteur `PaperEngine.admit_batch` (rejet `REJECTED_COMPLIANCE`), indépendamment de Grok
et de l'apprentissage.

## Règles retenues
| Règle | Statut | Source |
|---|---|---|
| Clients EEE servis par Payward Europe Solutions Ltd, CASP MiCA agréé par la Banque centrale d'Irlande (C468360), passeporté dans l'EEE | Vérifié (page Kraken) | https://support.kraken.com/articles/where-is-kraken-licensed-or-regulated ; https://blog.kraken.com/news/mica-license-central-bank-of-ireland (25/06/2025) |
| USDT et stablecoins non conformes (DAI, PYUSD, RLUSD, UST, EURT, TUSD, USDD, USDS) délistés pour l'EEE : ni achat ni vente | Vérifié (page Kraken, MAJ 13/04/2026) | https://support.kraken.com/gb/articles/stablecoin-offerings-for-eea-clients |
| Liste Kraken « EEA clients cannot deposit or trade » (dont USDT, XMR, XAUT, USDE, USD1…) appliquée en dur (`FR_RESTRICTED`) | Vérifié (page Kraken lue le 25/10/2026) | where-is-kraken-licensed-or-regulated |
| XMR délisté dans l'EEE depuis le 31/10/2024 | Vérifié | https://support.kraken.com/articles/support-for-monero-xmr-in-europe |
| USDC : e-money token émis dans l'EEE par Circle Internet Financial Europe SAS, EME agréé ACPR n° 17788 (conforme MiCA) | Vérifié (pages Circle) | https://www.circle.com/pressroom/circle-is-first-global-stablecoin-issuer-to-comply-with-mica-eus-landmark-crypto-law ; https://www.circle.com/legal/mica-redemption-policy |
| Paires accessibles à un résident FR = `AssetPairs?country_code=FR` (1 294 paires vs 1 463 sans filtre ; 37 XXX/USDC dont 35 `online`) | Vérifié (API publique, 25/10/2026 23h) | https://api.kraken.com/0/public/AssetPairs?country_code=FR |
| Pas de futures, marge, levier, vente à découvert : **spot long seulement** | **Choix de prudence du projet**, PAS une interdiction légale : Kraken propose aux clients EEE des dérivés (MiFID II, questionnaire d'adéquation) et de la marge financée en USDC/EURC | https://support.kraken.com/articles/derivatives-offerings-for-eea-clients ; https://support.kraken.com/articles/margin-conversion-eea |
| Spread ≤ 0,3 %, statut `online` | Règle interne du projet (déjà V1.1) | — |

## Non vérifié
- Que `country_code=FR` retire *tous* les actifs restreints FR (comportement non documenté publiquement par Kraken ; d'où la liste statique en plus).
- La conformité MiCA de chaque actif de base (livre blanc MiCA) : non contrôlée actif par actif.
- Aucune règle fiscale française (PFU, déclaration 2086/3916-bis) n'est modélisée.

## Univers
Uniquement XXX/USDC, `online`, `country_code=FR`, base hors stablecoins/fiat/wrapped et hors liste EEE, spread ≤ 0,3 %.
Aucune conversion XXX/USD → USDC (voie supprimée). Bougies journalières = OHLC XXX/USDC.
Historique < 220 bougies closes (SMA200 du régime BTC, EMA lente + 20) → `insufficient_history`,
`bars`/`sma200`/`donchian55` = null (jamais imputés), entrées refusées. Le régime BTC utilise BTC/USDC ;
son historique est publié dans `compliance.btc_regime_history`.
Limite connue : l'API OHLC publique Kraken renvoie au plus 720 bougies.
