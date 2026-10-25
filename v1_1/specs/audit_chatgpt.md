# Audit approfondi de Kraken Sim V1.04 : réduire le churn avant de chercher plus de signaux

## Verdict exécutif

La V1.04 a une base cohérente pour une stratégie spot de suivi de tendance, mais **son principal problème n'est probablement pas la qualité des indicateurs**. Il est surtout dans la mécanique de décision : synchronisation des bougies journalières, bascule binaire du régime BTC, renouvellement du top 3, logique de rééquilibrage et coût d'exécution.

Le point le plus important de cette recherche est le suivant : **le cas XMR du 25 octobre ne semble pas avoir été provoqué par un achat “juste après la clôture journalière”. C'est vraisemblablement l'inverse.** Le 25 octobre 2026, Paris était encore en heure d'été avant le changement d'heure de 03:00 ; à **01:14 heure de Paris, il était donc 23:14 UTC le 24 octobre**, soit **46 minutes avant** la clôture Kraken de 00:00 UTC. Kraken précise que ses données journalières basculent à minuit UTC et, surtout, que la dernière ligne renvoyée par l'API OHLC correspond toujours à la bougie **en cours, non encore validée**. citeturn18view10turn19view3turn18view0

Autrement dit, l'achat XMR s'est probablement fait avec le régime issu de la clôture précédente, puis une nouvelle clôture BTC est intervenue moins d'une heure plus tard et a inversé la règle B. **Interdire les achats pendant deux heures après la clôture n'aurait donc pas empêché ce trade.**

Mes priorités seraient, dans cet ordre :

| Priorité | Modification | Effet attendu |
|---|---|---|
| **Très haute** | Verrouiller les signaux journaliers sur la dernière bougie réellement clôturée en UTC | Élimine les incohérences de timing |
| **Très haute** | Filtrer directement les paires disponibles en France | Élimine les trades irréalisables comme XMR |
| **Très haute** | Introduire une hystérésis autour de l'EMA50 BTC | Évite les ventes/rachats sur un franchissement insignifiant |
| **Très haute** | Réduire le turnover du classement momentum | Probablement le meilleur levier rendement net/frais |
| **Haute** | Corriger la règle de rééquilibrage `10 % OU 25 $` | Évite de petits ordres coûteux |
| **Haute** | Maker pour les ordres non urgents, taker pour les sorties de risque | Réduit les frais sans sacrifier la protection |
| **Haute** | Utiliser les vrais paliers de frais Kraken dynamiquement | Rend la simulation beaucoup plus réaliste |
| **Moyenne** | Faire évoluer le sizing vers un risque basé sur l'ATR | Meilleure homogénéité du risque |
| **Moyenne** | Améliorer le coupe-circuit avec un drawdown depuis le plus-haut | Protège les gains accumulés |

Je **ne recommande pas**, en revanche, d'ajouter une durée minimale de détention à la règle B telle quelle. Une durée minimale peut empêcher une sortie légitime. Le meilleur traitement est de rendre le signal de rupture moins fragile, pas d'obliger artificiellement à rester investi.

Et je ne chercherais pas encore à optimiser RSI, MACD, ADX ou leurs périodes. Tant que la mécanique d'exécution et de rotation n'est pas assainie, le risque est de faire de l'optimisation de paramètres autour d'un problème essentiellement structurel.

## Le trade XMR révèle surtout un problème d'horloge

### La chronologie réelle est différente de l'intuition

Kraken indique que ses journées de marché commencent à **00:00 UTC**. citeturn19view3 Le 25 octobre 2026 est précisément le jour du passage de l'heure d'été à l'heure d'hiver en France : les horloges parisiennes ont reculé de 03:00 à 02:00. Avant ce recul, Paris était encore en UTC+2. citeturn18view10

La chronologie de ton exemple devient donc :

| Événement | Heure Paris | Heure UTC | Situation |
|---|---:|---:|---|
| Achat XMR | 25/10 01:14 | **24/10 23:14 UTC** | **46 min avant la nouvelle clôture daily** |
| Clôture Kraken daily | 25/10 02:00 Paris, première occurrence | **25/10 00:00 UTC** | Nouveau BTC daily validé |
| Vente XMR | 25/10 02:14 Paris | 00:14 ou 01:14 UTC selon l'occurrence de 02:14 | Dans tous les cas **après** la clôture |

Il y a une ambiguïté sur le `02:14` local car cette heure existe deux fois le jour du changement d'heure. Elle ne change toutefois pas le diagnostic : **la vente se produit après la clôture UTC et l'achat avant**. citeturn18view10

Le scénario le plus probable est donc :

> régime BTC haussier sur la clôture J-1 → achat à 23:14 UTC → clôture J à 00:00 UTC légèrement sous EMA50 → régime baissier → règle B → vente.

Cela signifie que la V1.04 autorise une nouvelle position dont la validité peut expirer **46 minutes plus tard sur simple renouvellement de la donnée journalière**.

C'est un défaut de conception plus important qu'une hésitation autour du seuil EMA.

### Il existe en plus un piège explicite dans l'API OHLC Kraken

La documentation Kraken dit sans ambiguïté que **la dernière entrée du tableau OHLC est toujours celle de la période courante, non encore validée**. Elle est renvoyée même si elle n'est pas demandée. citeturn18view0

