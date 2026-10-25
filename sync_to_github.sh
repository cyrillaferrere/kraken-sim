#!/usr/bin/env bash
# À lancer UNE fois au basculement (après arrêt du moteur local) : pousse l'état local courant vers le dépôt.
set -euo pipefail
cd /workspace/kraken-sim-gh && git pull -q
cp /workspace/kraken-sim/sim.db sim.db
git add sim.db && (git diff --cached --quiet || git commit -qm "sync état local avant bascule") && git push -q && echo SYNC_OK
