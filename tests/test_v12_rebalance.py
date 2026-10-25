import unittest
from v12_rebalance import bounded, retained_momentum_candidates, rebalance_actions, correlation_allowed
class TestRebalance(unittest.TestCase):
    def test_sells_and_buys_and_threshold(self):
        changes=rebalance_actions({"ETH":0.45,"BTC":0.1},{"ETH":0.2,"BTC":0.3},0.05)
        self.assertEqual(changes,[("ETH","sell",0.25),("BTC","buy",0.19999999999999998)])
        self.assertEqual(rebalance_actions({"BTC":0.3},{"BTC":0.32},0.05),[])
    def test_b_retention_k_plus_two(self):
        self.assertEqual(retained_momentum_candidates(["A","B","C","D","E","F"],{"E"},4,2),["E","A","B","C"])
        self.assertEqual(retained_momentum_candidates(["A","B","C","D","E","F"],{"F"},4,2),["F","A","B","C"])
        self.assertEqual(retained_momentum_candidates(["A","B","C","D","E","F","G"],{"G"},4,2),["A","B","C","D"])
    def test_caps(self):
        weights=bounded({"A":0.5,"B":0.5,"C":0.4},cap=0.9,per_asset=0.3)
        self.assertLessEqual(sum(weights.values()),0.9000001)
        self.assertLessEqual(max(weights.values()),0.3)
    def test_correlation_missing_history_blocks_new_entry(self):
        self.assertFalse(correlation_allowed("ETH",0.2,{"BTC":0.2},{},60))
if __name__=="__main__": unittest.main()