Donc, pour des indicateurs daily, le bot ne doit jamais supposer que :

```text
ohlc[-1] = dernière journée clôturée
```

Pour l'API Kraken, ce sera normalement :

```text
ohlc[-2] = dernière bougie clôturée
ohlc[-1] = journée en cours
```

Encore plus robuste : ne pas dépendre seulement de l'indice. Il faut contrôler explicitement le timestamp et exiger que la bougie utilisée corresponde à la dernière période quotidienne entièrement achevée.

### Ce que je modifierais

Je remplacerais la règle « pas d'achat pendant deux heures après la clôture » par une architecture beaucoup plus nette :

**Les indicateurs daily sont calculés une seule fois par jour, après la clôture UTC, sur des bougies explicitement validées.**

Par exemple :

```text
00:00 UTC        clôture théorique
00:05–00:10 UTC  récupération + validation des données
                 calcul BTC + univers + indicateurs + classement
                 gel du snapshot daily jusqu'au lendemain
```

Les dix cycles intrajournaliers conserveraient alors leur utilité, mais uniquement pour :

- vérifier les stops ;
- surveiller le carnet ;
- envoyer ou ajuster les ordres ;
- contrôler les fills ;
- éventuellement constater une dégradation exceptionnelle de liquidité.

Ils **ne recalculeraient plus EMA50, MACD, RSI, ADX ou classement momentum à partir d'une bougie daily en formation**.

J'ajouterais également une petite **zone interdite avant la clôture**, par exemple 30 à 60 minutes avant 00:00 UTC, parce qu'il est économiquement peu rationnel d'ouvrir à 23:45 un trade dont le filtre journalier sera entièrement réévalué quinze minutes après. Le bon seuil doit être backtesté ; 30, 45 et 60 minutes sont de bons candidats.

Cette solution est supérieure au « +2 h après clôture » parce qu'elle traite directement la cause et fonctionne indépendamment de l'heure d'été/hiver.

### Le trade XMR n'aurait de toute façon pas dû exister pour un compte français

Kraken a arrêté le trading de toutes les paires XMR pour les clients de l'Espace économique européen le **31 octobre 2024**, puis les retraits XMR le 31 décembre 2024. citeturn18view3

Plus intéressant encore : il n'est plus nécessaire de maintenir manuellement une blacklist réglementaire. L'API publique `AssetPairs` de Kraken accepte aujourd'hui un paramètre `country_code` qui permet de ne retourner que les paires disponibles dans le pays/région demandé. Pour la France :

```text
country_code=FR
```

Kraken documente explicitement cette fonction avec le code ISO du pays. citeturn18view1

La construction de l'univers devrait donc partir de quelque chose conceptuellement équivalent à :

```text
AssetPairs(
    assetVersion=1,
    aclass_base="currency",
    country_code="FR"
)
```

puis appliquer les exclusions stablecoins/or/wrapped BTC et les critères de liquidité. Kraken distingue également dans cette API les paires spot `currency` des actifs tokenisés, ce qui permet d'éviter une partie des exclusions bricolées à la main. citeturn18view1

**Conclusion sur le cas XMR : deux contrôles indépendants auraient dû bloquer l'opération** : incompatibilité réglementaire avec la France, puis proximité immédiate de la clôture UTC.

## Là où la V1.04 perd probablement le plus d'argent

### Les frais imposent un hurdle beaucoup plus élevé qu'il n'y paraît

Tes chiffres XMR sont cohérents.

Pour 3,57 XMR :

- achat : `3,57 × 609,98 = 2 177,63 $` ;
- vente : `3,57 × 613,10 = 2 188,77 $` ;
- profit brut : **+11,14 $**, soit environ **+0,511 %** ;
- commissions à 0,80 % sur chaque jambe : **34,93 $** ;
- résultat après commissions : environ **−23,79 $**, avant même d'isoler d'éventuels autres effets de slippage.

Avec un taux de 0,80 % à l'achat et 0,80 % à la vente, un trade doit monter d'environ **1,613 % rien que pour compenser les commissions**, en tenant compte de leur effet multiplicatif. Avec ton hypothèse supplémentaire de 0,05 % de slippage par jambe, le seuil approche **1,715 %**, avant tout coût résiduel qui ne serait pas déjà intégré par les prix ask/bid.

Kraken affiche actuellement pour le spot Tier 1 **0,40 % maker et 0,80 % taker**. À partir de 2 500 $ de volume spot roulant sur 30 jours, les taux passent à **0,30 % / 0,60 %**, puis à partir de 10 000 $ à **0,22 % / 0,38 %**. citeturn19view0

À l'échelle de tes 6 605,10 $, un achat puis une vente de tout le portefeuille au Tier 1 coûte théoriquement :

| Exécution | Commissions aller-retour | + hypothèse 0,05 %/jambe | Coût sur 6 605,10 $* |
|---|---:|---:|---:|
| Taker → taker | 1,60 % | ~1,70 % | ~112,29 $ |
| Maker → taker | 1,20 % | ~1,30 % | ~85,87 $ |
| Maker → maker | 0,80 % | ~0,90 % | ~59,45 $ |

