# Kraken Sim V1.2 — Corrections Grok P1-A à P1-F et essai synthétique 30 jours

**25 octobre 2026 — PR #7 en brouillon uniquement. Aucun démarrage du bot V1.2, aucune fusion, aucun cron ni ordre réel.** Cette étape corrige la revue de Grok (commentaire #6401578854) sur la partie **moteur PAPER hors ligne**, pas encore sur l'intégration des IT automatiques.

## 1. Six corrections demandées par Grok Bot

| Priorité | Correction livrée | Fichiers et vérification |
|---|---|---|
| P1-A | **Décision ≠ exécution** : admission sur la synthèse de l'IT (quotes de synthèse pouvant dater de plusieurs heures au moment de la remise de la décision), expiration autorisée jusqu'à **26 h** pour A/C/D et **7 jours** pour B ; au cycle d'exécution, contrôle séparé des **quotes ≤ 5 minutes**, du risque, des signaux et du cash. Une proposition expirée ne crée pas de fill. | `v12_autonomy.py`, `v12_paper_engine.py`, tests de délai et d'expiration |
| P1-B | **Exécution PAPER persistante** : SQLite séparé du site et de V1.1, décisions idempotentes par `decision_id`, ordre maker initial, trades post-placement, fill partiel et fallback taker au cycle suivant. Reprise avec état en base, sorties A/B/C/D déterministes sans Grok, liquidation kill-switch. | `v12_paper_engine.py`, `v12_execution.py`, tests bout en bout |
| P1-C | **Kill-switch contrôlé par le moteur** : pic de capital, arrêt, cooldown, modèle et politique autorisés sont persistés dans la base du moteur et ne sont **jamais lus depuis la synthèse ou la décision Grok**. Les ordres en attente réservent cash/quantités, contrôle renouvelé à l'exécution. | `v12_paper_engine.py`, `v12_autonomy.py`, tests d'injection d'état et de plafonds |
| P1-D | **Conserver 100 % USDC** : benchmark d'unités USDC conservées, valorisé au bid USDC/USD observé sur Kraken ; aucune parité fictive 1 USDC = 1 USD. Base PAPER théorique distincte de la quantité réellement détenue par Cyril. Les marks sont enregistrés chaque cycle. | `v12_usdc_baseline.py`, `v12_paper_engine.py`, tests de spread, de taux et de benchmark figé |
| P1-E | **Outcomes calculés par le moteur** : au terme des horizons 1/7/30 jours, calcul dans le moteur sur marks conservés : variation nette du portefeuille, benchmark USDC, BTC, frais et excursions défavorables (MAE). Enregistrements de preuve idempotents ; Grok ne transmet que des décisions, jamais ses propres outcomes. | `v12_paper_engine.py`, `v12_learning.py`, tests d'horizons et chaîne d'empreintes |
| P1-F | **Plafond C** : max d'exposition = **min(90 % global, limite du candidat)**, sans dérogation implicite à 100 % ; un test construit explicitement deux positions C qui franchiraient le plafond tout en respectant les limites individuelles. | `v12_autonomy.py`, `tests/test_v12_autonomy.py` |

**Important :** la limite de 7 jours en B sert à accepter une décision tardive, et non à garantir qu'un signal hebdomadaire reste économiquement pertinent pendant une semaine. La future connexion au vrai flux Kraken doit confirmer la règle de rafraîchissement du signal avant tout ordre. Les frais F2 et les slippages sont des hypothèses de simulation, pas des fills authentifiés de Kraken.

## 2. Essai PAPER synthétique sur 30 jours (accéléré, hors ligne)

La commande manuelle est :

```bash
python3 cycle_v12.py --dry-run --out /tmp/kraken-v12-paper-dryrun
```

Sur Windows (PowerShell) :

```powershell
py -3 cycle_v12.py --dry-run --out "D:\Kraken-V12-Dryrun"
```

Conditions : Python 3.12, dossier de sortie externe **ne contenant aucun état précédent** de ce test. Le programme refuse de réutiliser un dossier déjà doté de `paper_engine_v12.db`.

`--dry-run` n'a **aucun accès réseau**, aucune clé Kraken, aucun appel Grok, aucun workflow ou cron. `--cycle` reste **bloqué avec code de retour 3**.

