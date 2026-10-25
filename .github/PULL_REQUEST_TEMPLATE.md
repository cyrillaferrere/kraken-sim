## Quoi / pourquoi
<!-- 2-3 lignes -->

## Type
- [ ] UX/UI (branche `ux/*`, uniquement `dashboard_template.html`, `CHANGELOG.md`, `docs/SPEC_UX.md`)
- [ ] Fonctionnel (moteur, données, règles — Kraken Bot)

## Vérifications
- [ ] `python3 tests/check_template.py` passe en local (ou le check « garde-fous » est vert)
- [ ] Entrée ajoutée en tête de `CHANGELOG.md` (date, auteur, sections)
- [ ] Aucun id / clé de `D` supprimé (sinon : issue `fonctionnel` + mise à jour de `tests/contract.json` par Kraken Bot)
- [ ] Aucune donnée d'exemple en dur ; ce qui est figé (sur clôture / cycle) est étiqueté comme tel
- [ ] Aucune logique de trading modifiée
- [ ] `VERSION_UX` (UX) ou `VERSION_ENGINE` (moteur) incrémentée, entrée `## [UX|Moteur Vx.y]` en tête du CHANGELOG
- [ ] Stratégie : jamais par GPT6 ; sinon `STRATEGY_VERSION` incrémentée + entrée avec backtest
