# Journal d'apprentissage — Kraken Sim V1.2 (PAPER)

Tenu par Kraken - Bot Crypto à chaque revue (vers 8h et 19h, heure de Paris). PAPER uniquement, aucun ordre réel.

## 2026-10-26 08h (Paris) — revue n°1

**Observations.** Départ le 26/10 à 01h52 (Paris), capital 6 605,10 USDC, moteur V1.6.5, plafond 2 000 USDC. Enveloppe initiale répartie à parts égales (≈ 486 USDC chacun) sur BTC, ETH, SOL et XRP, 4 ordres taker acceptés, 0 refusé, slippage estimé 0,006 %, spread médian 0,005 %, aucune alerte LIQUIDITY_REVIEW, 4 paires éligibles. Frais payés 15,55 USDC. Valorisation au prix Kraken public de 06h50 UTC : environ 6 579 USDC, soit −26 USDC (−0,39 %) contre 0 % pour l'USDC et −0,08 % pour un maintien BTC sur la même période. Les frais expliquent l'essentiel de l'écart ; ETH, SOL et XRP ont un peu plus baissé que BTC. Le cycle de 05h04 UTC n'a vu aucun signal d'entrée A, C ou D (B signale les 4 actifs mais le budget restant n'est que de 41 USDC). Les cycles planifiés de 01h25 à 04h25 UTC n'ont pas tourné : le cron GitHub a sauté 4 créneaux, le seul run planifié est celui de 05h04 UTC, qui a réussi.

**Rapport GPT-6.** `v2/reports/2026-10-26.md` ne contient aucune donnée Kraken vérifiée (horodatage de collecte null). Ses prix externes (BTC 80 211 USD à 00h31 UTC) sont cohérents avec Kraken (BTC/USDC 79 935, plus bas 24 h 79 233), et sa lecture « prudence, biais défensif » est raisonnable mais non exploitable. Je n'en tire aucune décision.

**Hypothèse.** Avec un portefeuille investi à 98 % du plafond dès le départ, la performance des prochains jours dépendra presque entièrement du marché, pas des signaux ; les frais taker (≈ 0,2 %) pèsent sur une période courte.

**Décision.** Aucun changement de `strategy/v1_2/params.json` : 7 heures de données, c'est du bruit. Pas de correctif : les créneaux sautés viennent de la planification GitHub, pas d'un run en échec, et l'état est bien publié.

**À vérifier ensuite.** Que le cron horaire tourne régulièrement d'ici 19h (si plus de la moitié des créneaux manquent encore, envisager un filet de déclenchement) ; l'écart contre BTC hors frais ; si les signaux A, C ou D se déclenchent et seraient bloqués par le plafond.
