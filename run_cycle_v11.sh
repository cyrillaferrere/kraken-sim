#!/usr/bin/env bash
# Kraken Sim V1.1 + socle : cycle papier (aucun ordre réel) + rendu Page/dashboard.
# Ne touche jamais /workspace/kraken-jeu. Publication : publie seul si un jeton GitHub existe, sinon affiche PUBLISH_PENDING.
set -euo pipefail
cd /workspace/kraken-sim
python3 cycle_v11.py
python3 render_page.py
echo "PAGE_CONTENTS=/workspace/kraken-sim/page_contents.txt"
