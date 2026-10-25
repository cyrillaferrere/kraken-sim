import copy
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from v12_v11_replay import (run_in_temporary_directory,replay_fixture,
                             check_snapshots,assert_not_official_baseline)

UTC=timezone.utc
PAIRS={"XXBTZUSD":("XBT",250.0),"XETHZUSD":("ETH",130.0),"XXRPZUSD":("XRP",0.8)}
def make_api():
    day=datetime(2026,10,24,tzinfo=UTC)
    assetpairs={}
    ticker={}
    ohlc={}
    trades={}
    depth={}
    for pair,(asset,price) in PAIRS.items():
        assetpairs[pair]={"quote":"ZUSD","wsname":asset+"/USD","status":"online"}
        ticker[pair]={"b":[str(price*.999)],"a":[str(price*1.001)],
                      "c":[str(price)],"v":["0","100000"],"p":["0","1"]}
        rows=[]
        for i in range(140):
            ts=int((day-timedelta(days=140-i)).timestamp())
            close=price*(1+0.0005*i)
            rows.append([ts,close,close*1.005,close*.995,close,
                         close,100000,20])
        ohlc[pair]={pair:rows,"last":str(rows[-1][0])}
        trades[pair]={pair:[],"last":"0"}
        depth[pair]={pair:{"asks":[[price*1.001,"100000","1"]],
                           "bids":[[price*.999,"100000","1"]]}}
    return {"AssetPairs":assetpairs,"Ticker":ticker,"OHLC":ohlc,
            "Trades":trades,"Depth":depth}

def fixture():
    api=make_api()
    return {"source":"SYNTHETIC_FOR_CI_ONLY",
            "cycles":[{"now_utc":"2026-10-24T01:10:00Z","api":api},
                      {"now_utc":"2026-10-24T04:10:00Z","api":api}]}

class TestV11OfflineReplay(unittest.TestCase):
    def test_original_engine_deterministic_without_network(self):
        a=run_in_temporary_directory(fixture())
        b=run_in_temporary_directory(fixture())
        self.assertEqual(a,b)
        self.assertEqual(a["classification"],
                         "OFFLINE_FIXTURE_ONLY_NOT_HISTORICAL_REPRODUCTION")
        self.assertEqual(len(a["cycles"]),2)
        self.assertEqual(a["capital_initial_usd"],6605.10)
        self.assertTrue(all(row[1]=="ok" and row[3]=="V1.1" for row in a["cycles"]))
        self.assertGreaterEqual(len(a["orders"]),3)
        self.assertEqual({row[1] for row in a["orders"][:3]},{"XBT","ETH","XRP"})
        self.assertEqual({row[7] for row in a["orders"][:3]},{"V1.2"})
        with self.assertRaisesRegex(ValueError,"NOT_VERIFIED_V11_BASELINE"):
            assert_not_official_baseline(a)
    def test_no_production_ledger_or_history(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"replay"
            result=replay_fixture(fixture(),root)
            self.assertTrue((root/"fixture_v11.db").exists())
            self.assertTrue((root/"fixture_history"/"state"/"history"/"index.json").exists())
            self.assertEqual(result["classification"],
                             "OFFLINE_FIXTURE_ONLY_NOT_HISTORICAL_REPRODUCTION")
            with self.assertRaisesRegex(ValueError,"WOULD_OVERWRITE"):
                replay_fixture(fixture(),root)
    def test_invalid_snapshot_halts_before_engine(self):
        f=fixture()
        f["cycles"][1]["now_utc"]=f["cycles"][0]["now_utc"]
        with self.assertRaisesRegex(ValueError,"NON_MONOTONIC"):
            check_snapshots(f)
        f=fixture()
        del f["cycles"][1]["api"]["OHLC"]
        # shared dict in synthetic fixture also affects first cycle: still fails.
        with self.assertRaisesRegex(ValueError,"MISSING_PUBLIC_SNAPSHOTS"):
            check_snapshots(f)
    def test_rejects_network_dependent_missing_pair(self):
        f=fixture()
        f["cycles"][0]["api"]["OHLC"].pop("XXBTZUSD")
        with self.assertRaisesRegex(ValueError,"V11_REPLAY_PAIR_MISSING"):
            run_in_temporary_directory(f)
if __name__=="__main__":
    unittest.main()
