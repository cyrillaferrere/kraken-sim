import json
import tempfile
import unittest
import urllib.parse
from datetime import datetime,timedelta,timezone

from v12_grok_issues import InboxError,parse_decision_issue,fetch_latest
from v12_kraken_public import KrakenMarketError,collect,overview,daily_bars,call
from v12_live_bridge import paper_step
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
        pairs={"XXBTZUSD":{"wsname":"XBT/USD","status":"online","costmin":"5"},
               "XETHZUSD":{"wsname":"ETH/USD","status":"online","costmin":"5"},
               "USDCUSD":{"wsname":"USDC/USD","status":"online","costmin":"5"}}
        tickers={k:{"b":[str(price*.999)],"a":[str(price*1.001)],
                    "c":[str(price)],"v":["1","10000"]}
                 for k,price in (("XXBTZUSD",300),("XETHZUSD",200),("USDCUSD",1))}
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
        self.assertEqual(set(snapshot["daily_bars"]),{"BTC","ETH"})
        self.assertNotIn("USDC",snapshot["daily_bars"])
        self.assertEqual(len(snapshot["daily_bars"]["BTC"]),2)
        self.assertNotIn("999",str(snapshot["daily_bars"]["BTC"]))
        self.assertEqual(snapshot["usdc_usd"]["bid"],"0.999")
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
