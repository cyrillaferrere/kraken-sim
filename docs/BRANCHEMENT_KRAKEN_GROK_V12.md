# Kraken Sim V1.2 — passerelle marchés réels, sans activation

**25/10/2026 — PR #7 `strategy/v1.2` uniquement.** **Précision utilisateur : Grok Bot possède déjà un connecteur Kraken et gère seul les décisions en utilisant les stratégies V1.2.** Cette livraison ajoute au moteur PAPER un contrôle de valorisation autonome sur les données **publiques** Kraken, et un canal possible de décision via des issues GitHub ; elle ne remplace pas le connecteur Kraken de Grok.

### Ce qui est opérationnel au niveau du code

- `v12_kraken_public.py` télécharge les informations spot/USD, bid/ask, les bougies journalières clôturées (jamais la dernière bougie non terminée), ainsi que la cotation **USDC/USD**. L'API utilisée est exclusivement `AssetPairs`, `Ticker`, `OHLC` ; **aucune clé privée et aucun accès au trading Kraken**. Présélection par volume 24h pour limiter les requêtes puis filtres sur la médiane du volume 30 jours dans la stratégie. Présélection **non exhaustive**, ce n'est pas une preuve de couverture de toutes les cotations/délistages.
- `v12_grok_issues.py` lit en lecture seule les issues ouvertes **`IT V1.2 ...`** avec le label exact `it-decision`, dont l'auteur a l'identifiant numérique GitHub autorisé. Il exige le JSON `{it_id,synthesis_sha256,decisions}`. Le login seul ne constitue pas une preuve d'identité et toute issue conserve son caractère non fiable jusqu'au contrôle du moteur.
- `v12_live_bridge.py` raccorde techniquement collecteur → `PaperEngine.tick()` (protections d'abord) → réception de l'issue Grok → `PaperEngine.admit_batch()`. Si GitHub est indisponible, **les protections moteur sont traitées avant la tentative de réception**, sans nouvelle entrée. Le moteur n'utilise jamais le corps d'une issue comme source d'état de risque.
- `tests/test_v12_real_bridge.py` reproduit l'API Kraken/GitHub avec des réponses injectées : absence de clé, exclusion de la bougie ouverte, authentification de l'auteur, SHA erroné, fail-closed de la passerelle et protection lorsque GitHub ne répond pas.

### Commande de vérification des vrais prix Kraken (lecture seule)

Depuis une copie locale de `strategy/v1.2`, avec Python 3.12 :

```bash
python3 v12_live_bridge.py --check-market --max-pairs 8
```

Cette commande est un **contrôle réseau manuel** : elle interroge Kraken et résume les données disponibles. Elle **ne crée ni portefeuille, ni ordre fictif, ni IT Grok**, et ne modifie pas le site.

### À fournir avant mise en service (pas encore effectué)

1. **ID numérique GitHub du compte qui publiera les IT Grok**. Le nom du compte doit être identifié et fixé explicitement : le commentaire PR de Grok apparaît actuellement sous le compte GitHub humain, ce qui ne permet pas de présumer l'identité d'une issue future.
2. Créer et gérer le canal de décision (par exemple des issues `it-decision`) et la remise d'une synthèse figée à Grok. **Aucune cadence d'une IT par jour n'est imposée : Grok peut effectuer une dizaine d'IT par jour, voire davantage selon son quota et les opportunités.** Chaque IT porte un identifiant et le SHA de la synthèse utilisée. Les cycles de suivi PAPER peuvent être indépendants des IT.
3. Configurer un environnement d'exécution stable pour les cycles PAPER (dossier SQLite hors dépôt, persistant d'un cycle à l'autre, accès minimum aux données). Le module `fetch_and_step()` existe mais n'a **aucun workflow, cron ni CLI actif**. Les données de trading PAPER de l'essai ne sont pas sur le dashboard préprod.
4. Définir un accès GitHub en **lecture seule** pour les issues, les droits du compte Grok et la distribution des synthèses/états, plus vérification réelle de l'API Kraken, des minima d'ordre et des spreads avant activation.
5. Faire une dernière revue et obtenir le **GO de Cyril distinct pour activation** de la V1.2. Le `cycle_v12.py --cycle` d'origine reste volontairement bloqué ; aucun changement de `sim.yml`, main ou V1.1.

**Les tests CI sont hors réseau :** le collecteur a été testé contre des fixtures, pas encore contre la disponibilité effective des vrais marchés. Aucune performance réelle n'a été mesurée. L'UX préprod devra être refondue séparément une fois le nouveau contrat de données stabilisé.
