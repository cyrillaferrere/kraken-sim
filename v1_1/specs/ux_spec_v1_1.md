# KRAKEN SIM — Cahier des charges UX/UI V1.1

**Projet :** Kraken — Bot Crypto  
**Version :** 1.1 — Refonte complète de l'interface  
**Destinataire :** Grok Bot  
**Périmètre :** UX, UI, ergonomie, visualisation des données  
**Responsabilité technique :** Grok Bot  
**Langue :** français  
**Thème :** sombre, desktop-first, responsive mobile

---

## 1. Objectif de la refonte

Transformer Kraken Sim en un véritable **terminal de surveillance et d'analyse d'un portefeuille crypto simulé**.

L'interface actuelle présente plusieurs défauts :

- Trop de cartes et de tuiles, donnant un aspect générique.
- Typographie devenue trop petite à force de compacter l'interface.
- Absence de hiérarchie claire entre solde, performance, marché et activité.
- Graphiques hétérogènes en dimensions et en présentation.
- Journal des ordres peu lisible et insuffisamment structuré.
- Informations essentielles dispersées sur une page excessivement longue.
- Trop d'informations techniques affichées en permanence.

La V1.1 doit privilégier trois usages :

1. **Surveiller :** connaître instantanément la valeur du compte et son évolution.
2. **Comprendre :** identifier les positions, les décisions du bot et leurs conséquences.
3. **Analyser :** examiner les performances, indicateurs, stratégies et risques.

**Principe directeur : moins de conteneurs, davantage de hiérarchie et de lisibilité.**

## 2. Répartition des responsabilités

### UX/UI — Présent cahier des charges

Définition de :

- L'architecture des pages.
- La hiérarchie visuelle.
- La navigation.
- Les composants d'interface.
- La typographie, les couleurs et les espacements.
- La présentation des tableaux et graphiques.
- Les interactions utilisateur.
- Les états vides, de chargement et d'erreur.
- L'adaptation mobile.

### Fonctionnel — Grok Bot

Grok Bot reste responsable :

- De l'intégration des données.
- Du fonctionnement des graphiques.
- Du calcul des performances et des périodes.
- Des connexions Kraken et GitHub.
- De la conservation des règles de trading.
- Du rafraîchissement des données.
- De la gestion de l'historique.
- De la compatibilité avec la génération automatique du HTML.

**La refonte UX ne doit modifier ni les règles de trading ni les résultats financiers.**

Les données fictives utilisées dans des maquettes ne doivent jamais être présentées comme des valeurs réelles du simulateur.

---

## 3. Architecture générale

### 3.1 Navigation latérale

Conserver un menu latéral rétractable, mais réduire son importance visuelle.

**Mode réduit :**
- Largeur cible : 56 à 64 px.
- Icônes seules, avec infobulles au survol.
- Élément actif clairement identifiable.
- Ouverture par clic.

**Mode déployé :**
- Largeur cible : 190 à 210 px.
- Icônes et libellés.
- Possibilité de le refermer.
- État conservé pendant la navigation si techniquement possible.

### 3.2 Rubriques

**Vue d'ensemble**
- Synthèse financière.
- Évolution du portefeuille.
- Marché BTC.
- Positions et dernières opérations.

**Portefeuille**
- Positions ouvertes.
- Allocation.
- Conditions de vente.
- P&L par actif.

**Marché**
- BTC en direct.
- Indicateurs techniques.
- Scores des cryptomonnaies.

**Activité**
- Journal des ordres.
- Décisions du bot.
- Historique des opérations.

**Analyse**
- Performances comparées.
- Drawdown.
- Statistiques de trading.
- Stratégies et backtests.
- Walk-forward.

**Règles**
- Paramètres et règles de simulation.
- Informations techniques et sources.

La vue d'ensemble ne doit plus contenir l'intégralité des sections des autres rubriques.

---

## 4. Header financier — Élément prioritaire

Le haut de l'interface doit être consacré au compte.

