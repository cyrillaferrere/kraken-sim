"""Negative regression: a strategy/* PR changing V1.1 production state must fail."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
YAML=(ROOT / ".github/workflows/guard.yml").read_text(encoding="utf8")
JOB=YAML.split("  perimetre-strategie:", 1)[1].split("  isolation-v12:", 1)[0]
MATCH=re.search(r"""BAD=\$\(echo "\$FILES" \| grep -E '([^']+)'""", JOB)
if MATCH is None:
    raise AssertionError("Missing strategy protected-path detection")
FORBIDDEN=re.compile(MATCH.group(1))

class TestProtectedPaths(unittest.TestCase):
    def test_all_production_state_files_are_denied(self):
        for path in ("state/x.json", "state/public_state.json", "state/history/index.json",
                     "state/history/2026-10.json", "state/aa/bb/cc.db", "state/.hidden"):
            with self.subTest(path=path):
                self.assertIsNotNone(FORBIDDEN.search(path))
    def test_v11_files_are_denied(self):
        for path in ("sim.db", "cycle_v11.py", "cycle.py", "strategy/params.json",
                     ".github/workflows/sim.yml", "page_data.py",
                     "render_page.py", "dashboard_template.html"):
            with self.subTest(path=path):
                self.assertIsNotNone(FORBIDDEN.search(path))
    def test_v12_files_are_permitted(self):
        for path in ("cycle_v12.py", "strategy/v1_2/params.json",
                     "docs/ARCHI_PREPROD_V1_2.md", ".github/workflows/sim_v12.yml"):
            with self.subTest(path=path):
                self.assertIsNone(FORBIDDEN.search(path))
    def test_rule_covers_strategy_branches_without_other_job(self):
        self.assertIn("startsWith(github.head_ref, 'strategy/')",JOB)
        self.assertIn('test -z "$BAD"',JOB)

if __name__=="__main__":
    unittest.main()
