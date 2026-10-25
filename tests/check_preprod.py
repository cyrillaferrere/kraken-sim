#!/usr/bin/env python3
"""Vérifie _site/index.html (préprod) : bandeau, STATE_URL de prod, zéro erreur JS, aucun undefined/NaN visible."""
import os, re, shutil, subprocess, sys, tempfile
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.environ.get("PREPROD_OUT", os.path.join(D, "_site")) + "/index.html"
h = open(P).read(); bad = []
if "PreProd</small>" not in h: bad.append("identification discrète PreProd absente")
if "preprod-banner" in h: bad.append("ancien bandeau rouge toujours présent")
if 'const STATE_URL = "https://raw.githubusercontent.com/cyrillaferrere/kraken-sim/main/state/public_state.json";' not in h: bad.append("STATE_URL ne pointe pas vers la prod")
if "__DATA__" in h: bad.append("données non injectées")
chrome = next((shutil.which(b) for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(b)), None)
if chrome:
    inj = '<script>window.__E=[];addEventListener("error",e=>__E.push(String(e.message)));addEventListener("unhandledrejection",e=>__E.push("promesse : "+e.reason));setTimeout(()=>document.title="ERR="+JSON.stringify(__E),10000)</script>'
    t = tempfile.mktemp(suffix=".html"); open(t, "w").write(h.replace("<head>", "<head>" + inj, 1))
    dom = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=12000", "--dump-dom", "file://" + t], capture_output=True, text=True, timeout=120).stdout
    m = re.search(r"<title>ERR=(.*?)</title>", dom, re.S)
    if not m or m.group(1) != "[]": bad.append("erreurs JS : " + (m.group(1) if m else "titre non posé"))
    txt = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", dom, flags=re.S)
    for w in ("undefined", "NaN", "[object Object]"):
        if re.search(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", txt): bad.append(f"« {w} » visible")
    if "Stratégie : V" not in txt: bad.append("bandeau des versions non rempli")
else: print("INFO : Chrome absent, test navigateur ignoré")
print("\n".join("ÉCHEC : " + b for b in bad) or "OK préprod : bandeau, state prod, zéro erreur JS")
sys.exit(1 if bad else 0)
