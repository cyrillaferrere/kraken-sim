#!/usr/bin/env python3
"""Contrôle du contrat d'interface du dashboard (voir GARDE_FOUS.md).
Usage : python3 tests/check_template.py [--no-browser]
Code de sortie 0 = OK, 1 = contrat cassé."""
import json, os, re, shutil, subprocess, sys, tempfile
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = open(os.path.join(R, "dashboard_template.html"), encoding="utf-8").read()
C = json.load(open(os.path.join(R, "tests", "contract.json"), encoding="utf-8"))
errs = []
def bad(m): errs.append(m); print("ÉCHEC :", m)
def ok(m): print("OK    :", m)

# 1. injection unique des données
n = len(re.findall(r"__DATA__", T))
if n != 1 or T.count("const D = __DATA__;") != 1: bad(f"il faut exactement une ligne 'const D = __DATA__;' et aucun autre __DATA__ (trouvé {n})")
else: ok("injection unique 'const D = __DATA__;'")
# 2. deux blocs <script>
ns = len(re.findall(r"<script\b", T, re.I))
if ns != 2: bad(f"il faut exactement 2 blocs <script> (trouvé {ns})")
else: ok("2 blocs <script>")
# 3. pas de données d'exemple en dur
for pat, why in ((r"\bD\s*=\s*\{", "objet D écrit en dur"), (r"\bD\s*=\s*JSON\.parse\(", "D remplacé par un JSON en dur"),
                 (r"(?i)lorem ipsum", "texte factice"), (r"(?i)(données|data)\s*(fictives|d'exemple|mock)", "jeu de données fictif")):
    if re.search(pat, T): bad(f"donnée d'exemple interdite : {why}")
ok("pas de données d'exemple en dur") if not any("exemple" in e for e in errs) else None
# 4. sources live obligatoires
for s, why in (("STATE_URL", "lecture de l'état publié (state.json)"), ("fetch(STATE_URL", "fetch de l'état publié"),
               ("api.kraken.com/0/public/Ticker", "prix live Kraken (Ticker)"), ("api.kraken.com/0/public/OHLC", "bougies Kraken (OHLC)"),
               ("state/public_state.json", "état servi par GitHub Pages")):
    if s not in T: bad(f"source live manquante : {why} ({s})")
ok("sources live (state.json + API publique Kraken)") if not any("source live" in e for e in errs) else None
# 4b. versions distinctes
mv = re.findall(r'^const VERSION_UX = "(V\d+(?:\.\d+)*)";', T, re.M)
if len(mv) != 1: bad("il faut exactement une ligne 'const VERSION_UX = \"Vx.y\";' (version UX/UI)")
else: ok(f"version UX/UI {mv[0]}")
if "D.version_engine" not in T: bad("la version moteur (D.version_engine) n'est plus affichée")
if not os.path.exists(os.path.join(R, "VERSION_ENGINE")): bad("fichier VERSION_ENGINE absent")
# 5. ids requis
ids = set(re.findall(r'\bid="([^"]+)"', T)) | set(re.findall(r"\bid='([^']+)'", T))
miss = [i for i in C["required_ids"] if i not in ids]
if miss: bad(f"ids requis supprimés : {', '.join(miss)}")
else: ok(f"{len(C['required_ids'])} ids requis présents")
js_ids = set(re.findall(r"""(?:\$|el|getElementById)\(\s*["']([A-Za-z_][\w-]*)["']\s*\)""", T))
orphan = sorted(i for i in js_ids if i not in ids)
if orphan: bad(f"le JS utilise des ids absents du HTML : {', '.join(orphan)}")
# 6. clés de D : celles du contrat restent utilisées... et toute clé utilisée doit exister dans les données réelles
data = json.loads(subprocess.check_output([sys.executable, os.path.join(R, "page_data.py")], text=True, cwd=R))
used = set(re.findall(r"\bD\.([A-Za-z_]\w*)", T))
RUNTIME = {"equity"}  # clés recalculées dans le navigateur
unknown = sorted(k for k in used if k not in data and k not in RUNTIME)
if unknown: bad(f"clés de D inexistantes dans les données du moteur : {', '.join(unknown)} (demander au fonctionnel via une issue 'fonctionnel')")
else: ok(f"{len(used)} clés de D utilisées, toutes fournies par page_data.py")
dropped = sorted(k for k in C["required_D_keys"] if k not in used)
if dropped: print("INFO  : clés du contrat plus affichées :", ", ".join(dropped), "(vérifier que ce n'est pas une perte d'information)")
# 7. rendu réel + navigateur headless
out = tempfile.mkdtemp(); env = dict(os.environ, SIM_OUT=out)
r = subprocess.run([sys.executable, os.path.join(R, "render_page.py")], cwd=R, env=env, capture_output=True, text=True)
if r.returncode: bad("render_page.py a échoué : " + r.stderr[-500:])
else: ok("render_page.py (données réelles, sortie temporaire)")
chrome = next((shutil.which(b) for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(b)), None)
if "--no-browser" in sys.argv or not chrome or r.returncode: print("INFO  : test navigateur ignoré")
else:
    h = open(os.path.join(out, "dashboard.html"), encoding="utf-8").read()
    inj = '<script>window.__E=[];addEventListener("error",e=>__E.push(String(e.message)));addEventListener("unhandledrejection",e=>__E.push("promesse : "+e.reason));setTimeout(()=>document.title="ERR="+JSON.stringify(__E),10000)</script>'
    p = os.path.join(out, "t.html"); open(p, "w", encoding="utf-8").write(h.replace("<head>", "<head>" + inj, 1))
    dom = subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=12000", "--dump-dom", "file://" + p], capture_output=True, text=True, timeout=120).stdout
    m = re.search(r"<title>ERR=(.*?)</title>", dom, re.S)
    if not m: bad("le navigateur n'a pas terminé le rendu")
    elif m.group(1).strip() != "[]": bad("erreurs JS : " + m.group(1)[:600])
    else: ok("aucune erreur JS (Chrome headless)")
    vis = re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", "", dom, flags=re.S | re.I))
    hits = [re.sub(r"\s+", " ", vis[max(0, x.start()-60):x.end()+20]) for x in re.finditer(r"undefined|NaN|\[object Object\]|null \$", vis)]
    if hits: bad("valeurs non définies affichées : " + " | ".join(hits[:5]))
    else: ok("aucun undefined / NaN affiché")
    vm = re.search(r'id="versions"[^>]*>([^<]*)', dom)
    if not vm or "Moteur : V" not in vm.group(1) or "UX/UI : V" not in vm.group(1): bad("bandeau des versions non rempli : " + (vm.group(1) if vm else "absent"))
    else: ok("versions affichées : " + vm.group(1))
print("\nRÉSULTAT :", "CONTRAT CASSÉ" if errs else "contrat respecté")
sys.exit(1 if errs else 0)
