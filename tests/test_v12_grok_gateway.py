import copy
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path

from test_v12_autonomy import fixture,risk_fixture
from v12_accounting import Portfolio
from v12_grok_gateway import inspect_and_record as real_inspect
from v12_learning import open_journal,summarize,verify

def inspect_and_record(proposal,market,portfolio,directory,now):
    return real_inspect(proposal,market,portfolio,directory,now,
                        risk_state=risk_fixture(market),phase="admission")
class TestGrokGatewayOffline(unittest.TestCase):
    def test_good_paper_proposal_is_logged_and_never_executed(self):
        market,proposal=fixture()
        p=Portfolio("6605.10")
        with tempfile.TemporaryDirectory() as temp:
            result=inspect_and_record(proposal,market,p,temp,market["observed_at"])
            self.assertTrue(result["decision"]["accepted"],result)
            self.assertFalse(result["paper_order_executed"])
            self.assertFalse(result["live_order_executed"])
            self.assertFalse(result["model_invoked"])
            self.assertEqual(p.cash,Portfolio("6605.10").cash)
            self.assertFalse(p.positions)
            self.assertTrue((Path(temp)/"grok_paper_evidence_v12.db").exists())
            again=inspect_and_record(proposal,market,p,temp,market["observed_at"])
            self.assertTrue(again["evidence"]["duplicate"])
            db=open_journal(temp)
            try:
                self.assertEqual(summarize(db)["approved"],1)
                self.assertEqual(verify(db)["records"],1)
            finally:db.close()
    def test_invalid_agent_proposal_is_rejected_and_traceable(self):
        market,proposal=fixture()
        proposal["strategy_version"]="FAKE"
        with tempfile.TemporaryDirectory() as temp:
            r=inspect_and_record(proposal,market,Portfolio(6605.1),temp,market["observed_at"])
            self.assertFalse(r["decision"]["accepted"])
            self.assertEqual(r["decision"]["reason"],"FOREIGN_STRATEGY")
            db=open_journal(temp)
            try:self.assertEqual(summarize(db)["rejected"],1)
            finally:db.close()
    def test_absent_provider_cannot_trade(self):
        market,_=fixture()
        with tempfile.TemporaryDirectory() as temp:
            r=inspect_and_record(None,market,Portfolio(6605.1),temp,market["observed_at"])
            self.assertEqual(r["decision"]["reason"],"GROK_UNAVAILABLE_NO_TRADE")
            self.assertFalse(r["paper_order_executed"])
            self.assertFalse(r["live_order_executed"])
    def test_reused_id_different_proposal_detected(self):
        market,proposal=fixture()
        with tempfile.TemporaryDirectory() as temp:
            inspect_and_record(proposal,market,Portfolio(6605.1),temp,market["observed_at"])
            changed=dict(proposal,reason="Je change les raisons de cette decision apres coup")
            with self.assertRaisesRegex(ValueError,"EVIDENCE_ID_COLLISION"):
                inspect_and_record(changed,market,Portfolio(6605.1),temp,market["observed_at"])
    def test_production_repository_target_denied(self):
        market,proposal=fixture()
        target=Path(__file__).resolve().parents[1]/"state"
        with self.assertRaises(Exception):
            inspect_and_record(proposal,market,Portfolio(6605.1),target,market["observed_at"])
if __name__=="__main__":unittest.main()