### 4.1 Informations principales

Afficher dans cet ordre :

**Solde total du portefeuille**
- Montant en USD.
- Police de 36 à 44 px sur desktop.
- Police de 28 à 34 px sur mobile.
- Valeur actualisée selon les données disponibles.

**Gains / pertes sur la période sélectionnée**
- Montant en dollars.
- Variation en pourcentage.
- Vert pour une variation positive.
- Rouge pour une variation négative.
- Couleur neutre pour une variation nulle ou indisponible.

### 4.2 Sélecteur de période

Créer un sélecteur horizontal comportant exactement :

**1j | 7j | 1 mois | 6 mois | 1 an | Tout**

Ce sélecteur contrôle :

- Le graphique principal d'évolution du portefeuille.
- Le gain ou la perte affiché dans le header.
- Le pourcentage de performance.
- Les éventuelles comparaisons associées à cette période.

Le changement de période doit être immédiat, sans rechargement complet de la page.

L'option sélectionnée doit être visuellement identifiable, sans bouton disproportionné.

### 4.3 Disponibilité des données

Si l'historique est insuffisant pour une période :

- Ne jamais inventer de rendement.
- Afficher « Historique insuffisant » ou « Données indisponibles ».
- Permettre de consulter les données réellement disponibles.
- Signaler clairement une période partielle.
- Ne pas présenter une performance depuis le lancement comme une performance sur un an.

Grok Bot devra définir la méthode de calcul et la profondeur d'historique réellement disponibles.

### 4.4 Informations secondaires

Sous le solde, afficher une ligne de synthèse :

- Liquidités.
- Exposition.
- Drawdown.
- Frais cumulés.
- Nombre de transactions.

Ces informations doivent être présentées **en ligne**, avec de simples séparateurs, sans cinq cartes distinctes.

---

## 5. Barre de statut du bot

Supprimer le grand panneau « Centre de contrôle ».

Le remplacer par une barre discrète, placée dans l'en-tête ou immédiatement en dessous.

Informations :

- État de la simulation.
- Temps depuis le dernier cycle.
- Heure estimée du prochain cycle.
- Fraîcheur des données.
- Version du bot.
- Provenance de l'état : direct ou instantané.

### Présentation

Exemple :

**Simulation active · Dernier cycle : 1h 09min · Prochain : ~11h05 · État direct · V1.1**

Le compteur ne doit pas être une grande tuile.

- Police cible : 14 à 16 px.
- Pas de secondes visibles par défaut.
- Couleurs sobres.
- Mise en évidence uniquement en cas d'anomalie.

Les états « simulation active », « données actualisées » et « connexion au marché » doivent rester distincts.

Une donnée obsolète doit être signalée même si le bot est toujours considéré comme actif.

---

## 6. Graphique principal — Valeur du portefeuille

Le graphique central de la V1.1 doit représenter **l'évolution de la valeur totale du portefeuille**, et non le BTC.

### Présentation

- Grande largeur.
- Hauteur desktop cible : 260 à 320 px.
- Hauteur mobile : 200 à 240 px.
- Courbe claire et fine.
- Grille horizontale discrète.
- Axe des montants en USD.
- Axe temporel adapté à la période sélectionnée.
- Infobulle au survol ou au toucher.

### Interactions

Au survol d'un point :

- Date et heure.
- Valeur du portefeuille.
- Variation par rapport au début de la période, si calculable.

Prévoir éventuellement une zone colorée très subtile sous la courbe.

Éviter les dégradés agressifs et les effets lumineux inutiles.

Le graphique doit utiliser les données de performance réellement disponibles, sans interpolation trompeuse des périodes manquantes.

---

## 7. Graphiques secondaires

Tous les graphiques doivent appartenir à une même famille visuelle.

### 7.1 Marché BTC

Afficher :

- Prix BTC/USD en direct.
- Variation journalière.
- Graphique historique.
- Sélecteur de période propre au BTC.

