#!/usr/bin/env python3
"""Préprod en lecture seule : mode actuel V1.1 ou mode V1.2 activé explicitement.
Aucun moteur, cycle ni écriture dans un état. Sortie dans _site seulement."""
import json, os, re, sys, urllib.request
D = os.path.dirname(os.path.abspath(__file__))
PROD_STATE = "https://raw.githubusercontent.com/cyrillaferrere/kraken-sim/main/state/public_state.json"
OUT = os.environ.get("PREPROD_OUT", os.path.join(D, "_site"))
V12_STATE = "https://raw.githubusercontent.com/cyrillaferrere/kraken-sim-preprod/state-v12/public_state_v12.json"
V12_ENABLED = os.environ.get("PREPROD_V12_READY") == "1"
STATE_SOURCE = V12_STATE if V12_ENABLED else PROD_STATE
data = json.loads(urllib.request.urlopen(urllib.request.Request(STATE_SOURCE, headers={"User-Agent": "kraken-sim-preprod"}), timeout=30).read())
if V12_ENABLED:
    if data.get("strategy_id") != "kraken-sim-v1.2" or data.get("environment") != "preprod" or data.get("strategy_version") != "V1.2":
        raise RuntimeError("REFUS : source V1.2 absente ou état étranger, pas de fallback silencieux vers V1.1")
    # Exclure les résultats et leçons V1.1 : seul l'export V1.2 peut les fournir.
    data.setdefault("walkforward", {})
    data.setdefault("backtest", {})
    data.setdefault("lessons", [])
    data["C0_source"] = "Simulation papier V1.2 indépendante (état réel du dernier cycle)"
else:
    # Champs exclus du state public : reconstruits depuis les fichiers statiques du dépôt (backtests, leçons), sans la base de la sim
    J = lambda fn: json.load(open(os.path.join(D, fn)))
    wf = {}
    for tag, fn in (("040", "backtest2_results.json"), ("080", "backtest2_fee080.json")):
        w = J(fn); keep = ("B", "Bfixe", "BTC", "EW")
        wf[tag] = dict(folds=[dict(test=r["test"], res={k: dict(ret=r["res"][k]["ret"], mdd=r["res"][k]["mdd"]) for k in keep}) for r in w["folds"]],
                       agg={k: dict(ret=w["agg"][k]["ret"], mdd=w["agg"][k]["mdd"], pos=w["agg"][k].get("pos_folds")) for k in keep}, period=w["period"], n=w["n_folds"])
    data["walkforward"] = wf
    bt = J("backtest_results.json")
    data["backtest"] = dict(periods=bt["periods"], rows={k: [dict(v=v, **r) for v, r in res.items()] for k, res in bt["results"].items()})
    lp = os.path.join(D, "lecons.md")
    data["lessons"] = [b.strip() for b in open(lp).read().split("\n## ")[1:] if b.strip()] if os.path.exists(lp) else []
    data["C0_source"] = "state public de production (préprod, lecture seule)"

html = open(os.path.join(D, "dashboard_template.html")).read()
assert html.count("__DATA__") == 1, "template : une seule injection attendue"
html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
# Le JS lit uniquement la source explicitement sélectionnée (les prix Kraken restent live)
html, n = re.subn(r'const STATE_URL = [^;\n]*;', f'const STATE_URL = "{STATE_SOURCE}";', html, count=1)
assert n == 1, "STATE_URL introuvable dans le template"
# Bandeau préprod injecté à la publication uniquement (jamais dans le template, donc jamais en prod)
# Marquage préprod discret, sans bandeau occupant toute la largeur.
# Modifié exclusivement dans le rendu préprod : jamais dans le template de production.
BAN = ''
html = html.replace('<strong>Kraken <span>Sim</span></strong>', '<strong><span style="color:#ef4444">Kraken</span> <span>Sim</span> <small style="font-size:12px;color:#a7b7c9;font-weight:650">PreProd</small></strong>', 1)
html, n = re.subn(r'(<body[^>]*>)', r'\1' + BAN, html, count=1)
assert n == 1, "<body> introuvable"
html = html.replace("<title>", "<title>[PRÉPROD] ", 1)
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "index.html"), "w").write(html)
open(os.path.join(OUT, ".nojekyll"), "w").write("")
print("préprod rendue :", os.path.join(OUT, "index.html"), "| source :", "V1.2" if V12_ENABLED else "V1.1", "| cycle du", data.get("as_of"))
