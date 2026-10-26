"""Moteur V1.6.5 : enveloppe initiale de 2 000 USDC répartie sur plusieurs paires."""
import unittest
from decimal import Decimal
import v12_autonomy as au

class TestEnvelope2000(unittest.TestCase):
    def test_params(self):
        r=au.SPEC["RISK"]
        self.assertEqual(Decimal(str(r["max_crypto_exposure_usdc"])),Decimal("2000"))
        self.assertTrue(r["initial_envelope_split"])
        self.assertEqual(r["initial_envelope_max_assets"],4)
        # 4 paires x 500 USDC : chaque part respecte 40 % par actif et 25 % par achat.
        self.assertLessEqual(2000/4,2000*r["max_per_asset_share"])
        self.assertLessEqual(2000/4,2000*r["max_buy_share_per_cycle"]+1e-9)
if __name__=="__main__":unittest.main()
