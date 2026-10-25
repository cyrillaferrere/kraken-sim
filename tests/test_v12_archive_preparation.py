import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from prepare_kraken_history_v12 import _archives, inventory, prepare

def sample_zip(root, name, btc="1735689600,100,102,99,101,2000,5\n", eth=None):
    path=Path(root)/name
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("folder/XXBTZUSD_1440.csv",btc)
        if eth is not None:
            z.writestr("folder/ETHUSD_1440.csv",eth)
        z.writestr("folder/USDTUSD_1440.csv","1735689600,1,1,1,1,100,10\n")
        z.writestr("folder/EURGBP_1440.csv","1735689600,1,1,1,1,100,10\n")
        z.writestr("MANIFEST.json",'{"archive":"test only"}')
    return dict(file=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                source_url="https://assets.kraken.com/testing/"+name,
                retrieved_utc="2026-10-25T12:00:00Z")

def mapping():
    return {"pairs":{
        "XXBTZUSD":{"asset":"BTC","listed_at":None,"status":"unknown",
                    "delisted_at":None,"evidence_url":None},
        "USDTUSD":{"exclude":True,"reason":"stablecoin"}
    }}

class TestArchivePreparation(unittest.TestCase):
    def test_scan_and_safe_draft_export(self):
        with tempfile.TemporaryDirectory() as td:
            src=sample_zip(td,"full.zip")
            arches=_archives({"archives":[src]})
            inv=inventory(arches)
            self.assertEqual(set(inv["pairs"]),{"XXBTZUSD","USDTUSD"})
            dest=Path(td)/"out"
            result=prepare(arches,mapping(),dest)
            self.assertEqual(result["status"],"DRAFT_ONLY")
            self.assertFalse((dest/"MANIFEST.json").exists())
            doc=json.loads((dest/"MANIFEST.draft.json").read_text())
            self.assertFalse(doc["coverage"]["all_historical_usd_spot_pairs_verified"])
            self.assertEqual(doc["files"][0]["asset"],"BTC")
            self.assertEqual(doc["files"][0]["status"],"unknown")
            self.assertEqual(doc["files"][0]["listed_at"],None)
            self.assertEqual(doc["files"][0]["sha256"],
                             hashlib.sha256((dest/"BTCUSD_1440.csv").read_bytes()).hexdigest())
    def test_no_unknown_pair_can_be_silently_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            src=sample_zip(td,"full.zip",eth="1735689600,100,101,99,100,1000,5\n")
            arches=_archives({"archives":[src]})
            with self.assertRaisesRegex(ValueError,"UNREVIEWED_PAIRS"):
                prepare(arches,mapping(),Path(td)/"output")
    def test_reject_changed_historical_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            old=sample_zip(td,"full.zip")
            new=sample_zip(td,"update.zip",btc="1735689600,100,102,99,102,2000,5\n")
            arches=_archives({"archives":[old,new]})
            with self.assertRaisesRegex(ValueError,"CONFLICTING_OVERLAP"):
                prepare(arches,mapping(),Path(td)/"output")
    def test_merges_matching_overlap_and_incremental_day(self):
        with tempfile.TemporaryDirectory() as td:
            initial="1735689600,100,102,99,101,2000,5\n"
            incr=initial+"1735776000,101,103,100,102,1000,9\n"
            a=sample_zip(td,"full.zip",btc=initial)
            b=sample_zip(td,"q3.zip",btc=incr)
            arches=_archives({"archives":[a,b]})
            result=prepare(arches,mapping(),Path(td)/"out")
            self.assertEqual(result["assets"],1)
            self.assertEqual(len((Path(td)/"out"/"BTCUSD_1440.csv").read_text().splitlines()),2)
    def test_rejects_nan_ohlc_rows_without_silent_failures(self):
        with tempfile.TemporaryDirectory() as td:
            source=sample_zip(td,"nan.zip",btc="1735689600,100,nan,99,101,2000,5\n")
            arches=_archives({"archives":[source]})
            with self.assertRaisesRegex(ValueError,"BAD_OHLCVT_PRICE_OR_TIME"):
                prepare(arches,mapping(),Path(td)/"out")
    def test_refuses_invalid_hash_origin_and_exclusion(self):
        with tempfile.TemporaryDirectory() as td:
            source=sample_zip(td,"full.zip")
            wrong=dict(source,sha256="0"*64)
            with self.assertRaisesRegex(ValueError,"ARCHIVE_HASH_MISMATCH"):
                _archives({"archives":[wrong]})
            tricky=dict(source,source_url="https://assets.kraken.com.evil.example/marketing/institutions/full.zip")
            with self.assertRaisesRegex(ValueError,"ARCHIVE_UNTRUSTED_ORIGIN"):
                _archives({"archives":[tricky]})
            wrong=dict(source,source_url="https://evil.example/full.zip")
            with self.assertRaisesRegex(ValueError,"ARCHIVE_UNTRUSTED_ORIGIN"):
                _archives({"archives":[wrong]})
            review=mapping()
            review["pairs"]["USDTUSD"].pop("reason")
            with self.assertRaisesRegex(ValueError,"EXCLUSION_WITHOUT_REASON"):
                prepare(_archives({"archives":[source]}),review,Path(td)/"out")
if __name__=="__main__":
    unittest.main()
