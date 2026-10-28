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

## 2026-10-27 08h (Paris) — revue n°3

**Observations.** Depuis la revue d'hier 19h, seulement 2 cycles planifiés ont tourné (22h48 et 02h13 UTC), tous deux réussis, état publié à 02h14 UTC. Depuis le départ, environ 6 créneaux horaires sur une trentaine ont été exécutés par le cron GitHub, aucun en échec. Aucun nouvel ordre, 0 refus, aucune alerte LIQUIDITY_REVIEW, 4 paires éligibles, spread médian 0,027 %, slippage estimé 0,006 %. Signaux A, C, D : aucune entrée ; B signale BTC, SOL et XRP, mais le budget restant (≈ 41 USDC) impose HOLD. Revalorisation au prix public Kraken de 06h50 UTC (BTC 79 551, ETH 2 303,5, SOL 99,69, XRP 1,2963 USDC) : environ 6 575 USDC, soit −30 USDC (−0,46 %) depuis le départ et −12 USDC depuis hier 19h. En face, l'USDC fait 0 % et un maintien BTC −0,56 % depuis l'achat. Hors frais, le panier est à environ −0,76 % (BTC −0,56 %, ETH −0,85 %, SOL −1,63 %, XRP 0,0 %). Frais cumulés 15,55 USDC.

**Rapport GPT-6.** Pas de rapport du 27/10 à cette heure (attendu avant 18h30) ; rien de neuf à revérifier.

**Hypothèses passées.** « La performance suit le marché » : confirmée une troisième fois, le recul de la nuit vient du marché (BTC −0,6 % sur 24 h). « ETH et SOL plus faibles que BTC » : confirmée sur 30 h, SOL est le plus gros contributeur négatif ; XRP compense. Toujours trop court pour en tirer une règle.

**Décision.** Aucun changement de `strategy/v1_2/params.json` : à peine 30 h de données, et aucun signal n'a été bloqué de façon instructive. Pas de correctif moteur. Le cron reste irrégulier mais pas en panne ; le déclencheur de secours reste une proposition à valider avec Cyril.

**À vérifier ensuite.** Sur 48 h, si l'écart SOL/ETH contre BTC se confirme (piste d'un poids réduit sur SOL, à ne décider qu'après plusieurs jours) ; le taux de créneaux exécutés ; le rapport GPT-6 du 27/10 et ses chiffres contre Kraken en direct.

## 2026-10-27 19h (Paris) — revue n°4

**Observations.** Depuis la revue de 8h, 2 cycles planifiés ont tourné (08h06 et 14h45 UTC), tous deux réussis, état publié à 14h45 UTC. Depuis le départ, 8 runs planifiés sur environ 40 créneaux horaires, aucun en échec. Aucun nouvel ordre, 0 refus, aucune alerte LIQUIDITY_REVIEW, 4 paires éligibles (BTC, ETH, SOL, XRP contre USDC). Signaux A, C, D : aucune entrée ; B signale BTC, SOL et XRP, budget restant ≈ 41 USDC, donc HOLD. Valeur publiée à 14h45 UTC : 6 593,60 USDC. Revalorisée au prix public Kraken de 17h48 UTC (BTC 80 582, ETH 2 349,27, SOL 101,07, XRP 1,3189 USDC) : environ 6 605,7 USDC, soit +0,6 USDC (+0,01 %) depuis le départ et +31 USDC depuis 8h. En face, l'USDC fait 0 % et un maintien BTC +0,73 % depuis l'achat. Hors frais, le panier est à +0,83 % (XRP +1,75 %, ETH +1,12 %, BTC +0,73 %, SOL −0,27 %). Frais cumulés 15,55 USDC, qui effacent à eux seuls le gain du panier. Drawdown max observé ≈ −30 USDC (−0,46 %, ce matin), loin du seuil de 25 %.

**Rapport GPT-6.** Aucun rapport `v2/reports/2026-10-27.md` à 18h48 (attendu avant 18h30), ni branche de rapport. Rien à revérifier ; à signaler.

