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
    def test_nested_clones_and_ledger_files_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ("kraken-sim", "kraken-sim-state", "kraken-sim-clone", "state"):
                with self.subTest(name=name), self.assertRaises(IsolationError):
                    state_dir(str(root / name / "paper"))
            foreign=root / "foreign-checkout"
            foreign.mkdir()
            (foreign / ".git").mkdir()
            with self.assertRaises(IsolationError):
                state_dir(str(foreign / "paper"))
            other=root / "other"
            other.mkdir()
            (other / "sim.db").write_text("V1.1 untouched")
            with self.assertRaises(IsolationError):
                state_dir(str(other / "paper"))
    def test_only_preprod_checkout_allowed_at_state_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp) / "paper-output"
            (p / ".git").mkdir(parents=True)
            (p / ".git" / "config").write_text("[remote \"origin\"]\n url = https://github.com/elsewhere/kraken-sim\n")
            with self.assertRaises(IsolationError):
                state_dir(str(p))
            (p / ".git" / "config").write_text("[remote \"origin\"]\n url = https://github.com/cyrillaferrere/kraken-sim-preprod.git\n")
            self.assertEqual(state_dir(str(p)),p.resolve())
    def test_no_cycle_without_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=dict(os.environ,V12_STATE_DIR=tmp)
            cmd=[sys.executable,str(ROOT/"cycle_v12.py")]
            self.assertEqual(subprocess.run(cmd+["--validate-env"],env=env,capture_output=True).returncode,0)
            self.assertNotEqual(subprocess.run(cmd+["--cycle"],env=env,capture_output=True).returncode,0)
            self.assertFalse(db_path(tmp).exists())
if __name__=="__main__": unittest.main()
