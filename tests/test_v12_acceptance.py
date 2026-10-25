import copy
import unittest
from v12_acceptance import reject_candidate, choose_candidate

GOOD={
    "evaluation_status":"VALIDATED_WALK_FORWARD",
    "net_oos_f2":0.2,
    "net_oos_f1":0.3,
    "v11_net_oos_f2":-0.03,
    "max_drawdown_oos_f2":-0.23,
    "fold_returns_oos_f2":[0.08,0.04,0.03,-0.01],
    "fees_spread_slippage_usd_f2":200,
    "gross_profit_usd_f2":1000,
    "neighbors_oos_f2":[0.08,0.11],
    "closed_roundtrips_oos":36,
    "calmar_oos_f2":0.9,
    "sortino_oos_f2":1.2,
}
class TestAccept(unittest.TestCase):
    def test_exploratory_never_passes(self):
        d=dict(GOOD,evaluation_status="EXPERIMENTAL_NOT_OOS_VALIDATED")
        self.assertTrue(reject_candidate(d)[0])
        self.assertIsNone(choose_candidate({"A":d}))
    def test_complete_good_candidate_can_pass(self):
        self.assertEqual(reject_candidate(GOOD),(False,[]))
    def test_each_rejection_criterion(self):
        values=[
            ("net_oos_f2",0),("v11_net_oos_f2",0.4),
            ("max_drawdown_oos_f2",-0.36),
            ("fold_returns_oos_f2",[0.04,-0.02]),
            ("fees_spread_slippage_usd_f2",500),
            ("gross_profit_usd_f2",0),
            ("neighbors_oos_f2",[0.01,-0.02]),
            ("closed_roundtrips_oos",29),
            ("net_oos_f1",0)
        ]
        for k,value in values:
            with self.subTest(k=k,value=value):
                x=dict(GOOD,**{k:value})
                self.assertTrue(reject_candidate(x)[0])
    def test_null_or_missing_never_passes(self):
        for k in GOOD:
            with self.subTest(k=k):
                x=dict(GOOD)
                x[k]=None
                self.assertTrue(reject_candidate(x)[0])
                x.pop(k)
                self.assertTrue(reject_candidate(x)[0])
    def test_choose_only_survivors_by_calmar_then_sortino(self):
        a=dict(GOOD,calmar_oos_f2=0.9,sortino_oos_f2=0.8)
        b=dict(GOOD,calmar_oos_f2=0.9,sortino_oos_f2=1.5)
        bad=dict(GOOD,calmar_oos_f2=99,net_oos_f2=-0.01)
        self.assertEqual(choose_candidate({"A":a,"B":b,"C":bad}),"B")
        self.assertIsNone(choose_candidate({"A":bad}))
if __name__=="__main__":
    unittest.main()