\*Ordre de grandeur avant prise en compte exacte du spread et des éventuels fills partiels.

Le message n'est donc pas seulement « préférer maker ». Il est surtout :

> **chaque rotation doit justifier économiquement son coût total.**

Une différence minuscule de score momentum, de poids cible ou de position par rapport à l'EMA ne constitue pas une justification suffisante.

### Ton simulateur surestime probablement les frais après les premiers trades

Si la V1.04 applique **0,80 % à tous les ordres pour toujours**, elle n'est plus conforme à la grille actuelle dès que le volume roulant dépasse les seuils Kraken. Un portefeuille de 6 605 $ qui effectue une seule entrée significative de quelques milliers de dollars atteint très rapidement le Tier 2 de 2 500 $ de volume. Kraken calcule le volume spot sur une fenêtre roulante de trente jours. citeturn19view0

Kraken fournit même une API `TradeVolume` qui renvoie :

- le volume USD 30 jours ;
- le barème applicable ;
- les frais taker ;
- les frais maker.

citeturn18view7

Donc **il ne faut plus coder en dur `taker_fee = 0.008`** dans une simulation destinée à reproduire un compte Kraken.

Je modéliserais le palier de frais trade après trade, ou j'interrogerais l'API dans le bot réel.

Cela ne rend pas les rotations gratuites : même au Tier 3, les coûts restent significatifs. Mais cela évite de conclure à tort qu'une stratégie est non rentable parce qu'on lui applique en permanence le tarif maximal.

### La règle de rééquilibrage contient vraisemblablement un défaut logique

Ta règle dit :

> rééquilibrage seulement si l'écart à la cible dépasse **10 % ou 25 $**.

Pour une position cible d'environ 2 180 $, 10 % représentent environ **218 $**.

Avec un `OR`, dès que la position diffère de 25 $, le critère est satisfait. Le seuil de 10 % devient donc presque inutile :

```text
écart = 40 $
40 $ > 25 $  → oui
40 $ > 218 $ → non
OR            → rééquilibrage
```

Or un ordre de 40 $ peut supporter plusieurs dizaines de points de base de coûts pour corriger une erreur de poids économiquement insignifiante.

Je pense que l'intention réelle était plutôt :

```text
abs(delta_usd) > max(25 $, 10 % × target_usd)
```

ou, exprimé autrement, **les deux conditions doivent être dépassées**.

C'est exactement le genre de comportement que la littérature sur les coûts de transaction formalise sous la notion de *no-trade region* : lorsqu'il existe des coûts proportionnels, il peut être optimal de laisser le portefeuille dériver à l'intérieur d'une zone autour de la cible plutôt que de corriger chaque petit écart. citeturn19view2turn19view5

Dans ton contexte, j'irais même plus loin : **pas de rééquilibrage cosmétique**. Une position déjà ouverte ne devrait être ajustée que si le changement est suffisamment important pour modifier réellement le risque.

### Le « top 3 momentum » mérite d'être beaucoup plus contesté que les cinq confirmations

Les cinq confirmations donnent l'impression d'une forte diversification du signal, mais quatre d'entre elles reposent principalement sur des transformations différentes de la même information : le prix passé.

EMA, MACD, RSI et ADX/+DI ne sont donc pas quatre sources indépendantes d'information. Une crypto en tendance régulière peut mécaniquement satisfaire plusieurs de ces conditions à la fois.

Cela ne rend pas ces indicateurs inutiles. Cela signifie simplement qu'un score « 5/5 » ne doit pas être interprété comme cinq preuves indépendantes.

Plus important : une étude publiée le 13 octobre 2026 dans *The Review of Asset Pricing Studies* a réévalué le momentum crypto en intégrant des frictions plus réalistes. Les auteurs trouvent des preuves solides de **momentum en série temporelle** — autrement dit, la tendance propre d'un actif — mais très peu de preuves robustes de **momentum transversal**, c'est-à-dire l'idée que les cryptos récemment les plus fortes continueront nécessairement à surperformer les autres. Sous des hypothèses réalistes, beaucoup de portefeuilles de momentum transversal se comportent nettement moins bien que leurs rendements moyens bruts ne le laissent penser. citeturn19view1

C'est directement pertinent ici :

- tes conditions 1 à 5 sont surtout des filtres de **tendance absolue** ;
- ton « top 3 » et surtout la sortie C introduisent un mécanisme de **rotation relative entre cryptos**.

Je conserverais volontiers le classement pour décider **qui acheter lorsqu'une place est libre**. Je serais beaucoup plus réticent à l'utiliser pour vendre régulièrement un actif encore sain simplement parce qu'il passe momentanément de la troisième à la quatrième place.

### La sortie C est une source probable de churn

Supposons :

```text
Jour 1 : A #1, B #2, C #3, D #4
Jour 2 : A #1, B #2, D #3, C #4
```

Avec la V1.04, C devient vendable après 24 h et D peut le remplacer, même si :

- C est toujours au-dessus de son EMA50 ;
- son MACD reste positif ;
- son RSI reste favorable ;
- son ADX reste favorable ;
- son stop ATR est loin ;
- la différence de momentum entre C et D est minime.

Tu paies alors une vente, puis un achat, pour transformer un bon actif en un autre bon actif à cause d'un classement qui peut s'inverser à nouveau le lendemain.