Le scénario déroule **30 jours calendaires fictifs** en quelques secondes, avec :

- Historique synthétique de 325 bougies initiales, puis progression et choc de prix configuré (données non représentatives des marchés).
- Deux propositions Grok de test suivant **C — BTC/ETH tendance**.
- Premier cycle : limites maker placées sans fill garanti ; cycle suivant : **fallback taker**, frais F2 comptabilisés.
- Nouvelle réception des mêmes `decision_id` : **aucun doublon**.
- Trois IT Grok manquées : **aucune entrée autonome ajoutée**.
- Une décision volontairement à TTL court : **expirée sans ordre**.
- Effondrement fictif du BTC/ETH : **kill-switch -25 % sur pic moteur**, annulation des ordres en attente et ventes PAPER obligatoires.
- Suivi du taux USDC/USD fictif, sans le forcer à 1, et des revenus fictifs de BTC passif.
- Journaux de décision et outcomes J+1/J+7/J+30 produits par le **moteur**, avec preuve des timestamps et hash chain.
- Redémarrage/doublon de créneau refusé par idempotence du cycle.

Le test en CI vérifie notamment **2 décisions remplies, 1 ordre expiré, 1 kill-switch, 3 IT manquées, 33 marques comptables** et l'absence de positions après liquidation. Les résultats de ce test ne sont **ni une preuve de rendement, ni une observation de 30 jours de marché réel**.

Les fichiers `synthesis.json`, `decision_fixture.json`, `paper_engine_v12.db`, `grok_paper_evidence_v12.db` et `dry_run_30d.json` sont créés **uniquement dans le dossier externe choisi**.

## 3. Contrôles CI

- `tests/test_v12_paper_engine_30d.py` : simulation accélérée 30 jours, état moteur non pilotable par snapshot, prix expirés, comparaison USDC, sortie de tendance C sans intervention Grok.
- `tests/test_v12_cli_dry_run.py` : exécution réelle de la commande en sous-processus, résultats de synthèse, dossier isolé, absence de réutilisation silencieuse et `--cycle` interdit.
- `tests/test_v12_autonomy.py` : admission IT vs exécution, quota de cash réservé, kill moteur, version de politique et plafond C à 90 %.

CI vérifiée le 25/10/2026 : **121 tests V1.2 + 2 tests statiques V1.1** à ce jalon, plus contrat, versions, périmètre stratégie et préprod isolée.

## 4. Ce qui N'EST PAS encore validé

1. Le collecteur réseau Kraken **public** avec données horodatées, volumes, spread, positions et flux trades n'est pas branché au moteur autonome.
2. L'identité de l'émetteur Grok et le canal GitHub Issue `it-decision` ne sont pas authentifiés ni automatisés ; les décisions du test sont **fabriquées dans le code**, non émises par Grok.
3. La synthèse automatique quotidienne à environ **02h30 Europe/Paris**, la routine Grok et les IT extraordinaires plafonnées ne sont **ni configurées ni actives**.
4. Les sorties A/B/C/D sont implémentées de façon **déterministe à la clôture des bougies**, mais n'ont pas été auditées sur une session vivante avec carnet réel, gaps, pannes et retards d'API. Les limites de stops ne sont pas des garanties de prix de sortie.
5. Les outcomes mesurent ici la **performance du portefeuille autour d'une décision**, pas la causalité ni la qualité prédictive de cette décision isolée. Une évaluation pertinente de Grok exigera une période prospective et une méthode de comparaison préenregistrée.
6. Le benchmark USDC est initialisé à une quantité **théorique**, pas aux USDC détenus réellement. Son suivi en USD dépend entièrement des quotes authentifiées.
7. L'UX du dashboard PREPROD devra être revue pour les IT, l'apprentissage, les risques et les comparaisons USDC. Aucune refonte ni publication effectuée.

**Prochaine phase proposée à Cyril, sans l'entreprendre ici :** audit de Grok sur les six corrections, puis connexion authentifiée `Grok ↔ GitHub Issue ↔ collecte Kraken ↔ moteur PAPER`, et validation séparée par Cyril avant toute IT et tout cycle autonome. **Aucun passage LIVE n'est envisagé à cette étape.**
