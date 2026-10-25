import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import fetch_kraken_history_v12 as fetch

class Response(io.BytesIO):
    def __init__(self,data,status=200,content_range=None):
        super().__init__(data)
        self.status=status
        self.headers={"Content-Range":content_range} if content_range else {}

def archive_bytes():
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("XXBTZUSD_1440.csv","1735689600,100,102,99,101,100,10\n")
    return b.getvalue()

class TestKrakenManualDownload(unittest.TestCase):
    def test_dry_run_never_calls_network_or_creates_files(self):
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t)/"data"
            with patch.object(fetch.urllib.request,"urlopen",side_effect=AssertionError("NO NETWORK")):
                plan=fetch.run(str(directory))
            self.assertEqual(plan["mode"],"DRY_RUN")
            self.assertEqual(len(plan["urls"]),5)
            self.assertFalse(directory.exists())
    def test_each_sha_and_assembled_sha_are_verified(self):
        content=archive_bytes()
        # In tests only, use smaller distinct chunks and their SHA256.
        cuts=[content[:20],content[20:45],content[45:70],content[70:95],content[95:]]
        hashes=[hashlib.sha256(b).hexdigest() for b in cuts]
        parts=tuple(("Kraken_OHLCVT_Full.zip.part%02d"%i,h) for i,h in enumerate(hashes))
        def fake_open(request,timeout=None):
            name=request.full_url.rsplit("/",1)[-1]
            index=[x for x,_ in parts].index(name)
            offset=int(request.get_header("Range","bytes=0-").split("=")[1].split("-")[0])
            if offset:
                return Response(cuts[index][offset:],206,"bytes %d-%d/%d"%(offset,len(cuts[index])-1,len(cuts[index])))
            return Response(cuts[index])
        with tempfile.TemporaryDirectory() as t:
            dst=Path(t)/"kraken"
            dst.mkdir()
            # The first part was interrupted. Range resume MUST NOT duplicate bytes.
            (dst/(parts[0][0]+".partial")).write_bytes(cuts[0][:7])
            with patch.object(fetch,"FULL_PARTS",parts),patch.object(fetch,"FULL_SHA256",hashlib.sha256(content).hexdigest()),patch.object(fetch.urllib.request,"urlopen",side_effect=fake_open):
                for name,digest in parts:
                    p,status=fetch.get_part(dst,name,digest)
                    self.assertEqual(p.read_bytes(),cuts[int(name[-2:])])
                result,state=fetch.assemble(dst)
                self.assertEqual(result.read_bytes(),content)
                self.assertEqual(state,"assembled")
                config=fetch.build_config(dst,result)
                document=json.loads(config.read_text())
                self.assertEqual(document["archives"][0]["sha256"],hashlib.sha256(content).hexdigest())
                self.assertIn("NOT_HISTORICALLY_CERTIFIED",document["status"])
                self.assertEqual(fetch.build_config(dst,result),config)
                # A later invocation must not rewrite or discard verified evidence.
                self.assertEqual(json.loads(config.read_text())["archives"][0]["sha256"],
                                 hashlib.sha256(content).hexdigest())
    def test_invalid_resume_range_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)
            name="Kraken_OHLCVT_Full.zip.part00"
            expected=hashlib.sha256(b"abc").hexdigest()
            (dest/(name+".partial")).write_bytes(b"a")
            with patch.object(fetch.urllib.request,"urlopen",return_value=Response(b"bc",206,"bytes 0-1/3")):
                with self.assertRaisesRegex(ValueError,"INVALID_CONTENT_RANGE"):
                    fetch.get_part(dest,name,expected)
    def test_server_ignoring_range_restarts_and_does_not_append(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t); name="Kraken_OHLCVT_Full.zip.part00"
            (dest/(name+".partial")).write_bytes(b"UNRELATED")
            expected=hashlib.sha256(b"abc").hexdigest()
            with patch.object(fetch.urllib.request,"urlopen",return_value=Response(b"abc",200)):
                path,status=fetch.get_part(dest,name,expected)
            self.assertEqual(path.read_bytes(),b"abc")
            self.assertEqual(status,"downloaded")
    def test_wrong_checksum_never_promotes_to_verified(self):
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t);name="Kraken_OHLCVT_Full.zip.part00"
            with patch.object(fetch.urllib.request,"urlopen",return_value=Response(b"abc")):
                with self.assertRaisesRegex(ValueError,"PART_HASH"):
                    fetch.get_part(dest,name,"0"*64)
            self.assertFalse((dest/name).exists())
    def test_rejects_code_repo_and_production_state_locations(self):
        with self.assertRaisesRegex(ValueError,"OUTSIDE_REPOSITORY"):
            fetch.destination(str(fetch.HERE/"data"/"v12"))
        with tempfile.TemporaryDirectory() as t:
            (Path(t)/"sim.db").write_text("sentinel",encoding="utf8")
            with self.assertRaisesRegex(ValueError,"PRODUCTION_LEDGER"):
                fetch.destination(str(Path(t)/"output"))
    def test_optional_q3_is_not_independently_certified(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            f=d/fetch.Q3_NAME
            f.write_bytes(b"Q3 mock, not real historical archive")
            zipfile=(d/fetch.FULL_NAME)
            zipfile.write_bytes(b"mock full zip")
            with patch.object(fetch,"FULL_SHA256",hashlib.sha256(b"mock full zip").hexdigest()):
                cfg=fetch.build_config(d,zipfile)
                self.assertEqual(len(json.loads(cfg.read_text())["archives"]),1)
                cfg=fetch.build_config(d,zipfile,f)
                self.assertEqual(fetch.build_config(d,zipfile,f),cfg)
            q=json.loads(cfg.read_text())["archives"][1]
            self.assertFalse(q["checksum_independently_attested"])
            self.assertIn("Local fingerprint only",q["checksum_provenance"])

if __name__=="__main__":
    unittest.main()