À 0,8 % taker de chaque côté, ce comportement est extrêmement coûteux. Même avec maker, il reste coûteux et introduit un risque de non-remplissage.

Je remplacerais le top 3 strict par une **zone tampon de classement** :

```text
ENTRÉE : candidat dans le top 3
MAINTIEN : position existante tant qu'elle reste dans le top 5
SORTIE C : seulement si rang > 5
```

Une variante plus exigeante demanderait également qu'un remplaçant soit **significativement meilleur**, par exemple :

```text
score_challenger > score_position × 1,10
```

ou un écart normalisé minimal.

Les valeurs top 5 et +10 % ne doivent pas être prises comme vérités ; elles constituent des paramètres à tester. Le principe est ce qui compte : **hystérésis dans le classement**.

## Une V1.05 plus robuste

Je recommanderais de ne pas bouleverser simultanément tous les paramètres techniques. La V1.05 devrait surtout corriger l'architecture. Les indicateurs de V1.04 peuvent rester temporairement identiques afin de mesurer proprement le bénéfice des changements.

### Univers

La nouvelle séquence serait :

```text
1. Récupérer les AssetPairs Kraken avec country_code=FR
2. Garder uniquement spot / USD
3. Exclure stablecoins, or tokenisé, wrapped BTC
4. Éliminer les marchés trop larges en spread
5. Contrôler la profondeur réellement exécutable pour la taille prévue
6. Prendre les 10 plus liquides
7. Geler cet univers pour la journée
```

Le filtrage `country_code=FR` est directement fourni par Kraken. citeturn18view1

Je conserverais le filtre de spread, mais je testerais des plafonds de **0,10 %, 0,20 % et 0,30 %** plutôt que de présumer que 0,30 % est optimal.

Le volume 24 h seul ne suffit pas à mesurer l'exécutabilité d'un ordre d'environ 2 000 $. Le carnet compte. Pour chaque ordre prévu, il faut calculer le **VWAP obtenu en consommant réellement les niveaux du carnet** et rejeter l'opération si l'impact est excessif. Kraken fournit son carnet d'ordres via ses API marché. citeturn18view1

L'univers peut être recalculé une fois par jour. Pendant la journée, une forte dégradation du spread ou de la profondeur peut empêcher un ordre, mais je ne referais pas le classement complet à chaque cycle : cela ajoute une nouvelle source de turnover sans apporter de nouvelle information à des signaux daily.

### Régime BTC

Le filtre actuel est :

```text
BTC close > EMA50  => ON
BTC close <= EMA50 => OFF
```

C'est un comparateur sans mémoire. Une différence de quelques dollars peut donc transformer instantanément :

```text
100 % autorisé
```

en :

```text
0 % autorisé + liquidation de tout le portefeuille
```

alors que l'état économique du marché n'a pratiquement pas changé.

Ta proposition d'une marge de +1 % va dans le bon sens, mais j'utiliserais plutôt une marge **proportionnelle à la volatilité du BTC**.

Par exemple :

```text
borne haute = EMA50 + k × ATR14
borne basse = EMA50 - k × ATR14
```

avec un `k` à tester, par exemple 0,15 ; 0,25 ; 0,50.

Le régime deviendrait :

```text
Close > borne haute
    => BULL

Close < borne basse
    => BEAR

entre les deux
    => conserver le régime précédent
```

C'est un filtre à hystérésis : il faut franchir une borne plus haute pour entrer dans un état et une borne plus basse pour en sortir.

Il traite précisément ton problème :

```text
EMA50 = 100
close hier = 100,05
close aujourd'hui = 99,98
```

ne doit probablement pas provoquer une liquidation massive uniquement à cause de 0,07 % de variation autour d'un seuil arbitraire.

### Je séparerais « interdiction d'acheter » et « liquidation du portefeuille »

C'est, à mon avis, une amélioration encore plus importante.

Le fait que le BTC soit légèrement sous EMA50 peut raisonnablement signifier :

> « Je ne veux plus ouvrir de nouvelles positions. »

Cela ne signifie pas nécessairement :

> « Je dois immédiatement vendre trois cryptos dont les tendances propres sont encore intactes. »

Je créerais trois états :

| État BTC | Nouvelles entrées | Positions existantes |
|---|---|---|
| **Risk-on** | Autorisées | Maintenues normalement |
| **Neutre / prudence** | Interdites | Stops et tendance propre continuent |
| **Hard risk-off** | Interdites | Sortie accélérée / liquidation |

Illustration à backtester :

```text
Risk-on:
BTC close > EMA50 + 0,25 ATR

Prudence:
entre les deux bandes

Hard risk-off:
BTC close < EMA50 - 0,25 ATR
```

Ou, si tu veux une asymétrie plus prudente :

```text
close < EMA50          => plus aucun achat
close < EMA50 - 0,5ATR => liquidation des positions
```

Je préfère cette construction à « deux clôtures consécutives » : deux clôtures réduisent effectivement les faux franchissements, mais peuvent retarder une véritable sortie d'une journée entière. Une bande d'hystérésis fournit un mécanisme plus continu.

### Règle B : pas de durée minimale obligatoire

Je modifierais :

