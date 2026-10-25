import os, subprocess, sys, tempfile, unittest
from pathlib import Path
from v12_isolation import ROOT, IsolationError, state_dir, db_path
class TestIsolation(unittest.TestCase):
    def test_explicit_absolute_location(self):
        for v in ("","v12_state","state"):
            with self.assertRaises(IsolationError): state_dir(v)
    def test_forbid_production_directory(self):
        for v in (str(ROOT),str(ROOT/"state"),"/"):
            with self.assertRaises(IsolationError): state_dir(v)
    def test_no_cycle_without_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,V12_STATE_DIR=tmp)
            cmd=[sys.executable,str(ROOT/"cycle_v12.py")]
            self.assertEqual(subprocess.run(cmd+["--validate-env"],env=env,capture_output=True).returncode,0)
            self.assertNotEqual(subprocess.run(cmd+["--cycle"],env=env,capture_output=True).returncode,0)
            self.assertFalse(db_path(tmp).exists())
if __name__=="__main__": unittest.main()
