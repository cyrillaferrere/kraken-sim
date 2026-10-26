"""Moteur V1.6.1 : garde-fou UE/MiCA (USDC uniquement, spot long, FR)."""
import unittest
import v12_compliance as c
import v12_kraken_public as kp

SNAP={"compliance":{"quote":"USDC","eligible":["BTC","ETH","SOL"],"insufficient_history":["SOL"]}}
def dec(**k):
    base={"decision_id":"x","action":"BUY","asset":"BTC","quantity":"1","order_type":"taker"}
    base.update(k);return base

class EuCompliance(unittest.TestCase):
    def test_rejects_usd_pair(self):
        with self.assertRaisesRegex(c.ComplianceError,"QUOTE_NOT_USDC"):
            c.check_decision(dec(asset="BTC/USD"),SNAP,{})
        self.assertEqual(c.pair_rejection({"wsname":"XBT/USD","status":"online"}),"QUOTE_NOT_USDC")
    def test_rejects_usdt(self):
        with self.assertRaisesRegex(c.ComplianceError,"STABLECOIN"):
            c.check_decision(dec(asset="USDT"),SNAP,{})
        with self.assertRaisesRegex(c.ComplianceError,"QUOTE_NOT_USDC"):
            c.check_decision(dec(asset="BTC/USDT"),SNAP,{})
        self.assertEqual(c.pair_rejection({"wsname":"USDT/USDC","status":"online"}),"STABLECOIN_OR_FIAT_EXCLUDED")
    def test_rejects_short_and_leverage(self):
        with self.assertRaisesRegex(c.ComplianceError,"SHORT"):
            c.check_decision(dec(action="SELL",quantity="1"),SNAP,{})
        with self.assertRaisesRegex(c.ComplianceError,"LEVERAGE"):
            c.check_decision(dec(leverage=2),SNAP,{})
        with self.assertRaisesRegex(c.ComplianceError,"LEVERAGE"):
            c.check_decision(dec(margin=True),SNAP,{})
        self.assertTrue(c.check_decision(dec(action="SELL",quantity="1"),SNAP,{"BTC":{"qty":"1"}}))
    def test_rejects_fr_restricted_and_ineligible(self):
        with self.assertRaisesRegex(c.ComplianceError,"FR_RESTRICTED"):
            c.check_decision(dec(asset="XMR"),SNAP,{})
        with self.assertRaisesRegex(c.ComplianceError,"NOT_ELIGIBLE"):
            c.check_decision(dec(asset="ADA"),SNAP,{})
        with self.assertRaisesRegex(c.ComplianceError,"INSUFFICIENT_HISTORY"):
            c.check_decision(dec(asset="SOL"),SNAP,{})
    def test_universe_100pct_usdc(self):
        rows={"XBTUSDC":{"wsname":"XBT/USDC","status":"online"},"ETHUSD":{"wsname":"ETH/USD","status":"online"},
              "OFF":{"wsname":"ADA/USDC","status":"cancel_only"},"T":{"wsname":"USDT/USDC","status":"online"},
              "M":{"wsname":"XMR/USDC","status":"online"}}
        found,rej=kp.pairs_usdc(rows)
        self.assertEqual(set(found),{"BTC"})
        self.assertEqual(rej,{"ADA":"PAIR_NOT_ONLINE","USDT":"STABLECOIN_OR_FIAT_EXCLUDED","XMR":"FR_RESTRICTED_ASSET"})
        self.assertFalse(hasattr(kp,"usdc_quote"))  # plus de conversion USD
        self.assertFalse(c.spread_ok("100","100.5"));self.assertTrue(c.spread_ok("100","100.2"))

if __name__=="__main__":unittest.main()