```text
close crypto < EMA50
```

en quelque chose comme :

```text
close crypto < EMA50 - k × ATR14
```

ou éventuellement :

```text
deux clôtures sous EMA50
```

mais **je ne mettrais pas « interdiction de vendre avant 24 h » sur une vraie cassure**.

Pourquoi ?

Parce qu'une durée minimale règle le symptôme ainsi :

> « le signal de sortie est mauvais, donc je vais l'ignorer pendant X heures. »

L'hystérésis règle le problème ainsi :

> « je vais rendre le signal suffisamment robuste pour qu'un bruit minuscule ne soit plus considéré comme une cassure. »

Une fois la synchronisation UTC corrigée, un trade entré après une vraie clôture quotidienne ne peut de toute façon plus être invalidé par la clôture quotidienne suivante avant presque 24 heures. Le besoin de verrouiller artificiellement la position disparaît donc en grande partie.

### Conditions d'achat

Pour la première V1.05, je garderais :

```text
1 obligatoire + 3 confirmations sur les 4 restantes
```

afin de ne pas changer trop de variables simultanément.

À l'étape suivante, je challengerais cependant ce montage avec une version plus simple :

```text
Tendance obligatoire :
Close > EMA50
EMA20 > EMA50

Momentum absolu :
rendement / volatilité positif au-dessus d'un seuil

Force de tendance :
ADX / DI

Volume :
simple filtre secondaire
```

Le classement devrait également être défini mathématiquement. « Momentum » est actuellement trop vague pour qu'une stratégie soit réellement reproductible. Il faut savoir s'il signifie :

```text
rendement 7 jours ?
rendement 20 jours ?
rendement 30 jours ?
MACD normalisé ?
distance à EMA20 ?
mélange de plusieurs horizons ?
```

Je préférerais un score ajusté de la volatilité, par exemple conceptuellement :

```text
momentum_20j = rendement_20j / volatilité_20j
```

ou :

```text
score = rendement_20j / (ATR14 / prix)
```

plutôt qu'un rendement brut qui tend à favoriser mécaniquement les actifs très volatils.

La littérature récente en faveur du momentum crypto est beaucoup plus convaincante pour le comportement propre d'un actif dans le temps que pour la rotation permanente vers les gagnants relatifs. citeturn19view1

### Position sizing

Trois positions de 33 % sont simples et lisibles. En revanche, elles ne représentent pas trois risques identiques.

Exemple :

```text
Crypto A : ATR/price = 2 %
Crypto B : ATR/price = 5 %
```

Avec ton stop à `3 × ATR`, le risque de prix approximatif avant glissement est respectivement autour de :

```text
A : 6 %
B : 15 %
```

Une allocation de 33 % sur les deux donne donc beaucoup plus de poids de risque à B.

Une évolution possible serait :

```text
taille = budget_de_risque / distance_du_stop
```

avec :

```text
distance_stop_pct = 3 × ATR14 / prix
```

et toujours un plafond de 35 %.

Je ne l'imposerais pas dès la V1.05, car cela change fortement la construction du portefeuille. Ce serait un test séparé. L'égalité de risque peut améliorer la stabilité sans nécessairement améliorer le rendement brut.

Et surtout : **je n'obligerais pas le bot à détenir trois cryptos**. S'il n'y a qu'un ou deux signaux suffisamment forts, conserver du cash est préférable à prendre un troisième actif simplement pour remplir un slot.

### Nouvelle sortie C

Ma version de départ serait :

```text
Évaluation : une fois par jour après clôture UTC
Détention minimale : 24 h ou 48 h à tester

Vente seulement si :
    rang actuel > 5
AND
    un remplaçant valide existe
AND
    amélioration de score suffisamment grande
```

Je testerais 24 / 48 / 72 h, mais mon intuition est que le **buffer top 3 → top 5** sera plus important que la durée minimale elle-même.

Cette conception revient à créer une *no-trade region* dans l'espace du classement, cohérente avec le principe général selon lequel les coûts de transaction rendent les corrections permanentes autour d'une cible sous-optimales. citeturn19view2turn19view5

### Stop suiveur ATR

Le stop `highest since entry – 3 × ATR14` est l'une des règles que je changerais le moins au départ.

Il a deux avantages conceptuels :

- il s'élargit lorsque la volatilité est élevée ;
- il se resserre relativement lorsque la volatilité diminue.

Je vérifierais néanmoins précisément la définition de `highest since entry`.

Si le stop est recalé sur chaque micro-pic intrajournalier mais que l'ATR reste quotidien, tu mélanges deux horizons. Une mèche intraday peut relever définitivement le stop alors que le reste de la logique est daily.

Deux variantes doivent être comparées :

```text
A. plus haut tick/intraday depuis entrée - 3 ATR daily
B. plus haut journalier clôturé depuis entrée - 3 ATR daily
```

Je ne présume pas que B sera supérieure ; c'est un test à effectuer.

### Coupe-circuit

Le seuil actuel :

```text
equity < 70 % × capital_initial
```

donne :

```text
4 623,57 $
```

Il protège le capital initial, mais pas les profits accumulés.

Si le portefeuille passe par exemple de 6 605 $ à 10 000 $, le coupe-circuit reste à 4 623,57 $. Il autoriserait donc une perte de plus de la moitié du pic avant arrêt.