**Hypothèses passées.** « La performance suit le marché » : confirmée une quatrième fois (rebond de la journée, BTC +1,3 % depuis ce matin). « ETH et SOL plus faibles que BTC » : invalidée pour ETH, qui passe devant BTC ; seule SOL reste en retard (−1 point contre BTC sur 40 h). Le classement entre actifs s'est inversé en 12 h : c'est du bruit, pas une règle.

**Point appris.** Sur 40 h, la diversification n'a ni aidé ni nui (panier +0,83 % contre BTC +0,73 % hors frais), mais les frais d'entrée de 0,8 % pèsent plus que tout l'écart de performance entre actifs. Le levier principal à court terme est le coût d'exécution, pas la sélection.

**Décision.** Aucun changement de `strategy/v1_2/params.json` : moins de 2 jours de données, et l'idée d'alléger SOL repose sur un écart que la journée a déjà en partie effacé. Pas de correctif : le cron est irrégulier (environ 1 créneau sur 5) mais aucun run n'échoue et l'état est publié.

**À vérifier ensuite.** Sur 3 à 4 jours, si SOL reste durablement sous BTC ; le barème réel des frais USDC (0,8 % simulé semble pessimiste) avant toute réflexion sur des ordres maker ; le taux de créneaux exécutés ; l'arrivée du rapport GPT-6.

## 2026-10-28 08h (Paris) — revue n°5

**Observations.** Depuis la revue d'hier 19h, 3 cycles planifiés ont tourné (20h09, 23h53 et 05h59 UTC), tous réussis, état publié à 05h59 UTC. Depuis le départ, 11 runs planifiés sur environ 53 créneaux horaires, aucun en échec. Aucun nouvel ordre, 0 refus, aucune alerte LIQUIDITY_REVIEW, 4 paires éligibles. Signaux : B signale les 4 actifs, C signale BTC (première entrée C observée), A et D rien ; budget restant ≈ 41 USDC, donc HOLD. Valeur publiée à 05h59 UTC : 6 612,08 USDC (nouveau plus haut moteur 6 612,74). Revalorisée au prix public Kraken de 06h55 UTC (BTC 80 802, ETH 2 349,7, SOL 101,90, XRP 1,3259 USDC) : environ 6 613,8 USDC, soit +8,7 USDC (+0,13 %) depuis le départ et +8 USDC depuis hier 19h. En face, l'USDC fait 0 % et un maintien BTC +1,01 % depuis l'achat. Hors frais, le panier est à +1,25 % (XRP +2,28 %, ETH +1,14 %, BTC +1,01 %, SOL +0,55 %). Frais cumulés 15,55 USDC. Drawdown max toujours ≈ −30 USDC (−0,46 %, le 27 au matin).

**Rapport GPT-6.** Toujours aucun rapport `v2/reports/2026-10-27.md` (seul celui du 26 existe). Rien à revérifier ; deuxième jour manquant, à signaler.

**Hypothèses passées.** « La performance suit le marché » : confirmée une cinquième fois. « SOL durablement sous BTC » : toujours vrai (−0,5 point) mais l'écart se réduit ; pas une règle. « Les frais pèsent plus que la sélection » : confirmée, le panier bat BTC de 0,24 point hors frais mais les 0,8 % d'entrée le font passer derrière (+0,13 % du capital total, soit environ +0,45 % sur la part investie, contre +1,01 % pour BTC).

**Décision.** Aucun changement de `strategy/v1_2/params.json` : 54 h de données seulement, aucun signal bloqué de façon instructive (l'entrée C sur BTC ne pourrait de toute façon pas s'exécuter, plafond quasi atteint). Pas de correctif : cron irrégulier mais sans échec, état publié.

**À vérifier ensuite.** Si le signal C sur BTC persiste (signe d'une tendance que le plafond empêche de suivre, à documenter sans toucher au plafond) ; l'écart SOL contre BTC sur 4 jours ; le barème réel des frais USDC ; l'arrivée du rapport GPT-6.
