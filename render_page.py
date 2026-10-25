#!/usr/bin/env python3
"""V1.1 (socle) render step: page_data.py -> page_contents.txt (Page/WriteCanvas) + dashboard.html + état public JSON (publié sur gist)."""
import subprocess, os, sys, json, urllib.request
D = os.path.dirname(os.path.abspath(__file__))
data = json.loads(subprocess.check_output([sys.executable, os.path.join(D, "page_data.py")], text=True))
O = os.environ.get("SIM_OUT", D)  # dry-run : sortie ailleurs
js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
# V1.1 socle : la Page ne reçoit que les champs qu'elle affiche (contenu WriteCanvas plus léger)
PK = ("core","cash","exposure_pct","total","snapshot","curve","C0","killed","as_of","n_cycles","start_paris","net_return_pct","vs_btc_pct","btc_return_pct","max_dd_pct","cur_dd_pct","fees","n_trades","allocation","positions","pending","btc_regime_state","btc_regime","universe","fees_tier","indicators","indicators_src","journal","ablation","version")
pd = {k: data.get(k) for k in PK}; pd["decision_cycles"] = (data.get("decision_cycles") or [])[:1]; pd["journal"] = (data.get("journal") or [])[:15]
def _r(o): return {k: _r(v) for k, v in o.items()} if isinstance(o, dict) else [_r(v) for v in o] if isinstance(o, list) else float(f"{o:.7g}") if isinstance(o, float) else o
pd = _r(pd)
pd["curve"] = [{k: p.get(k) for k in ("t","sim","btc","core","strat")} for p in data["curve"]]
open(os.path.join(O, "page_contents.txt"), "w").write(open(os.path.join(D, "page_template.tsx")).read().replace("__DATA__", json.dumps(pd, ensure_ascii=False, separators=(",", ":"))))
html = open(os.path.join(D, "dashboard_template.html")).read().replace("__DATA__", js.replace("</", "<\\/"))
open(os.path.join(O, "dashboard.html"), "w").write(html)
print(os.path.join(O, "page_contents.txt")); print(os.path.join(O, "dashboard.html"))
# ---------- V1.04 : état public (lu par le HTML toutes les 60 s) ----------
SKIP = {"walkforward", "backtest", "lessons", "C0_source"}
state = {k: v for k, v in data.items() if k not in SKIP}
sp = os.path.join(O, "state", "public_state.json"); os.makedirs(os.path.dirname(sp), exist_ok=True)
sj = json.dumps(state, ensure_ascii=False, separators=(",", ":")); open(sp, "w").write(sj); print(sp)
REPO, FN = "cyrillaferrere/kraken-sim-state", "state.json"  # URL publique : https://raw.githubusercontent.com/cyrillaferrere/kraken-sim-state/main/state.json
if os.environ.get("SIM_OUT"): print("dry-run : publication ignorée"); sys.exit(0)
if os.environ.get("SIM_NO_REMOTE"): print("GitHub Actions : état servi par GitHub Pages (state/public_state.json), pas de publication externe"); sys.exit(0)
tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not tok:
    try: tok = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception: tok = ""
if not tok:
    print(f"PUBLISH_PENDING: pas de jeton GitHub sur la box ; publier state/public_state.json vers {REPO}/{FN} (branche main) via le connecteur GitHub create_or_update_file."); sys.exit(0)
try:
    import base64
    H = {"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json", "User-Agent": "kraken-sim"}
    u = f"https://api.github.com/repos/{REPO}/contents/{FN}"
    sha = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=20).read())["sha"]
    body = {"message": "état sim " + data["as_of"], "content": base64.b64encode(sj.encode()).decode(), "sha": sha, "branch": "main"}
    urllib.request.urlopen(urllib.request.Request(u, method="PUT", data=json.dumps(body).encode(), headers=H), timeout=20).read(); print("PUBLISHED " + REPO)
except Exception as e: print("PUBLISH_FAILED: " + str(e))
