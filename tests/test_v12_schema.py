import tempfile,unittest
from export_v12 import normalize,write_export
class TestExport(unittest.TestCase):
    def setUp(self):
        self.raw={"equity":6605.10,"cash":6605.10,"positions":[],"orders":[],
                  "decisions":[],"as_of":"2026-10-25T00:00:00Z","last_cycle_iso":"2026-10-25T00:00:00Z"}
    def test_version_and_absent_value(self):
        self.raw["btc_regime"]=None
        o=normalize(self.raw)
        self.assertIsNone(o["btc_regime"])
        self.assertEqual((o["strategy_version"],o["environment"]),("V1.2","preprod"))
    def test_reject_prod_and_missing(self):
        with self.assertRaises(ValueError): normalize(dict(self.raw,strategy_version="V1.1"))
        with self.assertRaises(ValueError): normalize({"cash":100})
    def test_only_explicit_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(write_export(self.raw,tmp).exists())
if __name__=="__main__": unittest.main()
