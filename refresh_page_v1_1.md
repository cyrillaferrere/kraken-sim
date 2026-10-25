# Rafraîchir le tableau de bord — Kraken Sim V1.1 (NE PAS ACTIVER avant validation de Cyril)
Page : Kraken Sim : trading fictif · canvas_id f12cd864-378b-47f3-8d6a-608e3b05e070

Planning proposé (UTC) : `10 * * * *` (toutes les heures à hh:10).
- Le cycle de 00:10 UTC = décision journalière (bougies clôturées vérifiées, instantané figé, nouveaux ordres post-only).
- Les autres heures = intraday : stops suiveurs et exécution/repositionnement des ordres en attente uniquement ; aucun achat dans les 60 min avant 00:00 UTC.
- Rattrapage : si le cycle de 00:10 est manqué, le premier cycle suivant avant 23:00 UTC prend la décision du jour.

1. `cd /workspace/kraken-sim && python3 cycle_v11.py && python3 render_page.py`
   - cycle_v11.py : simulation papier uniquement (API publique Kraken), idempotent par créneau horaire UTC.
2. Si render_page.py affiche `PUBLISH_PENDING` : publier state/public_state.json vers cyrillaferrere/kraken-sim-state, fichier state.json, branche main (connecteur user-GitHub-xai, create_or_update_file avec le sha courant, content "$file:/workspace/kraken-sim/state/public_state.json").
3. Lire page_contents.txt en entier et appeler WriteCanvas (canvas_id ci-dessus, contenu tel quel, jamais de nouvelle Page).
4. Montants en USD, heures de Paris, tout en français, BTC/DOGE (jamais XBT/XDG).
Retour arrière : `cp cycle_v1_04_backup.py cycle.py` n'est pas nécessaire (cycle.py inchangé) ; remettre dashboard_template_v1_04.html, page_data_v1_04_backup.py, refresh_page_v1_04.md.

## V1.1 + socle (25/10/2026)
- Cron : `10 * * * *` UTC ; le cycle de 00:10 UTC prend la décision journalière.
- Lancer `bash /workspace/kraken-sim/run_cycle_v11.sh`.
- Si la sortie contient PUBLISH_PENDING : GitHub `create_or_update_file` sur cyrillaferrere/kraken-sim-state, `state.json`, branche main, avec le sha courant (get_file_contents) et content `$file:/workspace/kraken-sim/state/public_state.json`.
- Puis WriteCanvas canvas_id f12cd864-378b-47f3-8d6a-608e3b05e070 avec le contenu intégral de page_contents.txt (même Page/URL).
- Socle de départ (500 BTC / 300 ETH / 200 XRP) acheté une seule fois (meta core_done) le 25/10 11h33 Paris.
## Correction 25/10 12h : socle de départ vendable
- Le socle est migré en positions normales (table positions, meta core_migrated ; script migrate_socle_libre.py, idempotent). Un seul portefeuille de 6 605,10 $ : coupe-circuit −30 % sur le total, cible 33 % du total, socle inclus dans l'univers/rotation.
- Stop suiveur 3×ATR et sortie risk-off s'appliquent tout de suite ; sortie de tendance (clôture < EMA50) et rotation seulement après 48 h depuis l'achat initial (27/10 11h33 Paris).
- Une position < ½ cible n'occupe pas d'emplacement ; en régime haussier, si elle passe le filtre d'entrée, elle est renforcée jusqu'à 33 %.
- Table core conservée = référence « socle conservé sans toucher » (core.bench sur la Page).
- Retour arrière : *_pre_socle_libre_backup.* et sim_pre_socle_libre_backup.db.
