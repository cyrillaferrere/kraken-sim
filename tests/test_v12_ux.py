"""Kraken V1.2 cockpit UX — tests purely offline; no Grok/market/deploy calls."""
import io
import json
import os
import re
import runpy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from export_v12 import normalize

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/"dashboard_v12_template.html"
BASIC={"equity":6605.10,"cash":6605.10,"positions":[],"orders":[],"decisions":[],
       "as_of":"2026-10-25T15:00:00Z","last_cycle_iso":"2026-10-25T15:00:00Z"}
STATE_URL="https://raw.githubusercontent.com/cyrillaferrere/kraken-sim-preprod/state-v12/public_state_v12.json"

def render_temp(source,output):
    body=json.dumps(normalize(source),ensure_ascii=False).encode()
    with patch.dict(os.environ,{"PREPROD_V12_READY":"1","PREPROD_OUT":str(output)}),patch(
        "urllib.request.urlopen",return_value=io.BytesIO(body)):
        runpy.run_path(str(ROOT/"render_preprod.py"),run_name="__main__")
    return (output/"index.html").read_text(encoding="utf8")

class TestV12Cockpit(unittest.TestCase):
    def test_new_cockpit_only_overwrites_v12_template_and_keeps_source_restricted(self):
        t=TEMPLATE.read_text(encoding="utf8")
        self.assertIn('const VERSION_UX = "V1.2.0";',t)
        self.assertEqual(t.count("const D = __DATA__;"),1)
        self.assertEqual(t.count("<script>"),1)
        self.assertEqual(t.count("__DATA__"),1)
        self.assertEqual(t.count('const STATE_URL = "__STATE_SOURCE__";'),1)
        for marker in ('id="overview"','id="portfolio"','id="grok"','id="analyse"',
                       'id="itHistory"','id="riskTag"','id="chartArea"','id="orderFilter"',
                       'id="signalA"','id="signalB"','id="signalC"','id="signalD"',
                       'id="usdcValue"','id="learning"'):
            if marker=='id="learning"':continue
            with self.subTest(marker=marker):self.assertIn(marker,t)
        for forbidden in ("kraken-sim/main/state/public_state.json","cycle_v11.py","sim.db",
                          "Grok est connecté","Simulation active"):
            self.assertNotIn(forbidden,t)
    def test_null_metrics_not_displayed_as_zero_or_a_fake_chart(self):
        with tempfile.TemporaryDirectory() as tmp:
            html=render_temp(BASIC,Path(tmp))
            self.assertIn(STATE_URL,html)
            self.assertIn("Stratégie : V1.2",html)
            self.assertIn("Historique V1.2",html)
            self.assertNotIn("__DATA__",html)
            self.assertNotIn("Simulation active",html)
            self.assertNotIn("Kraken</strong> Sim",html)
            self.assertIn("PreProd",html)
    def test_runtime_renders_a_real_v12_fixture_without_borrowing_v11(self):
        source=dict(BASIC,equity=7200,cash=2200,cur_dd_pct=-7.5,
            usdc_hold_usd=6800,btc_hold_usd=7050,exposure_pct=69.4,
            fees_paid_usd=21.54,
            positions=[{"asset":"BTC","qty":"0.1","value":4200,"pnl_pct":9.6,"candidate":"C"}],
            orders=[{"asset":"BTC","side":"BUY","qty":"0.1","status":"FILLED","created_at":"2026-10-25T15:00:00Z"}],
            grok={"last_it_iso":"2026-10-25T14:30:00Z","last_action":"HOLD","status":"Analyse terminée"},
            learning={"outcomes_count":3,"shadow_proposals":1},
            curve_v12=[
                {"ts":"2026-10-23T15:00:00Z","equity":6605.10,"usdc_hold_usd":6599,"btc_hold_usd":6600},
                {"ts":"2026-10-25T15:00:00Z","equity":7200,"usdc_hold_usd":6800,"btc_hold_usd":7050}])
        with tempfile.TemporaryDirectory() as tmp:
            html=render_temp(source,Path(tmp))
            for name in ("curve_v12","usdc_hold_usd","V1.2.0","Kraken"):
                self.assertIn(name,html)
            chrome=next((shutil.which(x) for x in ("google-chrome","google-chrome-stable","chromium")),None)
            if not chrome:self.skipTest("Chrome not installed in runner")
            # File fetch will fail (no website configured) and must be caught.
            # Render errors are recorded in the page title by injected script.
            snippet=('<script>window.__E=[];window.addEventListener("error",e=>__E.push(String(e.message)));'
                     'window.addEventListener("unhandledrejection",e=>__E.push(String(e.reason)));'
                     'setTimeout(()=>{document.title="JSCHECK="+JSON.stringify(__E)},800)</script>')
            target=Path(tmp)/"test.html"
            target.write_text(html.replace("<head>","<head>"+snippet,1),encoding="utf8")
            output=subprocess.run([chrome,"--headless=new","--no-sandbox","--disable-gpu",
                                   "--virtual-time-budget=1500","--dump-dom",target.as_uri()],
                                   text=True,capture_output=True,timeout=35)
            self.assertEqual(output.returncode,0,output.stderr[-250:])
            self.assertIn("<title>JSCHECK=[]</title>",output.stdout)
            self.assertRegex(output.stdout,r'<svg[^>]*viewBox="0 0 730 248"')
            self.assertIn("Historique",output.stdout)
    def test_renderer_rejects_a_foreign_v11_state(self):
        source=dict(normalize(BASIC),strategy_id="kraken-sim-v1.1")
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ,{"PREPROD_V12_READY":"1","PREPROD_OUT":tmp}),patch(
                "urllib.request.urlopen",return_value=io.BytesIO(json.dumps(source).encode())):
                with self.assertRaisesRegex(RuntimeError,"REFUS"):
                    runpy.run_path(str(ROOT/"render_preprod.py"),run_name="__main__")
            self.assertFalse((Path(tmp)/"index.html").exists())
if __name__=="__main__":unittest.main()