Je séparerais deux mécanismes :

```text
Hard floor absolu :
70 % du capital initial

Contrôle du drawdown :
X % sous le plus haut d'équité
```

avec, par exemple, 20–25 % de drawdown à tester pour une mise en sécurité ou une suspension des nouvelles entrées. Je ne transformerais pas nécessairement ce deuxième seuil en arrêt définitif : il peut simplement placer le bot en cash jusqu'à un nouveau régime haussier confirmé.

## Exécution : maker oui, mais surtout pas partout

### Les entrées devraient devenir « maker-first »

Kraken explique qu'un ordre limite peut être exécuté en maker s'il ne traverse pas le carnet. L'option **Post Only** garantit ce comportement : si l'ordre devait prendre immédiatement de la liquidité, il est annulé plutôt que converti en taker. Kraken rappelle également qu'un ordre limite peut n'être que partiellement exécuté. citeturn18view6

Je ferais donc :

```text
Entrée :
Post-only limit
prix = best bid ou amélioration d'un tick
TTL = 10 à 30 min à tester
si non rempli :
    annulation
    réévaluation au cycle suivant
```

Le simulateur ne doit surtout pas supposer :

```text
ordre maker placé = ordre maker exécuté
```

C'est faux. Le gain de frais maker est la rémunération de l'attente et du risque de non-exécution.

### Les sorties C et les rééquilibrages peuvent aussi être maker

Une sortie de classement n'est pas urgente.

Donc :

```text
Sortie C             → maker-first
Rééquilibrage        → maker-first
Prise de profit lente → maker-first
```

La patience y est cohérente.

### Les stops et vraies ruptures doivent rester prioritaires sur les frais

Pour un stop A ou un vrai régime `hard risk-off`, je privilégierais la certitude d'exécution.

Un stop-limit n'est pas équivalent à une protection garantie : Kraken précise qu'il existe un risque que l'ordre limite déclenché ne soit pas exécuté si le marché chute trop vite. citeturn19view4

Donc :

```text
Stop A              → taker / exécution immédiate
Hard BTC risk-off   → taker
Cassure crypto forte → taker

Sortie non urgente  → maker
```

Payer 0,20 ou 0,40 point de pourcentage supplémentaire pour sortir d'un risque qui s'effondre peut être parfaitement rationnel.

La bonne stratégie n'est donc pas **« tout maker »**, mais **« maker lorsque le temps n'a pas de valeur, taker lorsque le risque a plus de valeur que l'économie de frais »**.

### Il faut simuler le carnet, pas un slippage forfaitaire identique partout

Ton `+0,05 %` de slippage est pratique, mais trop homogène.

Pour un ordre de 2 000 $ :

- BTC/USD peut avoir quasiment aucune profondeur consommée ;
- une altcoin de dixième rang peut traverser plusieurs niveaux ;
- un marché peut être liquide à midi et beaucoup moins quelques heures après.

Kraken expose les données nécessaires au carnet et les ordres limites peuvent être partiellement remplis en fonction de la liquidité disponible. citeturn18view6turn18view1

Je remplacerais progressivement :

```text
slippage = 0,05 %
```

par :

```text
slippage_taker =
VWAP du carnet pour la quantité à exécuter
- meilleur prix
```

Pour les ordres maker, le coût principal devient différent : fill partiel, non-fill et éventuellement mauvais *selection timing* plutôt qu'un slippage mécanique.

### La grille de frais doit évoluer avec le volume

La simulation réaliste devrait enregistrer avant chaque exécution :

```text
rolling_volume_30d
maker_fee
taker_fee
```

Kraken fournit précisément ces informations avec `TradeVolume`. citeturn18view7

Avec ta taille de portefeuille, le passage de :

```text
0,40 / 0,80
```

à :

```text
0,30 / 0,60
```

peut arriver très vite, puis le palier `0,22 / 0,38` devient accessible à 10 000 $ de volume spot roulant. citeturn19view0

C'est particulièrement important quand on compare les variantes : une stratégie qui tourne davantage paie plus de commissions, mais peut aussi descendre plus vite dans les paliers. Il faut donc laisser le simulateur calculer cet effet plutôt que l'imposer a priori.

## Spécification V1.05 que je testerais en premier

Voici la version que je considérerais comme le meilleur compromis entre amélioration réelle et absence de sur-optimisation.

