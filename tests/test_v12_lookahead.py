from datetime import datetime
import unittest
def closed_before(candle_end,decision):
    e=datetime.fromisoformat(candle_end.replace("Z","+00:00"))
    d=datetime.fromisoformat(decision.replace("Z","+00:00"))
    if e.tzinfo is None or d.tzinfo is None or e>d: raise ValueError("open/future candle")
    return True
class TestLookahead(unittest.TestCase):
    def test_open_candle_rejected(self):
        with self.assertRaises(ValueError): closed_before("2026-10-26T00:00:00Z","2026-10-25T23:59:00Z")
        self.assertTrue(closed_before("2026-10-25T00:00:00Z","2026-10-25T01:10:00Z"))
    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError): closed_before("2026-10-25T00:00:00","2026-10-25T01:10:00Z")
if __name__=="__main__": unittest.main()
