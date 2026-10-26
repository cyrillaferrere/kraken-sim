import unittest
from backtest import ind
from v12_v11_compat import indicator,entry_score
from test_v12_signals import candles
class TestV11IndicatorParity(unittest.TestCase):
    def test_replay_indicators_exactly_match_original_backtest(self):
        rows=candles()
        original=ind({i:(b["high"],b["low"],b["close"],b["volume"]) for i,b in enumerate(rows)})
        computed=indicator(rows)
        expected=original[max(original)]
        for k in ("atr","e20","e50","rsi","adx","pdi","mdi","mom","volup","macd"):
            with self.subTest(key=k): self.assertAlmostEqual(computed[k],expected[k])
        scored=entry_score(rows)
        self.assertEqual(scored["score"],sum([
            expected["c"]>expected["e50"] and expected["e20"]>expected["e50"],
            expected["macd"],50<expected["rsi"]<75,
            expected["adx"]>20 and expected["pdi"]>expected["mdi"],expected["volup"]]))
if __name__=="__main__":unittest.main()
