import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/"cycle_v12.py"

class TestSyntheticCLI(unittest.TestCase):
    def test_thirty_day_dry_run_writes_only_external_fixture_directory(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/"synthetic-test"
            run=subprocess.run([sys.executable,str(CLI),"--dry-run","--out",str(output)],
                               cwd=ROOT,capture_output=True,text=True,timeout=60)
            self.assertEqual(run.returncode,0,run.stderr)
            result=json.loads(run.stdout)
            self.assertEqual(result["synthetic_elapsed_days"],30)
            self.assertEqual(result["scope"],"DRY_RUN_ONLY_NOT_OFFICIAL_PERFORMANCE")
            self.assertFalse(result["provider_grok_called"])
            self.assertFalse(result["real_market_data_used"])
            self.assertEqual(result["kill_count"],1)
            self.assertEqual(result["orders_by_status"]["EXPIRED"],1)
            self.assertEqual(len(result["grok_it_absences"]),3)
            self.assertTrue((output/"dry_run_30d.json").exists())
            self.assertTrue((output/"synthesis.json").exists())
            self.assertTrue((output/"decision_fixture.json").exists())
            self.assertFalse((ROOT/"paper_engine_v12.db").exists())
            again=subprocess.run([sys.executable,str(CLI),"--dry-run","--out",str(output)],
                                 cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertNotEqual(again.returncode,0)
            self.assertIn("DRY_RUN_OUTPUT_ALREADY_EXISTS",again.stderr)
    def test_production_cycle_remains_blocked_and_preflight_readonly(self):
        with tempfile.TemporaryDirectory() as td:
            env=dict(os.environ,V12_STATE_DIR=str(Path(td)/"external_state"))
            pre=subprocess.run([sys.executable,str(CLI),"--validate-env"],
                               env=env,cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(pre.returncode,0,pre.stderr)
            self.assertFalse((Path(td)/"external_state").exists())
            act=subprocess.run([sys.executable,str(CLI),"--cycle"],
                               env=env,cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(act.returncode,3)
            self.assertIn("BLOCKED",act.stderr)
            self.assertFalse((Path(td)/"external_state").exists())
    def test_no_implicit_dry_run_without_external_path(self):
        result=subprocess.run([sys.executable,str(CLI),"--dry-run"],
                              cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("--out",result.stderr)
if __name__=="__main__":unittest.main()
