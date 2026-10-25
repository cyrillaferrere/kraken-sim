import hashlib,json,tempfile,unittest
from pathlib import Path
from v12_data import read_kraken_daily,load_manifest,require_official_coverage
class TestHistoricalData(unittest.TestCase):
    def test_missing_historical_universe_rejected(self):
        missing={"files":[{"asset":"BTC","file":"BTC.csv"}]}
        with self.assertRaisesRegex(ValueError,"UNIVERSE_INCOMPLETE"):
            require_official_coverage(missing)
        claim={"files":[{"asset":"BTC","listed_at":"2011-01-01","status":"active"}],
               "coverage":{"all_historical_usd_spot_pairs_verified":True,
                           "enumeration_source_url":"https://example.invalid/registry",
                           "enumeration_utc":"2026-10-25T17:00:00Z",
                           "historical_pair_ids":["BTC","DELISTED"]}}
        with self.assertRaisesRegex(ValueError,"UNIVERSE_INCOMPLETE"):
            require_official_coverage(claim)
        claim["coverage"]["historical_pair_ids"]=["BTC"]
        self.assertTrue(require_official_coverage(claim))
        claim["files"][0]["status"]="delisted"
        with self.assertRaisesRegex(ValueError,"UNIVERSE_UNVERIFIABLE"):
            require_official_coverage(claim)
    def test_headerless_kraken_format_and_gap(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"BTCUSD_1440.csv"
            p.write_text("1735689600,100,102,99,101,10000,400\n1735862400,102,104,101,103,12000,450\n")
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            bars,s=read_kraken_daily(p,h)
            self.assertEqual(len(bars),3)
            self.assertEqual(s["gaps_imputed"],1)
            self.assertEqual(bars[1]["volume"],0)
            self.assertTrue(bars[1]["imputed"])
            self.assertEqual(bars[0]["end"],"2025-01-02T00:00:00+00:00")
            with self.assertRaises(ValueError): read_kraken_daily(p,"0"*64)
    def test_reject_incorrect_source(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"BTCUSD_1440.csv"
            p.write_text("1735689600,100,102,99,101,100,4\n")
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            manifest={"files":[{"asset":"BTC","file":"BTCUSD_1440.csv","sha256":h,
                                "retrieved_utc":"2026-10-25T12:00:00Z","source_url":"kraken.com"}]}
            (Path(td)/"MANIFEST.json").write_text(json.dumps(manifest))
            result,meta=load_manifest(td)
            self.assertEqual(len(result["BTC"]),1)
            self.assertEqual(meta["files"]["BTC"]["rows"],1)
            manifest["files"][0]["file"]="../outside.csv"
            (Path(td)/"MANIFEST.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): load_manifest(td)
if __name__=="__main__": unittest.main()
