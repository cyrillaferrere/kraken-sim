#!/usr/bin/env python3
"""PRÉPROD : rendu du dashboard depuis le state.json PUBLIC de prod (lecture seule).
Aucun accès à la base de la sim, aucune écriture dans le dossier d'état, aucun cycle. Sortie : _site/index.html (hors dépôt de prod)."""
import json, os, re, sys, urllib.request
D = os.path.dirname(os.path.abspath(__file__))
PROD_STATE = "https://raw.githubusercontent.com/cyrillaferrere/kraken-sim/main/state/public_state.json"
OUT = os.environ.get("PREPROD_OUT", os.path.join(D, "_site"))
data = json.loads(urllib.request.urlopen(urllib.request.Request(PROD_STATE, headers={"User-Agent": "kraken-sim-preprod"}), timeout=30).read())
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
# Le JS live lit le state.json de PROD (et les prix Kraken, inchangés)
html, n = re.subn(r'const STATE_URL = [^;\n]*;', f'const STATE_URL = "{PROD_STATE}";', html, count=1)
assert n == 1, "STATE_URL introuvable dans le template"
# Bandeau préprod injecté à la publication uniquement (jamais dans le template, donc jamais en prod)
BAN = ('<div id="preprod-banner" style="position:sticky;top:0;z-index:99999;background:repeating-linear-gradient(45deg,#b00020,#b00020 18px,#8a0018 18px,#8a0018 36px);'
       'color:#fff;font:800 18px/1.3 system-ui,sans-serif;text-align:center;padding:12px 8px;letter-spacing:.5px;border-bottom:4px solid #ffd400">'
       '⚠ PRÉPRODUCTION — NE PAS CONFONDRE AVEC LA SIMULATION OFFICIELLE ⚠<br><span style="font-weight:500;font-size:13px">'
       'Données en lecture seule de la prod · officielle : cyrillaferrere.github.io/kraken-sim</span></div>')
html, n = re.subn(r'(<body[^>]*>)', r'\1' + BAN.replace("\\", "\\\\"), html, count=1)
assert n == 1, "<body> introuvable"
html = html.replace("<title>", "<title>[PRÉPROD] ", 1)
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "index.html"), "w").write(html)
open(os.path.join(OUT, ".nojekyll"), "w").write("")
print("préprod rendue :", os.path.join(OUT, "index.html"), "| état prod du", data.get("as_of"))
