# Kraken Sim — isolation de la stratégie V1.2

Statut : infrastructure EN PR, NON DÉPLOYÉE. Aucun cycle V1.2 autorisé ni exécuté.

- Branche de code : strategy/v1.2, créée depuis develop.
- Etat V1.2 : branche state-v12 du dépôt public kraken-sim-preprod. Aucun secret, aucun état fictif inventé.
- Base à terme : sim_v12.db, accessible UNIQUEMENT via V12_STATE_DIR absolu hors du dépôt kraken-sim. Le pré-vol ne crée pas de base.
- Export cible : public_state_v12.json, format à finaliser après SPEC ; sa source est marquée preprod/V1.2.
- Versions indépendantes : `VERSION_ENGINE` reste **V1.2** (moteur partagé existant sur develop) ; `VERSION_ENGINE_V12` = **V1.3** exclusivement pour le moteur de la stratégie **V1.2** ; UX à part. Les ordres V1.1 ne sont pas ré-étiquetés.
- Contrôles : pas d'écriture vers kraken-sim, cycle_v11.py, sim.yml, sim.db, state/ ou strategy/params.json.
- Le site préprod existant conserve temporairement l'affichage V1.1 jusqu'à la présence d'un export réel V1.2 et l'accord de bascule ; NE JAMAIS appeler ce site une simulation V1.2 avant ce jalon.
- Workflow manuel V1.2 : fichier préparé sur la PR seulement. GitHub exige sa présence sur main pour workflow_dispatch : intégration après décision explicite de Cyril, pin SHA contrôlé et autorisation distincte pour lancer un cycle. Cron interdit pour l'instant.
- Aucune logique d'achat/vente ni résultat économique n'est implémenté : attendre docs/SPEC_STRATEGIE_V1_2.md publié par Grok Bot, critères de rejet pré-définis.
- Premier merge sur develop : Cyril décide après guard vert et revue technique Grok Bot. Tout passage sur main et tout cycle exigent validation distincte.

### Contrôles renforcés après revue de Grok Bot
- P0 : interdiction expresse de tous les fichiers `state/**` ainsi que `VERSION_ENGINE` dans la PR `strategy/v1.2`, couverte par des tests négatifs.
- P1 : chemins d'état interdits dès qu'un ancêtre contient un clone du moteur V1.1 ou `sim.db`, avec tests hors ligne.
- Restent ouverts avant tout backtest officiel : biais de survivance, délistages, validation chronologique complète, frais réels, schéma du dashboard et équivalence V1.1.