Le graphique BTC doit être secondaire par rapport à la valeur du portefeuille.

### 7.2 Performance comparée

Comparer :

- Kraken Sim.
- BTC conservé.
- Panier BTC/ETH.
- Liquidités.

Les séries doivent utiliser une base de comparaison cohérente et explicitée.

### 7.3 Drawdown

Afficher :

- Drawdown historique.
- Drawdown actuel.
- Drawdown maximum.
- Seuil du coupe-circuit.

Le seuil de risque doit apparaître sous forme de ligne de référence clairement identifiée.

### 7.4 Allocation

Remplacer le tableau d'allocation principal par :

- Une barre horizontale empilée, de préférence.
- Ou un donut compact.

Afficher la répartition entre liquidités et actifs.

Conserver les montants et pourcentages sous forme de légende.

### 7.5 P&L par actif

Créer un histogramme horizontal :

- Une barre par cryptomonnaie.
- Gains positifs vers la droite.
- Pertes négatives vers la gauche.
- Montants affichés en dollars.

### 7.6 Graphiques complémentaires

À prévoir si les données existent :

- Gains/pertes par jour ou par cycle.
- Évolution de l'exposition du portefeuille.
- Scores des cryptomonnaies surveillées.

Ne pas générer de graphique sans données fiables.

---

## 8. Système graphique commun

### 8.1 Couleurs

Palette indicative :

- Fond principal : `#080E19`
- Surfaces secondaires : `#101B2B`
- Bordures discrètes : `#26374A`
- Texte principal : `#EDF5FF`
- Texte secondaire : `#A8B8CB`
- Bleu d'accent : `#5EACFF`
- BTC : `#FFAD46`
- Gains : `#35D6A0`
- Pertes : `#FF667B`
- Comparaison secondaire : `#C6A5FF`

### 8.2 Règles communes

- Même typographie.
- Même style d'axes.
- Même niveau de contraste.
- Même traitement des infobulles.
- Même épaisseur de courbe pour les séries comparables.
- Légendes cohérentes.
- Unités toujours explicites.
- Couleurs constantes d'un graphique à l'autre.

Les axes doivent rester lisibles sans occuper une place excessive.

Les graphiques ne doivent pas changer artificiellement d'échelle pour amplifier les variations.

---

## 9. Portefeuille et conditions de vente

### 9.1 Positions ouvertes

Afficher un tableau structuré :

- Actif.
- Quantité.
- Prix moyen d'achat.
- Prix actuel.
- Valeur actuelle.
- P&L en dollars.
- P&L en pourcentage.

Le P&L doit être immédiatement visible.

Cliquer sur une position doit permettre d'afficher ses informations détaillées.

### 9.2 Conditions de vente

Pour chaque position :

- Distance au stop suiveur.
- Situation par rapport à l'EMA50.
- Régime BTC.
- Délai minimal de détention de 24 heures.
- Décision actuelle ou attendue.

Ne pas afficher une accumulation de « oui » et « non » sans contexte.

Utiliser des libellés explicites :

- Stop non atteint.
- Sous EMA50.
- Régime baissier.
- Détention minimale en cours.
- Conserver.
- Sortie différée.
- Vente déclenchée.

La décision doit être visuellement prioritaire.

**État vide :** afficher « Aucune position ouverte » dans une zone sobre, sans grand tableau vide.

---

## 10. Journal des ordres — Refonte complète

Le journal doit devenir une véritable interface de suivi des opérations.

### 10.1 Présentation principale

Afficher les opérations sous forme de lignes structurées :

| Date | Type | Actif | Montant | Résultat |
|---|---|---|---|---|
| 25/10 02:14 | Vente | XMR | 613,10 $ | −23,81 $ |
| 25/10 01:14 | Achat | XMR | 2 178,84 $ | — |
| 24/10 22:10 | Achat test | BTC | 330,25 $ | — |

*Ces valeurs sont des exemples issus des captures de la version précédente, et non des données actualisées.*