| Bloc | V1.04 | V1.05 proposée |
|---|---|---|
| **Horloge** | Cycles heure de Paris | Heure UTC Kraken pour tout ce qui est daily |
| **OHLC** | À contrôler | Toujours dernière bougie **committed**, jamais celle en cours ; Kraken confirme que la dernière entrée OHLC est non clôturée. citeturn18view0 |
| **Calcul daily** | Potentiellement chaque cycle | Une fois vers 00:05–00:10 UTC, puis snapshot gelé |
| **Fenêtre pré-clôture** | Aucune | Pas de nouvel achat dans les 30–60 min avant 00:00 UTC |
| **France** | Liste mondiale | `country_code=FR`, fourni par Kraken. citeturn18view1 |
| **Liquidité** | spread ≤0,3 %, top 10 volume | Même logique + VWAP/depth à la taille réelle |
| **Régime BTC** | close > EMA50, binaire | Zone d'hystérésis autour EMA50, normalisée ATR |
| **BTC légèrement faible** | liquidation | Bloque d'abord les nouveaux achats |
| **BTC franchement faible** | liquidation | Maintenue comme sortie de risque |
| **Achats** | 4/5 dont #1 | Inchangé dans un premier test |
| **Classement** | top 3 strict | top 3 pour entrer, buffer top 5 pour rester |
| **Sortie C** | dès 24 h | une fois/jour + rang >5 + remplaçant vraiment meilleur |
| **Rééquilibrage** | >10 % **OU** >25 $ | `delta > max(10 % cible, 25 $)` |
| **Entrée** | taker | post-only maker-first |
| **Sortie C** | taker | maker-first |
| **Stop A / hard B** | taker | taker conservé |
| **Frais** | Tier 1 fixe | palier dynamique via volume 30 j ; Kraken publie les seuils et l'API associée. citeturn19view0turn18view7 |
| **Stop** | 3 ATR | Inchangé initialement |
| **Sizing** | 33 % | Inchangé initialement, ATR-risk en variante |
| **Circuit breaker** | −30 % initial | floor initial + test d'un drawdown depuis peak |

### Pseudo-logique

```text
À 00:05 UTC :

    récupérer uniquement les paires Kraken autorisées pour FR

    charger OHLC daily
    supprimer/rejeter toute bougie non clôturée

    calculer :
        BTC EMA50 / ATR
        indicateurs des actifs
        volume
        momentum
        classement

    déterminer regime_BTC :
        si close > EMA50 + band:
            RISK_ON
        elif close < EMA50 - band:
            HARD_RISK_OFF
        else:
            NEUTRAL / conserver état selon variante

    geler le snapshot daily


À chaque cycle intraday :

    mettre à jour :
        bid / ask
        carnet
        high depuis entrée
        trailing stops
        ordres ouverts et fills

    priorité 1 :
        si stop A touché:
            vente taker immédiate

    priorité 2 :
        si HARD_RISK_OFF:
            vente selon règle de risque

    priorité 3 :
        si cassure propre de l'actif confirmée:
            sortie

    priorité 4 :
        une seule fois par jour,
        si détenu >= durée mini C
        et rang > seuil de maintien
        et challenger suffisamment meilleur:
            rotation maker-first

    achats :
        uniquement RISK_ON
        pas près de la prochaine clôture UTC
        candidat valide
        place libre
        carnet acceptable
        ordre post-only
```

### Le point essentiel : réduire les décisions, pas augmenter leur fréquence

Tes dix cycles par jour ne me gênent pas **si chaque cycle n'est pas une nouvelle occasion de changer d'avis sur un signal daily**.

Je les verrais plutôt ainsi :

```text
1 décision stratégique / jour
10 occasions d'exécuter correctement cette décision
```

et non :

```text
10 recalculs implicites d'une stratégie construite sur des données daily
```

C'est une différence fondamentale.

Un bot qui analyse des tendances journalières n'a pas besoin de prendre dix décisions de portefeuille par jour. Il peut en revanche avoir intérêt à surveiller dix fois par jour ses stops et sa qualité d'exécution.

## Comment déterminer objectivement si la V1.05 est meilleure

Aucune valeur comme `0,25 ATR`, `top 5`, `48 h` ou `15 min de TTL` ne devrait être considérée comme optimale sans backtest. Le but n'est pas de remplacer des paramètres arbitraires par d'autres paramètres arbitraires.

Kraken fournit des historiques OHLCVT téléchargeables, notamment en 1, 5, 15, 60, 240, 720 et 1 440 minutes ; les données contiennent timestamp, open, high, low, close, volume et nombre de trades. Kraken précise également que les intervalles sans transaction ne sont pas remplis artificiellement. citeturn18view8

Kraken propose également ses historiques *time-and-sales*, avec chaque trade public et notamment timestamp, prix, volume, sens et type d'ordre. citeturn18view9

Cela permet une validation beaucoup plus sérieuse qu'un backtest purement daily.

### Je ferais un test par ablation

Ne teste surtout pas directement :

```text
V1.04
vs
nouvelle stratégie avec 15 changements
```

Si V1.05 gagne, tu ne sauras pas pourquoi.

Je construirais plutôt :

| Variante | Changement ajouté |
|---|---|
| **Base** | V1.04 reproduite exactement |
| **Clock** | Bougies committed + synchronisation UTC + zone pré-clôture |
| **France** | + univers `country_code=FR` |
| **Fees** | + barème Kraken roulant dynamique |
| **Execution** | + maker-first sur flux non urgents |
| **Regime** | + hystérésis BTC |
| **Rank buffer** | + top 3 entrée / top 5 maintien |
| **Rebalance** | + vraie zone de non-rééquilibrage |
| **Risk sizing** | + sizing ATR, en dernier |

Ainsi, tu peux mesurer le rendement marginal de chaque amélioration.

### Les métriques à regarder sont différentes du simple rendement

Comme ton objectif explicite est **« meilleur rendement net de frais, avec un nombre d'allers-retours limité »**, le rendement brut ne doit pas être l'indicateur principal.

