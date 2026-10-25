import sqlite3
import tempfile
import unittest
from pathlib import Path
from v12_learning import open_journal,append,verify,summarize

DATE="2026-10-25T12:00:00Z"
PREFLIGHT={"status":"PREFLIGHT_ONLY_NOT_EXECUTED","decision_id":"paper-d1",
           "accepted":True,"candidate":"C","reason":"V12_STRATEGY_AND_RISK_PASSED"}
OUTCOME={"decision_id":"paper-d1","horizon_days":1,
         "strategy_net_return":0.015,"cash_usdc_net_return":-0.001,"btc_net_return":0.008}
PROPOSAL={"status":"SHADOW_ONLY","candidate":"C","live_permission":False,
          "hypothesis":"Conserver la tendance sans augmenter les poids."}

class TestEvidenceAndLearning(unittest.TestCase):
    def test_append_only_idempotence_and_verification(self):
        with tempfile.TemporaryDirectory() as td:
            conn=open_journal(td)
            try:
                r1=append(conn,"decision","paper-d1",DATE,PREFLIGHT)
                self.assertFalse(r1["duplicate"])
                again=append(conn,"decision","paper-d1",DATE,PREFLIGHT)
                self.assertTrue(again["duplicate"])
                self.assertEqual(r1["record_hash"],again["record_hash"])
                out=append(conn,"outcome","outcome:paper-d1:1","2026-10-26T12:00:00Z",OUTCOME)
                self.assertFalse(out["duplicate"])
                p=append(conn,"policy_proposal","policy-v2","2026-10-26T12:00:01Z",PROPOSAL)
                self.assertFalse(p["duplicate"])
                self.assertEqual(verify(conn)["records"],3)
                stats=summarize(conn)
                self.assertEqual(stats["decisions"],1)
                self.assertEqual(stats["outcomes"],1)
                self.assertEqual(stats["policy_proposals"],1)
                self.assertEqual(stats["auto_promotions"],0)
                self.assertEqual(stats["approved"],1)
            finally:conn.close()
    def test_id_collision_never_rewrites_event(self):
        with tempfile.TemporaryDirectory() as td:
            conn=open_journal(td)
            try:
                append(conn,"decision","paper-d1",DATE,PREFLIGHT)
                changed=dict(PREFLIGHT,accepted=False)
                with self.assertRaisesRegex(ValueError,"EVIDENCE_ID_COLLISION"):
                    append(conn,"decision","paper-d1",DATE,changed)
                self.assertEqual(verify(conn)["records"],1)
            finally:conn.close()
    def test_refuse_future_outcome_and_uncommitted_source(self):
        with tempfile.TemporaryDirectory() as td:
            conn=open_journal(td)
            try:
                with self.assertRaisesRegex(ValueError,"OUTCOME_WITHOUT_COMMITTED_DECISION"):
                    append(conn,"outcome","outcome:paper-d1:1","2026-10-26T12:00:00Z",OUTCOME)
                append(conn,"decision","paper-d1",DATE,PREFLIGHT)
                with self.assertRaisesRegex(ValueError,"OUTCOME_BEFORE_EVALUATION_HORIZON"):
                    append(conn,"outcome","outcome:paper-d1:1","2026-10-25T15:00:00Z",OUTCOME)
            finally:conn.close()
    def test_no_learning_can_auto_promote_or_edit_safety(self):
        with tempfile.TemporaryDirectory() as td:
            conn=open_journal(td)
            try:
                bad=dict(PROPOSAL,live_permission=True)
                with self.assertRaisesRegex(ValueError,"POLICY_PROPOSAL_NOT_SHADOW_ONLY"):
                    append(conn,"policy_proposal","p1",DATE,bad)
                with self.assertRaisesRegex(ValueError,"AUTOMATIC_POLICY_PROMOTION_FORBIDDEN"):
                    append(conn,"policy_assessment","p1-assess",DATE,{"decision":"PROMOTE"})
                with self.assertRaisesRegex(ValueError,"INVALID_EVALUATION_HORIZON"):
                    append(conn,"outcome","outcome:paper-d1:100","2027-05-01T12:00:00Z",
                           dict(OUTCOME,horizon_days=100))
            finally:conn.close()
    def test_hash_chain_detects_local_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            conn=open_journal(td)
            try:
                append(conn,"decision","paper-d1",DATE,PREFLIGHT)
                with conn:
                    conn.execute("UPDATE evidence SET payload=? WHERE event_id=?",('{"falsified":true}',"paper-d1"))
                with self.assertRaisesRegex(ValueError,"EVIDENCE_CHAIN_BROKEN"):
                    verify(conn)
            finally:conn.close()
    def test_only_external_directory_is_acceptable(self):
        with self.assertRaises(Exception):
            open_journal(Path(__file__).resolve().parents[1]/"state")
if __name__=="__main__":
    unittest.main()
