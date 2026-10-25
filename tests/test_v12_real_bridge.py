import json
import tempfile
import unittest
import urllib.parse
from datetime import datetime,timedelta,timezone

from v12_grok_issues import InboxError,parse_decision_issue,fetch_latest
from v12_kraken_public import KrakenMarketError,collect,overview,daily_bars,call
from v12_live_bridge import paper_step,fetch_and_step
from v12_grok_issues import InboxError
from unittest.mock import patch
from v12_paper_engine import PaperEngine
from v12_synthetic_30d import start_market,market_at,proposal
from v12_autonomy import utc

USER_ID=1371

def issue(batch,user=USER_ID):
    return {"number":44,"state":"open","title":"IT V1.2 2025-11-22",
            "labels":[{"name":"it-decision"}],
            "user":{"id":user,"login":"trusted-user"},"body":json.dumps(batch)}

class TestPublicBridge(unittest.TestCase):
    def test_offline_api_stubs_extract_closed_daily_candles_and_spot_prices(self):
        current=datetime.now(timezone.utc)
        base=int((current-timedelta(days=4)).timestamp())//86400*86400
        def bar(ts,cl):
            return [ts,str(cl),str(cl+2),str(cl-2),str(cl),"0", "100000",5]
        pairs={"XBTUSDC":{"wsname":"XBT/USDC","status":"online","costmin":"5"},
               "ETHUSDC":{"wsname":"ETH/USDC","status":"online","costmin":"5"},
               "XXBTZUSD":{"wsname":"XBT/USD","status":"online","costmin":"5"},
               "USDTUSDC":{"wsname":"USDT/USDC","status":"online","costmin":"5"}}
        tickers={k:{"b":[str(price*.999)],"a":[str(price*1.001)],
                    "c":[str(price)],"v":["1","10000"]}
                 for k,price in (("XBTUSDC",300),("ETHUSDC",200),("XXBTZUSD",300),("USDTUSDC",1))}
        requests=[]
        def opener(request):
            url=request.full_url
            requests.append(url)
            endpoint=url.split("?")[0].split("/")[-1]
            params=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            if endpoint=="AssetPairs":return json.dumps({"error":[],"result":pairs}).encode()
            if endpoint=="Ticker":return json.dumps({"error":[],"result":tickers}).encode()
            if endpoint=="OHLC":
                key=params["pair"][0]
                return json.dumps({"error":[],"result":{key:[
                    bar(base,300),bar(base+86400,301),
                    bar(int(current.timestamp())//86400*86400,999),
                ],"last":0}}).encode()
            raise AssertionError("FORBIDDEN_PATH")
        snapshot=collect(max_pairs=2,opener=opener)
        self.assertEqual(snapshot["data_origin"],"KRAKEN_PUBLIC_API")
        # 2 closed USDC bars only: insufficient_history, bars null (never imputed)
        self.assertEqual(snapshot["daily_bars"],{})
        c=snapshot["compliance"]
        self.assertEqual(c["eligible"],["BTC","ETH"])
        self.assertEqual(c["insufficient_history"],["BTC","ETH"])
        self.assertEqual(c["history"]["BTC"]["closed_bars"],2)
        self.assertIsNone(c["history"]["BTC"]["bars"])
        self.assertFalse(c["btc_regime_history"]["sufficient"])
        self.assertEqual(c["rejected"]["USDT"],"STABLECOIN_OR_FIAT_EXCLUDED")
        self.assertTrue(all(q["pair"].endswith("/USDC") for q in snapshot["quotes"].values()))
        self.assertTrue(any("country_code=FR" in u for u in requests if "AssetPairs" in u))
        self.assertTrue(all("XXBTZUSD" not in u for u in requests if "OHLC" in u))
        self.assertEqual(overview(snapshot)["orders_sent"],0) if "orders_sent" in overview(snapshot) else None
        self.assertTrue(all("/0/public/" in url for url in requests))
    def test_no_private_or_dangerous_endpoint(self):
        with self.assertRaises(KrakenMarketError):
            call("AddOrder")
    def test_author_id_label_and_synthesis_are_required(self):
        batch={"it_id":"x","synthesis_sha256":"a"*64,"decisions":[]}
        good=issue(batch)
        self.assertEqual(parse_decision_issue(good,USER_ID)["issue_number"],44)
        with self.assertRaises(InboxError):
            parse_decision_issue(issue(batch,user=99),USER_ID)
        broken=issue(batch);broken["labels"]=[]
        with self.assertRaises(InboxError):
            parse_decision_issue(broken,USER_ID)
        altered=issue(dict(batch,synthesis_sha256="not-a-hash"))
        with self.assertRaises(InboxError):
            parse_decision_issue(altered,USER_ID)
    def test_github_reader_is_read_only_and_filters_impostors(self):
        batch={"it_id":"x","synthesis_sha256":"a"*64,"decisions":[]}
        imposter=issue(batch,user=100);imposter["number"]=45
        def opener(request):
            self.assertEqual(request.get_method(),"GET")
            self.assertIn("Bearer read-only-test",dict(request.header_items()).get("Authorization"))
            return json.dumps([imposter,issue(batch)]).encode()
        got=fetch_latest(USER_ID,"read-only-test",opener=opener)
        self.assertEqual(got["issue_number"],44)
        with self.assertRaises(InboxError):fetch_latest(USER_ID,None,opener=opener)
    def test_full_bridge_safeguards_run_if_github_is_down(self):
        seed=start_market()
        m=market_at(seed,0);m["data_origin"]="KRAKEN_PUBLIC_API"
        with tempfile.TemporaryDirectory() as td:
            engine=PaperEngine(td)
            try:
                with patch("v12_live_bridge.collect",return_value=m),patch(
                    "v12_grok_issues.fetch_recent",side_effect=InboxError("timeout")):
                    response=fetch_and_step(engine,USER_ID,"fake-public-read-token",max_pairs=2)
                self.assertEqual(response["tick"]["status"],"DRY_RUN")
                self.assertEqual(response["it_status"],"GITHUB_UNAVAILABLE_NO_NEW_DECISIONS")
                self.assertEqual(response["live_orders"],0)
                self.assertEqual(engine.report()["marks"],1)
            finally:engine.close()
    def test_full_bridge_mismatched_hash_rejects_new_orders(self):
        seed=start_market()
        m=market_at(seed,0);m["data_origin"]="KRAKEN_PUBLIC_API"
        batch={"it_id":"x","synthesis_sha256":"a"*64,"decisions":[]}
        verified=parse_decision_issue(issue(batch),USER_ID)
        with tempfile.TemporaryDirectory() as td:
            engine=PaperEngine(td)
            try:
                with patch("v12_live_bridge.collect",return_value=m),patch(
                    "v12_grok_issues.fetch_recent",return_value=[verified]):
                    result=fetch_and_step(engine,USER_ID,"fake-public-read-token",max_pairs=2)
                self.assertEqual(result["it_status"],"GROK_ITS_PARTIALLY_REJECTED")
                self.assertEqual(result["it_decisions"],[])
                self.assertFalse(engine.wallet().positions)
                self.assertEqual(engine.report()["marks"],1)
            finally:engine.close()
    def test_many_grok_its_are_processed_not_only_latest(self):
        seed=start_market()
        m=market_at(seed,0);m["data_origin"]="KRAKEN_PUBLIC_API"
        with tempfile.TemporaryDirectory() as td:
            engine=PaperEngine(td)
            try:
                prepared=paper_step(engine,m,m["observed_at"])
                sha=prepared["synthesis"]["synthesis_sha256"]
                batches=[]
                for i in range(12):
                    decision=proposal(m,"it-multi-%02d"%i,"BTC",0.10)
                    decision["created_at"]=m["observed_at"]
                    batch={"it_id":"IT-%02d"%i,"synthesis_sha256":sha,
                           "decisions":[decision]}
                    item=parse_decision_issue(issue(batch),USER_ID)
                    item["issue_number"]=100+i
                    batches.append(item)
                with patch("v12_live_bridge.collect",return_value=m),patch(
                    "v12_grok_issues.fetch_recent",return_value=batches):
                    result=fetch_and_step(engine,USER_ID,"fake-public-read-token",max_pairs=2)
                self.assertEqual(result["it_status"],"GROK_ITS_PROCESSED")
                self.assertEqual(len(result["it_issue_numbers"]),12)
                self.assertEqual(len(result["it_decisions"]),12)
                self.assertFalse(engine.wallet().positions)
                self.assertEqual(result["live_orders"],0)
            finally:engine.close()
    def test_offline_bridge_real_origin_requires_engine_and_bound_synthesis(self):
        seed=start_market()
        m=market_at(seed,0)
        m["data_origin"]="KRAKEN_PUBLIC_API"  # Stub represents collector output, not live fetch.
        with tempfile.TemporaryDirectory() as td:
            engine=PaperEngine(td)
            try:
                first=paper_step(engine,m,m["observed_at"])
                self.assertEqual(first["tick"]["status"],"DRY_RUN")
                self.assertIsNotNone(first["synthesis"])
                decision=proposal(m,"bridge-test-BTC","BTC",1)
                # admission at same UTC second: a fixture decision may not refer to future time
                decision["created_at"]=m["observed_at"]
                batch={"it_id":"it-synthetic","synthesis_sha256":first["synthesis"]["synthesis_sha256"],
                       "decisions":[decision]}
                untrusted=issue(dict(batch,synthesis_sha256="0"*64))
                parsed=parse_decision_issue(untrusted,USER_ID)
                with self.assertRaisesRegex(ValueError,"UNKNOWN_SYNTHESIS_SHA256"):
                    paper_step(engine,m,m["observed_at"],parsed)
                parsed=parse_decision_issue(issue(batch),USER_ID)
                output=paper_step(engine,m,m["observed_at"],parsed)
                self.assertEqual(len(output["it_decisions"]),1)
                self.assertTrue(output["it_decisions"][0]["accepted"],output)
                self.assertEqual(output["live_orders"],0)
                self.assertFalse(engine.wallet().positions)
            finally:engine.close()
if __name__=="__main__":
    unittest.main()
