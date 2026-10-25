#!/usr/bin/env python3
"""Vérifie la migration GitHub de kraken-sim (dépôt, workflow, cron, derniers runs, Pages, fraîcheur de l'état)."""
import json, subprocess, urllib.request, datetime
R = "cyrillaferrere/kraken-sim"
def gh(*a): return subprocess.run(["gh", *a], capture_output=True, text=True).stdout
print("Dépôt :", json.loads(gh("repo", "view", R, "--json", "url,visibility") or "{}"))
wf = gh("api", f"repos/{R}/contents/.github/workflows/sim.yml", "-H", "Accept: application/vnd.github.raw")
print("Cron actif :", any(l.strip().startswith("schedule:") for l in wf.splitlines()))
print("Derniers runs :"); print(gh("run", "list", "-R", R, "-L", "5"))
pg = json.loads(gh("api", f"repos/{R}/pages") or "{}"); print("Pages :", pg.get("html_url"), pg.get("status"))
try:
    s = json.loads(urllib.request.urlopen(f"https://raw.githubusercontent.com/{R}/main/state/public_state.json", timeout=20).read())
    print("État publié : as_of", s.get("as_of"), "| total", s.get("total"), "| cycles", s.get("n_cycles"))
except Exception as e: print("État illisible :", e)