### 10.2 Détail d'une opération

Au clic sur une ligne, déployer :

- Quantité exécutée.
- Prix d'exécution.
- Frais.
- Motif de l'ordre.
- Conditions de marché associées, si disponibles.
- Résultat réalisé, si applicable.

### 10.3 Filtres

Prévoir :

- Tous les ordres.
- Achats.
- Ventes.
- Actif.
- Période.

Les filtres doivent rester compacts.

### 10.4 Lisibilité

- Une opération par ligne.
- Pas de phrases longues dans la vue principale.
- Montants alignés à droite.
- Dates au format français.
- Couleurs réservées aux opérations et résultats.
- Pas de valeur `undefined`, `NaN` ou de champ technique brut affiché.

Le journal doit exploiter des données structurées lorsqu'elles existent. Si seules des phrases sont disponibles, Grok Bot devra déterminer une méthode fiable de présentation sans inventer de champs.

---

## 11. Indicateurs de marché

Conserver le tableau technique, mais améliorer son exploitation.

### Présentation

- Première colonne « Crypto » fixe si nécessaire.
- Lignes lisibles.
- Alignement des valeurs numériques.
- Score sur 5 particulièrement visible.
- Tri par score décroissant par défaut.
- Distinction claire entre indicateur favorable et défavorable.

### Fonctions UX

- Trier les colonnes.
- Filtrer par actif.
- Afficher uniquement les meilleurs scores.
- Accéder au détail d'un indicateur.

Ne pas réduire la police pour faire tenir toutes les colonnes.

Sur mobile, privilégier une présentation par actif plutôt qu'un tableau microscopique.

---

## 12. Décisions du bot

Séparer clairement les **ordres exécutés** des **décisions sans transaction**.

Le journal des décisions doit présenter :

- Heure.
- Actif concerné.
- Action ou absence d'action.
- Motif synthétique.
- Détail dépliable.

Les décisions répétitives de type « aucun signal » doivent pouvoir être regroupées par cycle.

Objectif : éviter plusieurs dizaines de lignes quasiment identiques.

---

## 13. Analyse et backtests

Les sections techniques doivent être accessibles depuis la rubrique « Analyse », sans encombrer la vue principale.

Conserver :

- Performances comparées.
- Statistiques des trades.
- P&L par actif.
- Drawdown.
- Stratégies.
- Backtests.
- Walk-forward.
- Leçons de la semaine.

Les tableaux complexes doivent proposer une lecture synthétique avant les données détaillées.

Les avertissements sur les limites méthodologiques des backtests doivent rester visibles.

Ne jamais masquer un résultat défavorable au profit d'une présentation plus flatteuse.

---

## 14. Typographie et densité

La V1.06 était trop compacte au détriment de la lecture.

Tailles recommandées :

| Élément | Desktop |
|---|---|
| Solde principal | 36–44 px |
| Gain/perte principal | 20–24 px |
| Titres de section | 16–18 px |
| Texte courant | 14 px |
| Valeurs des tableaux | 13–14 px |
| Libellés secondaires | 12–13 px |
| Statut du bot | 13–14 px |
| Compteur horaire | 14–16 px |

Éviter les textes de 9 à 10 px, sauf éléments décoratifs non essentiels.

### Espacements

- Espacement entre grandes sections : 24 à 32 px.
- Espacement interne : 12 à 20 px.
- Hauteur des lignes de tableau : 36 à 44 px.
- Rayon des conteneurs : 8 à 12 px.

La densité doit provenir de la suppression des éléments inutiles, et non de la réduction excessive des caractères.

---

## 15. Responsive mobile

Sur mobile :

- Navigation latérale remplacée par un menu ouvrable.
- Solde et performance immédiatement visibles.
- Sélecteur de période accessible horizontalement.
- Graphiques adaptés à la largeur.
- Tableaux complexes transformés en listes ou cartes par actif.
- Aucune information essentielle tronquée.
- Zones tactiles suffisamment grandes.
- Pas de défilement horizontal global de la page.

