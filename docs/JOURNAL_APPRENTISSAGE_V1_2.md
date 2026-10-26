# Journal d'apprentissage — Kraken Sim V1.2 (PAPER)

Tenu par Kraken - Bot Crypto à chaque revue (vers 8h et 19h, heure de Paris). PAPER uniquement, aucun ordre réel.

## 2026-10-26 08h (Paris) — revue n°1

**Observations.** Départ le 26/10 à 01h52 (Paris), capital 6 605,10 USDC, moteur V1.6.5, plafond 2 000 USDC. Enveloppe initiale répartie à parts égales (≈ 486 USDC chacun) sur BTC, ETH, SOL et XRP, 4 ordres taker acceptés, 0 refusé, slippage estimé 0,006 %, spread médian 0,005 %, aucune alerte LIQUIDITY_REVIEW, 4 paires éligibles. Frais payés 15,55 USDC. Valorisation au prix Kraken public de 06h50 UTC : environ 6 579 USDC, soit −26 USDC (−0,39 %) contre 0 % pour l'USDC et −0,08 % pour un maintien BTC sur la même période. Les frais expliquent l'essentiel de l'écart ; ETH, SOL et XRP ont un peu plus baissé que BTC. Le cycle de 05h04 UTC n'a vu aucun signal d'entrée A, C ou D (B signale les 4 actifs mais le budget restant n'est que de 41 USDC). Les cycles planifiés de 01h25 à 04h25 UTC n'ont pas tourné : le cron GitHub a sauté 4 créneaux, le seul run planifié est celui de 05h04 UTC, qui a réussi.

**Rapport GPT-6.** `v2/reports/2026-10-26.md` ne contient aucune donnée Kraken vérifiée (horodatage de collecte null). Ses prix externes (BTC 80 211 USD à 00h31 UTC) sont cohérents avec Kraken (BTC/USDC 79 935, plus bas 24 h 79 233), et sa lecture « prudence, biais défensif » est raisonnable mais non exploitable. Je n'en tire aucune décision.

**Hypothèse.** Avec un portefeuille investi à 98 % du plafond dès le départ, la performance des prochains jours dépendra presque entièrement du marché, pas des signaux ; les frais taker (≈ 0,2 %) pèsent sur une période courte.

**Décision.** Aucun changement de `strategy/v1_2/params.json` : 7 heures de données, c'est du bruit. Pas de correctif : les créneaux sautés viennent de la planification GitHub, pas d'un run en échec, et l'état est bien publié.

**À vérifier ensuite.** Que le cron horaire tourne régulièrement d'ici 19h (si plus de la moitié des créneaux manquent encore, envisager un filet de déclenchement) ; l'écart contre BTC hors frais ; si les signaux A, C ou D se déclenchent et seraient bloqués par le plafond.

## 2026-10-26 19h (Paris) — revue n°2

**Observations.** Depuis la revue de 8h, seulement 2 cycles planifiés ont tourné (11h20 et 17h29 UTC), tous deux réussis, état bien publié ; sur la journée, 4 créneaux horaires sur environ 16 ont été exécutés par le cron GitHub (`25 * * * *`), le reste a été sauté sans échec. Aucun nouvel ordre, 0 refus, aucune alerte LIQUIDITY_REVIEW, 4 paires éligibles, spread médian 0,016 %, slippage estimé 0,006 %. Signaux A, C, D : aucune entrée ; B signale toujours les 4 actifs, mais le budget restant n'est que de 41 USDC, donc HOLD. Valeur publiée à 17h30 UTC : 6 589,66 USDC ; revalorisée au prix public Kraken de 17h50 UTC (BTC 80 064, ETH 2 316,6, SOL 100,97, XRP 1,2966 USDC) : environ 6 587 USDC, soit −18 USDC (−0,28 %) depuis le départ et environ +8 USDC depuis 8h. En face, l'USDC fait 0 % et un maintien BTC +0,08 % depuis l'achat. Hors frais, le panier est à −0,15 % (ETH −0,3 %, SOL −0,4 %, XRP stable, BTC +0,08 %). Frais 15,55 USDC.

**Point appris.** Les frais simulés valent 0,8 % de chaque achat (3,89 USDC pour ≈ 486 USDC), et non 0,2 % comme je l'avais écrit ce matin : 0,2 % était leur poids rapporté au capital total. 0,8 % semble élevé pour du taker Kraken Pro ; l'API publique ne donne pas le barème des paires USDC, je ne peux donc pas le confirmer ici.

**Hypothèse de ce matin.** Validée : sans nouveau signal exploitable, la performance suit le marché, et les frais expliquent l'essentiel de l'écart avec l'USDC. Le doute sur le cron est confirmé : bien plus de la moitié des créneaux manquent.

**Rapport GPT-6.** Pas de nouveau rapport depuis ce matin ; `v2/reports/2026-10-26.md` reste sans donnée Kraken vérifiée. Rien à en tirer.

**Décision.** Aucun changement de `strategy/v1_2/params.json` : moins de 24 h de données et aucun signal bloqué de façon instructive. Pas de correctif moteur. Pour le cron, ce n'est pas une panne (aucun run en échec, état publié), mais la régularité est insuffisante ; je propose à Cyril un déclencheur de secours plutôt que de modifier le workflow seul.

**À vérifier ensuite.** Le taux de créneaux exécutés sur 24 h ; le barème réel de frais USDC (via le compte de Cyril en lecture, ou la doc Kraken) pour savoir si 0,8 % est trop pessimiste ; l'écart du panier contre BTC sur plusieurs jours (ETH et SOL plus faibles que BTC aujourd'hui).