Je suivrais conjointement :

| Mesure | Pourquoi elle compte |
|---|---|
| Rendement net | Objectif final |
| Drawdown maximal | Risque réellement subi |
| Frais / P&L brut | Part de l'alpha consommée par Kraken |
| Turnover mensuel | Intensité de rotation |
| Nombre d'allers-retours/mois | Ton objectif explicite |
| Durée médiane de détention | Détecte le churn |
| Profit médian **net** par trade | Plus informatif que le win rate seul |
| Profit factor net | Qualité du système après coûts |
| Exposition moyenne | Savoir si le rendement vient de plus de risque |
| Taux de fill maker | Vérifier que l'économie théorique de frais existe réellement |
| Temps d'attente maker | Mesurer le coût d'opportunité |
| Trades maker ratés | Signal parti sans le bot |
| Slippage des sorties urgentes | Réalisme des stops |
| Nombre de rotations C | Détecter la source principale de frais |

J'accorderais notamment beaucoup d'attention à :

```text
frais / profit brut
```

Si une variante produit 1 000 $ de profits avant coûts mais en abandonne 700 $ en spread, frais et slippage, elle est bien moins robuste qu'une variante générant 700 $ brut et n'en abandonnant que 150 $.

### Grille de paramètres raisonnable

Pour ne pas exploser le nombre de combinaisons, je limiterais les tests à quelques valeurs économiquement interprétables :

| Paramètre | Valeurs à tester |
|---|---|
| Bande BTC | 0 ; 0,15 ; 0,25 ; 0,50 ATR |
| Rang de maintien | 3 ; 4 ; 5 ; 6 |
| Détention mini C | 24 ; 48 ; 72 h |
| TTL maker | 5 ; 15 ; 30 ; 60 min |
| Spread max | 0,10 ; 0,20 ; 0,30 % |
| Bande rééquilibrage | 5 ; 10 ; 15 % |
| Blackout pré-close | 0 ; 30 ; 60 min |

Il faut ensuite sélectionner les paramètres sur une période et les valider sur une période **non utilisée pour l'optimisation**. Autrement, il est très facile de découvrir une combinaison qui explique merveilleusement le passé et ne fonctionne plus ensuite.

La recherche récente sur le momentum crypto rappelle justement que des résultats apparemment attractifs peuvent fortement se dégrader lorsque l'on introduit des hypothèses de marché plus réalistes. citeturn19view1

### Attention particulière au backtest maker

Le piège classique serait :

```text
si low de la bougie <= mon limit buy
alors ordre rempli
```

Cette hypothèse est beaucoup trop favorable.

Un ordre post-only peut rester derrière d'autres ordres dans la file ; le fait que le marché touche ton prix ne prouve pas que ta quantité a été exécutée. Kraken indique explicitement que les ordres limites peuvent n'être remplis que partiellement. citeturn18view6

L'historique *time-and-sales* peut fournir une approximation plus conservatrice : ne considérer le maker rempli que si des transactions ultérieures se font à ton niveau ou le traversent avec suffisamment de volume. Kraken fournit chaque transaction publique avec prix, volume et sens. citeturn18view9

Cela ne reconstitue pas parfaitement ta place dans la file, mais c'est nettement préférable à un fill automatique au simple contact du prix.

Pour une simulation encore plus fidèle, il faudrait enregistrer prospectivement le carnet L2 et les mises à jour de marché.

### Mon ordre de test final

Je commencerais par une V1.05 minimale :

```text
1. Horloge UTC + bougies réellement clôturées
2. Filtre France
3. Frais dynamiques
4. Correction du rééquilibrage
5. Top 3 entrée / top 5 maintien
6. Maker-first entrée + sortie C
7. Hystérésis BTC
```

Je laisserais dans un premier temps :

```text
5 confirmations actuelles
3 positions à ~33 %
stop 3 ATR
coupe-circuit initial
```

Puis seulement après avoir mesuré cette version, je testerais le sizing ATR et la simplification des indicateurs.

**Mon hypothèse de recherche est que le gain principal viendra moins d'un meilleur point d'entrée que du fait de ne plus vendre puis racheter pour de mauvaises raisons.** C'est cohérent à la fois avec le niveau élevé des coûts Kraken, avec les résultats académiques récents qui rendent le momentum transversal moins convaincant que le momentum temporel, et avec le principe général de zones de non-trading lorsque les transactions ont un coût. citeturn19view0turn19view1turn19view2

En pratique, la philosophie de la V1.05 devrait devenir :

> **Entrer rarement sur une tendance clairement validée, laisser respirer une bonne position, ne pas confondre un changement de classement avec une cassure de tendance, et réserver les ordres coûteux aux situations où la vitesse d'exécution a réellement de la valeur.**

Sur le cas XMR, cette architecture aurait offert plusieurs barrières successives : XMR aurait été retiré de l'univers français ; l'achat de 23:14 UTC aurait été bloqué par la proximité de la clôture ; la nouvelle bougie aurait été explicitement validée avant recalcul ; et un franchissement infinitésimal du BTC autour de son EMA50 n'aurait plus nécessairement déclenché une liquidation générale. C'est ce type de robustesse cumulée que je privilégierais avant toute optimisation supplémentaire des indicateurs.