import json,tempfile,unittest
from pathlib import Path
from v12_history import record_snapshot
class TestHistory(unittest.TestCase):
    def test_records_and_preserves_slots(self):
        with tempfile.TemporaryDirectory() as td:
            a={"slot":"2026102501","ts":"2026-10-25T01:10:00Z","status":"ok",
               "strategy_version":"V1.2","complete":True,"portfolio":None,"missing":["portfolio"]}
            path=record_snapshot(a,td)
            self.assertTrue(path.exists())
            with self.assertRaises(ValueError): record_snapshot(a,td)
            b=dict(a,slot="2026102502",ts="2026-10-25T02:10:00Z")
            record_snapshot(b,td)
            index=json.loads((Path(td)/"history"/"index.json").read_text())
            self.assertEqual(index["n_cycles"],2)
            self.assertEqual(index["months"][0]["month"],"2026-10")
    def test_foreign_state_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                record_snapshot({"slot":"2026102501","ts":"2026-10-25T01:00:00Z",
                                 "status":"ok","strategy_version":"V1.1"},td)
if __name__=="__main__": unittest.main()
