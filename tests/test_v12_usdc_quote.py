"""Moteur V1.6: V1.2 account currency is USDC."""
import unittest
import v12_kraken_public as kp
from v12_accounting import d

USDC={"bid":"0.9997","ask":"0.9998"}
def t(b,a):return {"b":[b,"1","1"],"a":[a,"1","1"],"c":[a,"1"],"v":["1","100"]}

class UsdcQuote(unittest.TestCase):
    def test_direct_usdc_pair_preferred(self):
        tick={"XBTUSDC":t("100000","100010")}
        q=kp.usdc_quote("BTC",{"bid":"1","ask":"2"},{"BTC":("XBTUSDC",{})},tick,USDC)
        self.assertEqual((q["bid"],q["ask"]),("100000","100010"))
        self.assertEqual(q["valuation"],"KRAKEN_BTC_USDC_DIRECT")
    def test_fallback_usd_converted_conservatively(self):
        q=kp.usdc_quote("SOL",{"bid":"200","ask":"200.1"},{},{},USDC)
        self.assertEqual(d(q["bid"]),d("200")/d("0.9998"))
        self.assertEqual(d(q["ask"]),d("200.1")/d("0.9997"))
        self.assertEqual(q["valuation"],"KRAKEN_SOL_USD_DIV_USDCUSD")
    def test_wide_direct_pair_falls_back(self):
        tick={"SOLUSDC":t("190","210")}
        q=kp.usdc_quote("SOL",{"bid":"200","ask":"200.1"},{"SOL":("SOLUSDC",{})},tick,USDC)
        self.assertEqual(q["valuation"],"KRAKEN_SOL_USD_DIV_USDCUSD")
    def test_pairs_usdc(self):
        rows={"XBTUSDC":{"wsname":"XBT/USDC"},"ETHUSD":{"wsname":"ETH/USD"},
              "OFF":{"wsname":"ADA/USDC","status":"cancel_only"}}
        self.assertEqual(set(kp.pairs_usdc(rows)),{"BTC"})

if __name__=="__main__":unittest.main()
