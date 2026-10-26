"""Offline V1.2 render fixture — NEVER touches GitHub Pages or a trading engine."""
import io
import json
import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from export_v12 import normalize

ROOT=Path(__file__).resolve().parents[1]
RAW={"equity":6605.10,"cash":6605.10,"positions":[],"orders":[],"decisions":[],
     "as_of":"2026-10-25T15:00:00Z","last_cycle_iso":"2026-10-25T15:00:00Z"}

class TestV12Render(unittest.TestCase):
    def test_contract_all_legacy_fields_present_without_fake_zero(self):
        data=normalize(RAW)
        contract=json.loads((ROOT/"tests"/"contract.json").read_text())
        for key in contract["required_D_keys"]:
            with self.subTest(key=key): self.assertIn(key,data)
        self.assertIsNone(data["walkforward"])
        self.assertIsNone(data["backtest"])
        self.assertIsNone(data["btc_regime"])
        self.assertIsNone(data["cur_dd_pct"])
        self.assertEqual(data["source_detail"]["branch"],"state-v12")
        self.assertIn("+",data["generated_paris"])
    def test_local_render_only_v12_source_and_real_cycle(self):
        payload=json.dumps(normalize(RAW)).encode()
        with tempfile.TemporaryDirectory() as tmp:
            env={"PREPROD_V12_READY":"1","PREPROD_OUT":tmp}
            with patch.dict(os.environ,env),patch("urllib.request.urlopen",return_value=io.BytesIO(payload)):
                runpy.run_path(str(ROOT/"render_preprod.py"),run_name="__main__")
            html=(Path(tmp)/"index.html").read_text()
            self.assertIn("kraken-sim-preprod/state-v12/public_state_v12.json",html)
            self.assertIn("Stratégie : V1.2",html)
            self.assertNotIn("main/state/public_state.json",html)
            self.assertNotIn("D.walkforward[e]",html)
    def test_wrong_strategy_fails_closed_without_fallback(self):
        source=dict(normalize(RAW),strategy_id="foreign")
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ,{"PREPROD_V12_READY":"1","PREPROD_OUT":tmp}),patch("urllib.request.urlopen",return_value=io.BytesIO(json.dumps(source).encode())):
                with self.assertRaisesRegex(RuntimeError,"REFUS"):
                    runpy.run_path(str(ROOT/"render_preprod.py"),run_name="__main__")
            self.assertFalse((Path(tmp)/"index.html").exists())
if __name__=="__main__":unittest.main()
