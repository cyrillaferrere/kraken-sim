import unittest
from datetime import datetime,timezone,timedelta
from v12_walkforward import (make_folds,neighbors,param_grid,concat_oos,
                             require_verifiable_baseline,gate_results)
class TestWalkForward(unittest.TestCase):
    def test_rolling_windows_do_not_overlap(self):
        start=datetime(2021,1,1,tzinfo=timezone.utc)
        days=[(start+timedelta(days=i)).date().isoformat() for i in range(1850)]
        folds=make_folds(days)
        self.assertGreaterEqual(len(folds),1)
        for f in folds:
            self.assertLess(f["train_end"],f["test_start"])
            self.assertLess(f["test_start"],f["test_end"])
        for a,b in zip(folds,folds[1:]):
            self.assertLess(a["test_end"],b["test_start"])
    def test_grid_and_neighbors_default(self):
        d={"grid":{"lookback":[60,90,120],"k":[3,4,5],"vol":[0.3,0.4,0.5]},
           "lookback":90,"k":4,"vol":0.4}
        self.assertEqual(len(list(param_grid(d))),27)
        self.assertEqual(len(neighbors(d)),6)
    def test_no_baseline_no_selection(self):
        f=[{"test_start":"2025-01-01","test_end":"2025-04-01"}]
        with self.assertRaisesRegex(ValueError,"V11_BASELINE_NOT_REPRODUCED"):
            gate_results({},None,"hash",f)
        with self.assertRaisesRegex(ValueError,"BASELINE_DATASET_MISMATCH"):
            require_verifiable_baseline({"status":"REPRODUCED_V11"},"hash",f)
    def test_oos_compounding_and_no_overlap(self):
        def run(s,e,ret):
            return {"start":s,"end":e,"net_return":ret,
                    "curve":[{"day":s,"equity":100*(1+ret),"cash":80}],
                    "fees_usd":0,"spread_usd":0,"slippage_usd":0,
                    "gross_profit_usd":ret*100,"closed_roundtrips":0,"kill_switch_count":0}
        r=concat_oos([run("2025-01-01","2025-01-01",.1),run("2025-04-01","2025-04-01",.1)],100.)
        self.assertAlmostEqual(r["net_return"],.21)
        with self.assertRaises(ValueError):
            concat_oos([run("2025-01-01","2025-04-01",.1),run("2025-04-01","2025-06-01",.1)],100)
if __name__=="__main__":unittest.main()
