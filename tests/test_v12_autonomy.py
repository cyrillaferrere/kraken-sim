import copy
import math
import unittest
from datetime import datetime,timezone,timedelta
from v12_accounting import Portfolio
from v12_autonomy import validate,utc

def fixture():
    start=datetime(2025,1,1,tzinfo=timezone.utc)
    market={}
    for asset,offset in (("BTC",0),("ETH",40),("XRP",75)):
        bars=[]
        for i in range(325):
            close=110+offset+i*0.55
            end=(start+timedelta(days=i+1)).isoformat()
            bars.append({"end":end,"open":close-0.2,"high":close+0.7,
                         "low":close-0.7,"close":close,
                         "volume":100000,"trades":50,"imputed":False})
        market[asset]=bars
    at=market["BTC"][-1]["end"]
    quotes={asset:{"bid":round(float(bars[-1]["close"])*0.999,4),
                   "ask":round(float(bars[-1]["close"])*1.001,4),
                   "as_of":at,"min_order_usd":25}
            for asset,bars in market.items()}
    snapshot={"observed_at":at,"status":"PAPER","source":"trusted-public-kraken",
              "daily_bars":market,"quotes":quotes,"paused":False,
              "equity_peak_usd":6605.10,"cooldown_until":"1970-01-01T00:00:00Z"}
    decision={"decision_id":"example-grok-d1","cycle_id":"2025-11-22T00:00:00Z",
              "strategy_id":"kraken-sim-v1.2","strategy_version":"V1.2",
              "candidate":"C","model_id":"grok-bot-proposal","policy_version":"paper-policy-0",
              "market_data_asof":at,"created_at":at,"asset":"BTC","action":"BUY",
              "quantity":1.0,"order_type":"maker","max_slippage_pct":0.001,
              "reason":"La tendance BTC et son historique EMA confirment la strategie C",
              "confidence":0.72,"ttl_seconds":300}
    return snapshot,decision

class TestGrokPaperFirewall(unittest.TestCase):
    def test_candidate_c_valid_proposal_is_only_preflight(self):
        snapshot,decision=fixture()
        wallet=Portfolio("6605.10")
        result=validate(decision,snapshot,wallet,now=snapshot["observed_at"])
        self.assertTrue(result["accepted"],result)
        self.assertEqual(result["status"],"PREFLIGHT_ONLY_NOT_EXECUTED")
        self.assertEqual(wallet.cash,Portfolio('6605.10').cash)
        self.assertEqual(wallet.positions,{})
        self.assertLessEqual(result["max_strategy_weight"],.5)
    def test_extra_risk_override_is_refused(self):
        s,d=fixture()
        d["allow_leverage"]=True
        r=validate(d,s,Portfolio(6605.1),s["observed_at"])
        self.assertFalse(r["accepted"])
        self.assertIn("INVALID_DECISION_FIELDS",r["reason"])
    def test_candidate_does_not_allow_bypassing_donchian(self):
        s,d=fixture()
        d["candidate"]="A"
        r=validate(d,s,Portfolio(6605.1),s["observed_at"])
        self.assertFalse(r["accepted"])
        self.assertIn("A_NO_DONCHIAN_ENTRY",r["reason"])
    def test_b_weekly_rule_and_c_only_btc_eth(self):
        s,d=fixture()
        d["candidate"]="B"
        r=validate(d,s,Portfolio(6605.1),s["observed_at"])
        # Strict B rotation / universe constraint; no silent approval by model.
        if utc(s["observed_at"]).weekday()!=0:
            self.assertIn("WEEKLY_ROTATION",r["reason"])
        else:
            self.assertNotEqual(r["reason"],"V12_STRATEGY_AND_RISK_PASSED")
        d["candidate"]="C";d["asset"]="XRP"
        r=validate(d,s,Portfolio(6605.1),s["observed_at"])
        self.assertIn("C_BTC_ETH_ONLY",r["reason"])
    def test_cash_minimum_and_no_overweight(self):
        s,d=fixture()
        d["quantity"]=0.001
        r=validate(d,s,Portfolio(6605.1),s["observed_at"])
        self.assertIn("BELOW_MIN_NOTIONAL",r["reason"])
        d["quantity"]=25
        r=validate(d,s,Portfolio(6605.1),s["observed_at"])
        self.assertFalse(r["accepted"])
        self.assertIn("INSUFFICIENT_CASH",r["reason"])
        d["quantity"]=20
        r=validate(d,s,Portfolio(6605.1),s["observed_at"])
        self.assertFalse(r["accepted"])
    def test_risk_lock_kill_and_cooldown_block_buys(self):
        s,d=fixture()
        s["paused"]=True
        self.assertIn("MANUAL_PAUSE",validate(d,s,Portfolio(6605.1),s["observed_at"])["reason"])
        s["paused"]=False;s["risk_lock"]=True
        self.assertIn("RISK_LOCK",validate(d,s,Portfolio(6605.1),s["observed_at"])["reason"])
        s["risk_lock"]=False;s["equity_peak_usd"]=10000
        self.assertIn("KILL_SWITCH",validate(d,s,Portfolio(6605.1),s["observed_at"])["reason"])
    def test_stale_or_broken_public_quotes_block(self):
        s,d=fixture()
        now=s["observed_at"]
        s["quotes"]["BTC"]["as_of"]=(utc(now)-timedelta(minutes=7)).isoformat()
        self.assertIn("STALE_QUOTES",validate(d,s,Portfolio(6605.1),now)["reason"])
        s,d=fixture()
        s["quotes"]["BTC"]["ask"]=s["quotes"]["BTC"]["bid"]-1
        self.assertIn("BROKEN_BID_ASK",validate(d,s,Portfolio(6605.1),s["observed_at"])["reason"])
    def test_sell_requires_real_holding_and_hold_can_be_logged(self):
        s,d=fixture()
        d["action"]="SELL"
        self.assertIn("NO_SHORT_SELLING",validate(d,s,Portfolio(6605.1),s["observed_at"])["reason"])
        p=Portfolio("6605.10");p.buy("BTC",2,100,"0.004")
        d["quantity"]=2
        self.assertTrue(validate(d,s,p,s["observed_at"])["accepted"])
        self.assertEqual(p.positions["BTC"]["qty"],2)
        d["action"]="HOLD";d["quantity"]=0;d["order_type"]="none"
        self.assertEqual(validate(d,s,p,s["observed_at"])["reason"],"HOLD_LOGGED_NO_ORDER")
    def test_cancel_never_claims_execution(self):
        s,d=fixture()
        d["action"]="CANCEL";d["quantity"]=0;d["order_type"]="none"
        self.assertIn("CANCEL_REQUIRES_PENDING_ENGINE",validate(d,s,Portfolio(6605.1),s["observed_at"])["reason"])
    def test_expired_or_wrong_strategy_or_future_rejected(self):
        s,d=fixture()
        d["strategy_version"]="V1.3"
        self.assertIn("FOREIGN_STRATEGY",validate(d,s,Portfolio(6605.1),s["observed_at"])["reason"])
        s,d=fixture()
        now=(utc(s["observed_at"])+timedelta(seconds=301)).isoformat()
        self.assertIn("EXPIRED_DECISION",validate(d,s,Portfolio(6605.1),now)["reason"])
    def test_no_private_keys_or_live_actions_in_protocol(self):
        s,d=fixture()
        d["environment"]="LIVE"
        self.assertIn("INVALID_DECISION_FIELDS",validate(d,s,Portfolio(6605.1),s["observed_at"])["reason"])
        self.assertNotIn("api_key",s)
if __name__=="__main__":
    unittest.main()
