"""Check engine-version isolation in PR #7; never relabel V1.1 paper orders."""
import unittest
from pathlib import Path
from export_v12 import normalize

ROOT=Path(__file__).resolve().parents[1]
class TestVersionIsolation(unittest.TestCase):
    def test_engine_versions_are_independent(self):
        shared=(ROOT/"VERSION_ENGINE").read_text(encoding="utf8").strip()
        isolated=(ROOT/"VERSION_ENGINE_V12").read_text(encoding="utf8").strip()
        self.assertEqual(shared,"V1.2")
        self.assertEqual(isolated,"V1.5")
        self.assertNotEqual(shared,isolated)
    def test_export_only_uses_v12_version(self):
        data={"equity":6605.10,"cash":6605.10,"positions":[],"orders":[],
              "decisions":[],"as_of":"2026-10-25T15:00:00Z",
              "last_cycle_iso":"2026-10-25T15:00:00Z"}
        exported=normalize(data)
        self.assertEqual(exported["version_engine"],(ROOT/"VERSION_ENGINE_V12").read_text().strip())
        self.assertEqual(exported["strategy_version"],"V1.2")
    def test_v11_consumer_not_migrated(self):
        original=(ROOT/"cycle_v11.py").read_text(encoding="utf8")
        self.assertIn("VERSION_ENGINE",original)
        self.assertNotIn("VERSION_ENGINE_V12",original)
if __name__=="__main__":unittest.main()
