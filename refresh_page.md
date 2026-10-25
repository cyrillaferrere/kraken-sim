# Rafraîchir le tableau de bord (chaque heure) — Kraken Sim V1.01
Page : Kraken Sim : trading fictif · canvas_id f12cd864-378b-47f3-8d6a-608e3b05e070
URL : https://cursor.com/canvas/store-36b6b63e-c5cb-4fb4-af14-bc57d78c44af/f12cd864-378b-47f3-8d6a-608e3b05e070

1. `cd /workspace/kraken-sim && python3 cycle.py && python3 render_page.py`
   - cycle.py : idempotent par créneau horaire UTC ; enregistre aussi les 5 indicateurs par crypto (table `indicators`).
   - render_page.py : écrit page_contents.txt (Page) ET dashboard.html (HTML autonome, mode sombre, BTCUSD en direct).
1b. V1.04 : si render_page.py affiche `PUBLISH_PENDING`, publier le contenu exact de state/public_state.json dans le dépôt GitHub public cyrillaferrere/kraken-sim-state, fichier state.json, branche main (connecteur user-GitHub-xai, create_or_update_file avec le sha courant du fichier, content "$file:/workspace/kraken-sim/state/public_state.json"). URL lue par le HTML : https://raw.githubusercontent.com/cyrillaferrere/kraken-sim-state/main/state.json. Si un jeton GITHUB_TOKEN/gh est présent, render_page.py publie seul.
2. Lire page_contents.txt en entier et appeler WriteCanvas avec canvas_id=f12cd864-378b-47f3-8d6a-608e3b05e070, contents = texte du fichier tel quel (inline ; $file: ne marche pas). Pas de titre, jamais de nouvelle Page.
3. Montants en USD, heures de Paris, tout en français.
Optionnel : `python3 preview_indicators.py` (aperçu lecture seule des indicateurs, utilisé seulement si la base n'a encore aucune ligne `indicators`).
Leçons : ajouter une section `## Semaine du JJ/MM/AAAA` dans lecons.md (faits réels uniquement) ; la section n'apparaît que si une entrée existe.
