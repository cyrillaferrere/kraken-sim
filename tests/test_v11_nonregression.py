"""Static V1.1 freeze; deterministic trading replay to be added once fixtures exist."""
import subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BLOB="1e150eb33c8b2f550103acd1badecf574b645eb3"
class TestV11Freeze(unittest.TestCase):
    def test_engine_unchanged(self):
        sha=subprocess.check_output(["git","hash-object","cycle_v11.py"],cwd=ROOT,text=True).strip()
        self.assertEqual(sha,BLOB)
    def test_prod_workflow_calls_only_v11(self):
        yml=(ROOT/".github/workflows/sim.yml").read_text()
        self.assertIn("python3 cycle_v11.py",yml)
        self.assertNotIn("cycle_v12.py",yml)
if __name__=="__main__": unittest.main()