Les détails techniques peuvent être repliés.

---

## 16. États d'interface

Prévoir systématiquement :

**Chargement**
- Indicateur discret.
- Conservation des dimensions pour éviter les sauts de mise en page.

**Données indisponibles**
- Message compréhensible.
- Dernière actualisation connue si disponible.

**Historique insuffisant**
- Période clairement signalée.
- Aucun rendement extrapolé.

**Aucune position**
- État vide propre.

**Aucun ordre**
- Message neutre.

**Connexion perdue**
- Distinction entre valeur historique et valeur en direct.

**Cycle en retard**
- Avertissement progressif.
- Aucun changement artificiel des données financières.

**Mise à jour d'une valeur**
- Transition légère.
- Pas de clignotement agressif.
- Respect des préférences de réduction des animations.

---

## 17. Contraintes de compatibilité

Grok Bot doit préserver le fonctionnement de Kraken Sim.

Les contraintes historiques à prendre en compte comprennent notamment :

- Génération automatique du fichier HTML.
- Injection des données du cycle.
- Simulation spot sans ordre réel.
- Connexions aux API publiques Kraken.
- WebSocket Kraken v2.
- Récupération de l'état publié sur GitHub.
- Revalorisation des positions.
- Actualisation des indicateurs.
- Calcul des conditions de sortie.
- Graphiques historiques.
- Stratégies et backtests.

Les scripts, identifiants DOM et conventions d'injection doivent être vérifiés par Grok Bot sur sa version technique actuelle.

**La V1.1 est une refonte de l'interface, pas une nouvelle stratégie de trading.**

---

## 18. Critères de validation UX

La refonte sera considérée comme satisfaisante lorsque :

1. Le solde et la performance sont immédiatement visibles.
2. Les six périodes demandées sont accessibles.
3. Les performances affichées correspondent aux données disponibles.
4. Le graphique principal représente le portefeuille.
5. Le BTC dispose d'un graphique secondaire cohérent.
6. Les graphiques partagent un langage visuel commun.
7. La page principale n'est plus constituée d'une mosaïque de tuiles.
8. Le texte courant est lisible sans zoom navigateur.
9. Le statut du bot occupe une seule zone compacte.
10. Les positions et les dernières opérations sont rapidement accessibles.
11. Le journal des ordres est structuré et compréhensible.
12. Les décisions sont distinctes des transactions.
13. Les analyses avancées ne surchargent pas la vue principale.
14. La navigation fonctionne sur ordinateur et mobile.
15. Les données manquantes sont explicitement signalées.
16. Aucun calcul ou comportement de trading n'est modifié par la refonte.

### Tests demandés à Grok Bot

Vérifier au minimum :

- Desktop 1920 × 1080.
- Desktop 1440 × 900.
- Tablette 768 px.
- Mobile 390 px.
- Menu ouvert et fermé.
- Portefeuille vide et portefeuille avec plusieurs positions.
- Historique court et historique long.
- Données en direct et données indisponibles.
- Journal avec de nombreuses opérations.
- Changement de période.
- Mise à jour des données sans rechargement complet.

---

## 19. Livrable attendu de Grok Bot

Produire **Kraken Sim V1.1**, une interface entièrement fonctionnelle respectant ce cahier des charges.

Livrables :

- Dashboard HTML complet.
- Navigation opérationnelle.
- Graphiques interactifs.
- Sélecteur de périodes fonctionnel.
- Journal des ordres restructuré.
- Interface responsive.
- Compatibilité avec les données et la logique existantes.
- Vérification des interactions et absence d'erreurs JavaScript bloquantes.

Ne pas introduire de fausses données pour compléter les graphiques ou les performances.

**Objectif final : une interface de trading fictif élégante, professionnelle, lisible et efficace, privilégiant la compréhension immédiate de la situation financière plutôt que l'accumulation de widgets.**
