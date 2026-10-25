#!/usr/bin/env python3
"""V1.2 PAPER dry-run engine. No network, API key, deployment or live order route.

Trusted market snapshots and Grok decisions are injected by an offline caller.
Production orchestration, provider authentication, Kraken collector and scheduler
are NOT wired. SQLite state (including risk and position peak) is engine-owned,
outside the repository. For replay/CI only until approved by Cyril.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path

from v12_accounting import Portfolio,d
from v12_autonomy import SPEC,utc,validate,min_median_volume_usdc
from v12_execution import passive_crossing_qty,taker_estimate
from v12_isolation import state_dir
from v12_learning import canonical,append,open_journal
from v12_usdc_baseline import initial_units,usd_value,checked_rate

ZERO_TIME="1970-01-01T00:00:00+00:00"
TERMINAL=frozenset(("FILLED","REJECTED","EXPIRED","CANCELLED","RISK_CANCELLED"))
ACTIVE=frozenset(("ADMITTED","MAKER_PENDING"))
MODEL="grok-bot-proposal"  # Fixture identity; real provider authentication NOT implemented.
POLICY="paper-policy-0"

def digest(doc):
    return hashlib.sha256(canonical(doc).encode("utf8")).hexdigest()

def _money(value):
    return str(d(value))

class PaperEngine:
    def __init__(self,root,c0="6605.10",quote_currency="USD"):
        self.root=state_dir(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(self.root/"paper_engine_v12.db",timeout=30,
                                  isolation_level=None)
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.executescript("""
          CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY,v TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS syntheses(
            digest TEXT PRIMARY KEY, asof TEXT NOT NULL,
            summary_json TEXT NOT NULL,market_json TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS orders(
            decision_id TEXT PRIMARY KEY, original_json TEXT NOT NULL,
            synthesis_hash TEXT NOT NULL, submitted_at TEXT NOT NULL,
            expires_at TEXT NOT NULL, status TEXT NOT NULL,
            remaining TEXT NOT NULL,limit_price TEXT,
            placed_at TEXT,reason TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS fills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT NOT NULL,asset TEXT NOT NULL,side TEXT NOT NULL,
            qty TEXT NOT NULL,price TEXT NOT NULL,fee TEXT NOT NULL,
            liquidity TEXT NOT NULL,ts TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS marks(
            ts TEXT PRIMARY KEY,equity TEXT NOT NULL,fees TEXT NOT NULL,
            usdc_hold_usd TEXT,btc_hold_usd TEXT);
          CREATE TABLE IF NOT EXISTS position_rules(
            asset TEXT PRIMARY KEY,candidate TEXT NOT NULL,
            entry_price TEXT NOT NULL,high_close TEXT NOT NULL,
            entered_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS cycles(
            slot TEXT PRIMARY KEY,ts TEXT NOT NULL,status TEXT NOT NULL,
            note TEXT NOT NULL);
        """)
        if self._get("wallet") is None:
            with self.transaction():
                if self._get("wallet") is None:
                    p=Portfolio(c0)
                    self._put("wallet",self._wallet_json(p))
                    self._put("equity_peak_usd",_money(c0))
                    self._put("initial_capital_usd",_money(c0))
                    self._put("risk_lock",False)
                    self._put("paused",False)
                    self._put("cooldown_until",ZERO_TIME)
                    self._put("active_policy_version",POLICY)
                    self._put("authorized_model_id",MODEL)
                    self._put("kill_count",0)
                    self._put("quote_currency",quote_currency)
        # Legacy wallets created before Moteur V1.6 have no key: they are USD.
        self.quote_currency=self._get("quote_currency") or "USD"

    @contextmanager
    def transaction(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def _get(self,key):
        row=self.conn.execute("SELECT v FROM kv WHERE k=?",(key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _put(self,key,value):
        self.conn.execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                          (key,canonical(value)))

    @staticmethod
    def _wallet_json(p):
        return {"cash":str(p.cash),"fees_paid":str(p.fees_paid),
                "realized_pnl":str(p.realized_pnl),
                "positions":{a:{"qty":str(row["qty"]),"avg_cost":str(row["avg_cost"])}
                             for a,row in p.positions.items()}}

    def wallet(self):
        o=self._get("wallet")
        p=Portfolio(o["cash"])
        p.fees_paid=d(o["fees_paid"]);p.realized_pnl=d(o["realized_pnl"])
        p.positions={a:{"qty":d(row["qty"]),"avg_cost":d(row["avg_cost"])}
                     for a,row in o["positions"].items()}
        return p

    def _risk(self,snapshot=None,exclude=None):
        """ALL persisted control state is engine-owned, NOT in market snapshot."""
        out={"engine_controlled":True,
             "active_policy_version":self._get("active_policy_version"),
             "authorized_model_id":self._get("authorized_model_id"),
             "paused":self._get("paused"),"risk_lock":self._get("risk_lock"),
             "cooldown_until":self._get("cooldown_until"),
             "equity_peak_usd":self._get("equity_peak_usd")}
        sells={};reserved=d(0)
        if snapshot is not None:
            for row in self.conn.execute(
                "SELECT decision_id,original_json,remaining FROM orders WHERE status IN ('ADMITTED','MAKER_PENDING')"):
                identity,original,remaining=row
                if identity==exclude: continue
                act=json.loads(original)
                qty=d(remaining)
                if act["action"]=="SELL":
                    sells[act["asset"]]=sells.get(act["asset"],d(0))+qty
                elif act["action"]=="BUY":
                    quote=snapshot.get("quotes",{}).get(act["asset"])
                    if not quote:
                        # A missing quote never releases reserved budget.
                        reserved=d(self._get("initial_capital_usd"))*10
                    else:
                        reserved+=qty*d(quote["ask"])*d("1.02")
        out["reserved_sell_quantities"]={a:str(q) for a,q in sells.items()}
        out["reserved_buy_usd"]=str(reserved)
        out["pending_exposure_usd"]=str(reserved)
        return out

    # Per-pair exclusion policy (moteur V1.4): an invalid / too-wide quote
    # excludes ONLY that pair for the tick. Global pause only when BTC or ETH
    # are invalid, or when fewer than min_valid_pairs() remain usable.
    MAX_SPREAD=d("0.003")
    MANDATORY=("BTC","ETH")
    MIN_VALID_PAIRS_CAP=10

    @classmethod
    def min_valid_pairs(cls,quoted):
        """N = max(2, min(10, ceil(quoted/2))): 10 for the 40-pair universe."""
        return max(2,min(cls.MIN_VALID_PAIRS_CAP,(quoted+1)//2))

    def _market_quotes(self,snapshot,now,holdings):
        if snapshot.get("status")!="PAPER" or snapshot.get("source")!="trusted-public-kraken":
            raise ValueError("MARKET_SNAPSHOT_NOT_TRUSTED")
        quotes=snapshot.get("quotes",{})
        for a in holdings:
            if a not in quotes:raise ValueError("HELD_ASSET_MISSING_QUOTE")
        out={};excluded={};held_marks={}
        for asset,q in quotes.items():
            reason=None
            try:
                moment=utc(q["as_of"])
                bid,ask=d(q["bid"]),d(q["ask"])
                if now-moment>timedelta(minutes=5) or moment>now:
                    reason="QUOTE_NOT_FRESH_FOR_EXECUTION"
                elif bid<=0 or ask<bid:
                    reason="QUOTE_INVALID_FOR_EXECUTION"
                elif (ask-bid)/((ask+bid)/2)>self.MAX_SPREAD:
                    reason="SPREAD_TOO_WIDE"
            except (ValueError,TypeError,KeyError,ArithmeticError):
                reason="QUOTE_INVALID_FOR_EXECUTION";bid=d(0)
            if reason is None:
                out[asset]={"bid":bid,"ask":ask};continue
            if asset in self.MANDATORY:
                raise ValueError(reason if reason!="SPREAD_TOO_WIDE" else "QUOTE_INVALID_FOR_EXECUTION")
            info={"reason":reason}
            try:info["spread"]=str(((d(q["ask"])-d(q["bid"]))/((d(q["ask"])+d(q["bid"]))/2)).quantize(d("0.00001")))
            except Exception:pass
            if asset in holdings:
                # Held position kept under protection; valued at its last bid if positive.
                info["held"]=True
                if bid>0:held_marks[asset]=bid
            excluded[asset]=info
        need=self.min_valid_pairs(len(quotes))
        if len(out)<need:
            raise ValueError("TOO_FEW_VALID_PAIRS_%d_OF_%d"%(len(out),need))
        self.last_exclusions=excluded
        self.last_held_marks=held_marks
        return out

    def _marks(self,quotes,holdings):
        prices={a:q["bid"] for a,q in quotes.items()}
        for a in holdings:
            if a not in prices:
                if a not in getattr(self,"last_held_marks",{}):
                    raise ValueError("HELD_ASSET_UNVALUED")
                prices[a]=self.last_held_marks[a]
        return prices

    def _fee(self,liquidity):
        return d(SPEC["COSTS"]["F2"][liquidity])

    def _slip(self,asset,forced=False):
        group="major" if asset in ("BTC","ETH") else "other"
        base=d(SPEC["COSTS"]["slippage"][group])
        return base*d(SPEC["COSTS"]["forced_multiplier"] if forced else 1)

    def _fill(self,portfolio,identity,asset,side,qty,px,liquidity,now):
        fee=self._fee(liquidity)
        if side=="BUY":
            original=self.conn.execute("SELECT original_json FROM orders WHERE decision_id=?",(identity,)).fetchone()
            if not original:raise ValueError("BUY_MUST_ORIGINATE_FROM_ADMITTED_DECISION")
            candidate=json.loads(original[0])["candidate"]
            existing=self.conn.execute("SELECT candidate FROM position_rules WHERE asset=?",(asset,)).fetchone()
            if existing and existing[0]!=candidate:
                raise ValueError("CROSS_STRATEGY_POSITION_NOT_PERMITTED")
            paid=portfolio.buy(asset,qty,px,fee)
            if not existing:
                self.conn.execute("""INSERT INTO position_rules
                    (asset,candidate,entry_price,high_close,entered_at) VALUES(?,?,?,?,?)""",
                    (asset,candidate,str(px),str(px),now.isoformat()))
        else:
            portfolio.sell(asset,qty,px,fee)
            paid=d(qty)*d(px)*fee
            if asset not in portfolio.positions:
                self.conn.execute("DELETE FROM position_rules WHERE asset=?",(asset,))
        self.conn.execute("""INSERT INTO fills(decision_id,asset,side,qty,price,fee,liquidity,ts)
                             VALUES(?,?,?,?,?,?,?,?)""",
                          (identity,asset,side,_money(qty),_money(px),_money(paid),
                           liquidity,now.isoformat()))
        return paid

    def _liquidity_gate(self,asset,side,qty,forced):
        """Moteur V1.6.2 : contrôle Depth avant chaque ordre PAPER taker.
        Snapshot sans clé 'books' (fixtures hors ligne antérieures) : non contrôlé.
        Sorties de sécurité (forced) jamais bloquées par un carnet mince."""
        books=getattr(self,"current_books",None)
        if books is None or forced:return
        from v12_liquidity import book_from_snapshot,check_order,record
        result=check_order(book_from_snapshot(books.get(asset)),side,qty)
        self._put("liquidity_metrics",record(self._get("liquidity_metrics"),result))
        if not result["accepted"]:
            raise ValueError(result["reason"])

    def liquidity_metrics(self):
        from v12_liquidity import empty_metrics
        return self._get("liquidity_metrics") or empty_metrics()

    def _execute_taker(self,portfolio,identity,asset,side,qty,quotes,now,forced=False):
        q=quotes[asset]
        self._liquidity_gate(asset,side,qty,forced)
        estimate=taker_estimate(side.lower(),qty,q["bid"],q["ask"],
                                self._fee("taker"),self._slip(asset,forced))
        self._fill(portfolio,identity,asset,side,qty,estimate["price"],"taker",now)

    def build_synthesis(self,snapshot,now):
        """Compact public-only Grok input; server stores the full trusted market.
        The synthesis hash binds every decision to a single immutable snapshot.
        """
        t=utc(now) if isinstance(now,str) else now.astimezone(timezone.utc)
        if utc(snapshot["observed_at"])!=t:
            raise ValueError("SYNTHESIS_SNAPSHOT_TIMESTAMP_MISMATCH")
        p=self.wallet()
        quotes=self._market_quotes(snapshot,t,p.positions)
        excluded=dict(self.last_exclusions)
        equity=p.equity(self._marks(quotes,p.positions))
        from v12_signals import (
            candidate_a,candidate_b,candidate_c,candidate_d,
            closed_candles,point_in_time_universe)
        bars=snapshot.get("daily_bars",{})
        closed={asset:closed_candles(raw,t.isoformat()) for asset,raw in bars.items()}
        btc=closed.get("BTC",[])
        if not btc:raise ValueError("SYNTHESIS_BTC_HISTORY_REQUIRED")
        signals={"A":[],"B":[],"C":[],"D":[]}
        universe=point_in_time_universe(
            closed,t.isoformat(),
            min_history=int(SPEC["UNIVERSE"]["min_history_daily"]),
            min_daily_volume=min_median_volume_usdc(),
            max_assets=int(SPEC["UNIVERSE"]["max_assets"]))
        for asset in ("BTC","ETH"):
            arr=closed.get(asset,[])
            if len(arr)>=220:
                sig=candidate_c(arr,SPEC["CANDIDATES"]["C"])
                signals["C"].append({"asset":asset,"entry":bool(sig["entry"]),
                    "exit":bool(sig["exit"]),"max_weight":round(float(sig["target_weight"]),4)})
        for asset,series in [(a,v) for a,v in universe.items() if a in quotes][:20]:
            a=candidate_a(series,btc,SPEC["CANDIDATES"]["A"])
            b=candidate_b(series,btc,SPEC["CANDIDATES"]["B"])
            dd=candidate_d(series,btc,SPEC["CANDIDATES"]["D"])
            signals["A"].append({"asset":asset,"entry":bool(a.get("entry")),
                                  "exit":bool(a.get("exit")),
                                  "max_weight":round(float(a.get("target_weight",0)),4)})
            signals["B"].append({"asset":asset,"eligible":bool(b.get("eligible")),
                                  "momentum":round(float(b.get("score",0)),6)})
            signals["D"].append({"asset":asset,"entry":bool(dd.get("entry")),
                                  "exit":bool(dd.get("exit")),
                                  "momentum":round(float(dd.get("score",0)),6)})
        summary={"asof":t.isoformat(),"engine":"V1.2 PAPER OFFLINE FIXTURE",
                 "active_policy_version":self._get("active_policy_version"),
                 "strategy":"V1.2","candidates":["A","B","C","D"],
                 "quotes":{a:{"bid":str(v["bid"]),"ask":str(v["ask"])}
                           for a,v in list(quotes.items())[:20]},
                 "signals":signals,
                 "excluded_pairs":{a:v["reason"] for a,v in list(excluded.items())[:40]},
                 "positions":{a:{"qty":str(v["qty"]),"avg_cost":str(v["avg_cost"])}
                              for a,v in p.positions.items()},
                 "equity_usd":str(equity),
                 "risk":{"peak_usd":self._get("equity_peak_usd"),"locked":self._get("risk_lock"),
                         "paused":self._get("paused")},
                 "usdc_quote":snapshot.get("usdc_usd"),
                 "pending_count":self.conn.execute(
                       "SELECT COUNT(*) FROM orders WHERE status IN ('ADMITTED','MAKER_PENDING')").fetchone()[0]}
        if len(canonical(summary).encode("utf8"))>8192:
            raise ValueError("SYNTHESIS_OVER_8K")
        sha=digest(summary)
        with self.transaction():
            self.conn.execute("""INSERT OR IGNORE INTO syntheses(digest,asof,summary_json,market_json)
                                 VALUES(?,?,?,?)""",(sha,t.isoformat(),canonical(summary),canonical(snapshot)))
        return {"synthesis":summary,"synthesis_sha256":sha}

    def admit_batch(self,batch,now):
        """Only recognized synthesis hash is accepted, and decisions cannot set risk."""
        moment=utc(now) if isinstance(now,str) else now.astimezone(timezone.utc)
        if not isinstance(batch,dict) or set(batch)!={"it_id","synthesis_sha256","decisions"}:
            raise ValueError("INVALID_IT_BATCH")
        if not isinstance(batch["it_id"],str) or len(batch["it_id"])>120:
            raise ValueError("INVALID_IT_ID")
        decisions=batch["decisions"]
        if not isinstance(decisions,list) or len(decisions)>20:
            raise ValueError("INVALID_IT_DECISIONS")
        row=self.conn.execute("SELECT market_json FROM syntheses WHERE digest=?",
                              (batch["synthesis_sha256"],)).fetchone()
        if not row:raise ValueError("UNKNOWN_SYNTHESIS_SHA256")
        snapshot=json.loads(row[0])
        p=self.wallet()
        result=[]
        from v12_grok_gateway import inspect_and_record
        for decision in decisions:
            if not isinstance(decision,dict):
                raise ValueError("INVALID_DECISION_TYPE")
            identity=decision.get("decision_id")
            original=canonical(decision)
            old=self.conn.execute("SELECT original_json,status FROM orders WHERE decision_id=?",
                                  (identity,)).fetchone()
            if old:
                if old[0]!=original:
                    raise ValueError("DECISION_ID_REUSED_WITH_CHANGED_CONTENT")
                result.append({"decision_id":identity,"accepted":True,"status":old[1],"duplicate":True})
                continue
            if decision.get("market_data_asof")!=snapshot["observed_at"]:
                raise ValueError("DECISION_SYNTHESIS_MISMATCH")
            from v12_compliance import check_decision,ComplianceError
            try:check_decision(decision,snapshot,p.positions)
            except ComplianceError as exc:
                # Garde-fou UE/MiCA moteur : rejet, jamais d'ordre (indépendant de Grok).
                result.append({"decision_id":identity,"accepted":False,"reason":str(exc),
                               "status":"REJECTED_COMPLIANCE"})
                continue
            risk=self._risk(snapshot)
            record=inspect_and_record(decision,snapshot,p,str(self.root),moment,
                                      risk_state=risk,phase="admission")
            verdict=record["decision"]
            result.append(verdict)
            if verdict["accepted"] and decision["action"] in ("BUY","SELL"):
                created=utc(decision["created_at"])
                expires=created+timedelta(seconds=decision["ttl_seconds"])
                with self.transaction():
                    self.conn.execute("""INSERT INTO orders
                        (decision_id,original_json,synthesis_hash,submitted_at,expires_at,
                         status,remaining,reason) VALUES(?,?,?,?,?,?,?,?)""",
                        (identity,original,batch["synthesis_sha256"],moment.isoformat(),
                         expires.isoformat(),"ADMITTED",_money(decision["quantity"]),verdict["reason"]))
        return result

    def _protect_positions(self,p,quotes,snapshot,now,slot):
        """Deterministic A/B/C/D exits keep working when Grok skips an IT.
        These are daily CLOSE-based protection signals, not guaranteed stop fills.
        """
        from v12_signals import closed_candles,candidate_a,candidate_b,candidate_c,candidate_d
        from v12_indicators import atr
        bars=snapshot.get("daily_bars")
        if not isinstance(bars,dict) or "BTC" not in bars:
            return [{"action":"PROTECTIVE_SIGNALS_UNAVAILABLE"}]
        btc=closed_candles(bars["BTC"],now.isoformat())
        events=[]
        for asset in list(p.positions):
            rule=self.conn.execute("""SELECT candidate,entry_price,high_close
                FROM position_rules WHERE asset=?""",(asset,)).fetchone()
            if rule is None:
                # Never silently assume a strategy for a position.
                events.append({"action":"UNATTRIBUTED_POSITION_REQUIRES_REVIEW","asset":asset})
                continue
            if asset not in bars or asset not in quotes or not btc:
                events.append({"action":"PROTECTIVE_SIGNALS_UNAVAILABLE","asset":asset})
                continue
            asset_bars=closed_candles(bars[asset],now.isoformat())
            if not asset_bars or now-utc(asset_bars[-1]["end"])>timedelta(hours=26):
                events.append({"action":"PROTECTIVE_SIGNALS_STALE","asset":asset})
                continue
            label,entry,high=rule
            last=d(asset_bars[-1]["close"])
            high=max(d(high),last)
            self.conn.execute("UPDATE position_rules SET high_close=? WHERE asset=?",(str(high),asset))
            params=SPEC["CANDIDATES"][label]
            trigger=None
            if label=="A":
                signal=candidate_a(asset_bars,btc,params,highest_close_since_entry=float(high))
                if signal.get("exit"):trigger="DONCHIAN_ATR_EXIT"
            elif label=="B":
                signal=candidate_b(btc,btc,params)
                if signal.get("btc_momentum") is not None and signal["btc_momentum"]<=0:
                    trigger="BTC_RISK_OFF"
                elif len(asset_bars)>=21 and last<d(entry)-d(params["stop_atr_mult"])*d(atr(asset_bars,20)):
                    trigger="B_ATR_CATASTROPHE"
            elif label=="C":
                signal=candidate_c(asset_bars,params)
                if signal.get("exit"):trigger="C_EMA_EXIT"
            elif label=="D":
                signal=candidate_d(asset_bars,btc,params)
                if signal.get("exit"):trigger="D_TREND_EXIT"
            else:
                raise ValueError("UNKNOWN_POSITION_CANDIDATE")
            if trigger:
                self.conn.execute("""UPDATE orders SET status='RISK_CANCELLED',reason=?
                    WHERE status IN ('ADMITTED','MAKER_PENDING')
                    AND json_extract(original_json,'$.asset')=?""",(trigger,asset))
                held=p.positions[asset]["qty"]
                self._execute_taker(p,"protect:"+slot,asset,"SELL",held,quotes,now,forced=True)
                events.append({"action":"PROTECTIVE_SELL","asset":asset,"reason":trigger})
        return events

    def _process_pending(self,p,quotes,snapshot,now):
        events=[]
        rows=self.conn.execute("""SELECT decision_id,original_json,synthesis_hash,
                          expires_at,status,remaining,limit_price,placed_at
                          FROM orders WHERE status IN ('ADMITTED','MAKER_PENDING')
                          ORDER BY submitted_at,decision_id""").fetchall()
        for identity,original,sha,expires,status,remaining,limit_price,placed_at in rows:
            dec=json.loads(original)
            asset,side=dec["asset"],dec["action"]
            amount=d(remaining)
            if amount<=0:raise ValueError("PAPER_ORDER_INVALID_REMAINING")
            if now>utc(expires):
                self.conn.execute("UPDATE orders SET status='EXPIRED',reason='TTL_EXPIRED' WHERE decision_id=?",(identity,))
                events.append({"id":identity,"action":"EXPIRED"})
                continue
            if asset not in quotes:
                events.append({"id":identity,"action":"PAUSED_MISSING_QUOTE"})
                continue
            if status=="ADMITTED":
                original_market=self.conn.execute(
                    "SELECT asof FROM syntheses WHERE digest=?",(sha,)).fetchone()
                if original_market is None:raise ValueError("ADMISSION_SYNTHESIS_MISSING")
                latest=dict(snapshot,signal_asof=original_market[0])
                gate=validate(dec,latest,p,now,risk_state=self._risk(snapshot,exclude=identity),
                              phase="execution")
                if not gate["accepted"]:
                    self.conn.execute("UPDATE orders SET status='REJECTED',reason=? WHERE decision_id=?",
                                      (gate["reason"],identity))
                    events.append({"id":identity,"action":"REJECTED","reason":gate["reason"]})
                    continue
                if dec["order_type"]=="taker":
                    try:
                        self._execute_taker(p,identity,asset,side,amount,quotes,now)
                    except ValueError as exc:
                        self.conn.execute("UPDATE orders SET status='REJECTED',reason=? WHERE decision_id=?",
                                          (str(exc),identity))
                        events.append({"id":identity,"action":"REJECTED","reason":str(exc)})
                        continue
                    self.conn.execute("UPDATE orders SET status='FILLED',remaining='0',reason='TAKER_FILLED' WHERE decision_id=?",(identity,))
                    events.append({"id":identity,"action":"TAKER_FILLED"})
                else:
                    limit=quotes[asset]["bid"] if side=="BUY" else quotes[asset]["ask"]
                    self.conn.execute("""UPDATE orders SET status='MAKER_PENDING',limit_price=?,
                                      placed_at=?,reason='MAKER_POSTED' WHERE decision_id=?""",
                                      (str(limit),now.isoformat(),identity))
                    events.append({"id":identity,"action":"MAKER_POSTED"})
            else:
                if now<=utc(placed_at):continue
                # An order admitted at a previous IT is NOT pre-authorized forever:
                # re-check live quotes, remaining positions/cash and portfolio risk
                # at EVERY settlement cycle. Exclude only its own reservation.
                origin=self.conn.execute("SELECT asof FROM syntheses WHERE digest=?",(sha,)).fetchone()
                if not origin:raise ValueError("ADMISSION_SYNTHESIS_MISSING")
                live=dict(snapshot,signal_asof=origin[0])
                second_gate=validate(dec,live,p,now,
                                     risk_state=self._risk(snapshot,exclude=identity),
                                     phase="execution")
                if not second_gate["accepted"]:
                    self.conn.execute("""UPDATE orders SET status='REJECTED',reason=?
                                         WHERE decision_id=?""",
                                      (second_gate["reason"],identity))
                    events.append({"id":identity,"action":"SETTLEMENT_REJECTED",
                                   "reason":second_gate["reason"]})
                    continue
                # Only public trades after placing the limit, crossing strictly, can
                # generate partial PAPER maker fills. Remainder falls back to taker.
                tape=snapshot.get("trades",{}).get(asset,[])
                crossed=passive_crossing_qty(side.lower(),limit_price,amount,
                                            utc(placed_at).timestamp(),tape,
                                            participation=SPEC["COMMON"]["maker_fill_participation_hypothesis"])
                if crossed>0:
                    try:
                        self._fill(p,identity,asset,side,crossed,d(limit_price),"maker",now)
                        amount-=crossed
                        events.append({"id":identity,"action":"MAKER_PARTIAL","qty":str(crossed)})
                    except ValueError as exc:
                        events.append({"id":identity,"action":"MAKER_REJECTED","reason":str(exc)})
                if amount>0:
                    try:
                        self._execute_taker(p,identity,asset,side,amount,quotes,now)
                        amount=d(0)
                        events.append({"id":identity,"action":"TAKER_FALLBACK"})
                    except ValueError as exc:
                        self.conn.execute("UPDATE orders SET status='REJECTED',reason=? WHERE decision_id=?",
                                          (str(exc),identity))
                        events.append({"id":identity,"action":"FALLBACK_REJECTED","reason":str(exc)})
                        continue
                self.conn.execute("UPDATE orders SET status='FILLED',remaining='0',reason='SETTLED' WHERE decision_id=?",(identity,))
        return events

    def tick(self,snapshot,now,slot=None):
        """One offline PAPER cycle, idempotent by slot, no network and no real API."""
        moment=utc(now) if isinstance(now,str) else now.astimezone(timezone.utc)
        slot=slot or moment.strftime("%Y%m%d%H%M")
        if not isinstance(slot,str) or not slot or len(slot)>80:
            raise ValueError("INVALID_PAPER_CYCLE_SLOT")
        existing=self.conn.execute("SELECT status,note FROM cycles WHERE slot=?",(slot,)).fetchone()
        if existing:return {"status":existing[0],"duplicate":True,"note":existing[1]}
        events=[]
        self.current_books=snapshot.get("books") if isinstance(snapshot,dict) else None
        with self.transaction():
            p=self.wallet()
            try:
                quotes=self._market_quotes(snapshot,moment,p.positions)
                equity=p.equity(self._marks(quotes,p.positions))
                if self.last_exclusions:
                    events.append({"action":"PAIRS_EXCLUDED_THIS_TICK",
                                   "pairs":self.last_exclusions})
            except (ValueError,TypeError,KeyError) as exc:
                self.conn.execute("INSERT INTO cycles VALUES(?,?,?,?)",
                                  (slot,moment.isoformat(),"PAUSED_MISSING_MARKET",str(exc)))
                return {"status":"PAUSED_MISSING_MARKET","reason":str(exc),"events":[]}
            peak=max(d(self._get("equity_peak_usd")),equity)
            self._put("equity_peak_usd",str(peak))
            # Engine independently owns peak and kill-switch; snapshot risk data ignored.
            if equity<=peak*(1-d(SPEC["RISK"]["peak_drawdown_kill"])) and not self._get("risk_lock"):
                self._put("risk_lock",True)
                self._put("cooldown_until",(moment+timedelta(days=int(SPEC["RISK"]["cooldown_days"]))).isoformat())
                self._put("kill_count",int(self._get("kill_count"))+1)
                self.conn.execute("""UPDATE orders SET status='RISK_CANCELLED',reason='KILL_SWITCH'
                                     WHERE status IN ('ADMITTED','MAKER_PENDING')""")
                events.append({"action":"KILL_SWITCH"})
                for asset,held in list(p.positions.items()):
                    self._execute_taker(p,"risk:"+slot,asset,"SELL",held["qty"],quotes,moment,forced=True)
                    events.append({"action":"FORCED_SELL","asset":asset})
            if self._get("risk_lock"):
                self.conn.execute("""UPDATE orders SET status='RISK_CANCELLED',
                      reason='ENGINE_RISK_LOCK' WHERE status IN ('ADMITTED','MAKER_PENDING')""")
            else:
                events.extend(self._protect_positions(p,quotes,snapshot,moment,slot))
            if not self._get("risk_lock") and not self._get("paused"):
                events.extend(self._process_pending(p,quotes,snapshot,moment))
            else:
                # Risk-managed holdings stay under independent monitoring
                # even if Grok misses its daily IT.
                events.append({"action":"RISK_LOCK_OR_PAUSE_NO_NEW_ORDERS"})
            equity=p.equity(self._marks(quotes,p.positions))
            if self.current_books is not None:
                from v12_liquidity import evaluate_alert
                alert=evaluate_alert(self._get("liquidity_metrics"))
                self._put("liquidity_alert",alert)
                if alert:events.append({"action":"LIQUIDITY_REVIEW","alert":alert})
            self._put("wallet",self._wallet_json(p))
            usdc=None;btc_ref=None
            usdc_quote=snapshot.get("usdc_usd")
            if self.quote_currency=="USDC":
                # Account currency is USDC: "keep the USDC" is constant C0 (0 %).
                usdc=_money(self._get("initial_capital_usd"))
            elif usdc_quote is not None:
                checked_rate(usdc_quote,moment.isoformat())
                units=self._get("usdc_initial_units")
                if units is None:
                    units=str(initial_units(self._get("initial_capital_usd"),usdc_quote,moment.isoformat()))
                    self._put("usdc_initial_units",units)
                usdc=str(usd_value(units,usdc_quote,moment.isoformat()))
            if "BTC" in quotes:
                btc_units=self._get("btc_initial_units")
                if btc_units is None:
                    fee=self._fee("taker")
                    btc_units=str(d(self._get("initial_capital_usd")) /
                                  (quotes["BTC"]["ask"]*(1+fee)))
                    self._put("btc_initial_units",btc_units)
                btc_ref=str(d(btc_units)*quotes["BTC"]["bid"]*(1-self._fee("taker")))
            self.conn.execute("""INSERT OR IGNORE INTO marks(ts,equity,fees,usdc_hold_usd,btc_hold_usd)
                                 VALUES(?,?,?,?,?)""",
                              (moment.isoformat(),str(equity),str(p.fees_paid),usdc,btc_ref))
            self.conn.execute("INSERT INTO cycles VALUES(?,?,?,?)",
                              (slot,moment.isoformat(),"DRY_RUN",canonical(events)))
        self._outcomes(moment)
        return {"status":"DRY_RUN","duplicate":False,"events":events,
                "equity_usd":str(equity),"usdc_hold_usd":usdc,
                "risk_locked":self._get("risk_lock")}

    def _outcomes(self,now):
        """ENGINE-COMPUTED portfolio-period returns, not agent-reported PnL."""
        db=open_journal(str(self.root))
        try:
            records=db.execute("SELECT event_id,occurred_at,payload FROM evidence WHERE kind='decision' ORDER BY seq").fetchall()
            current=self.conn.execute("SELECT ts,equity,fees,usdc_hold_usd,btc_hold_usd FROM marks WHERE ts<=? ORDER BY ts DESC LIMIT 1",(now.isoformat(),)).fetchone()
            if not current:return
            for identity,at,raw in records:
                if not json.loads(raw).get("accepted"):continue
                baseline=self.conn.execute("""SELECT ts,equity,fees,usdc_hold_usd,btc_hold_usd
                     FROM marks WHERE ts<=? ORDER BY ts DESC LIMIT 1""",(at,)).fetchone()
                if baseline is None:continue
                for days in (1,7,30):
                    if now<utc(at)+timedelta(days=days):continue
                    # Once evaluated, never rewrite the outcome at a later tick.
                    # Its event timestamp, chosen first eligible mark and evidence
                    # hash remain frozen, even as more market data arrives.
                    if db.execute("SELECT 1 FROM evidence WHERE event_id=?",
                                  ("outcome:"+identity+":"+str(days),)).fetchone():
                        continue
                    mark=self.conn.execute("""SELECT ts,equity,fees,usdc_hold_usd,btc_hold_usd
                          FROM marks WHERE ts>=? ORDER BY ts LIMIT 1""",
                          ((utc(at)+timedelta(days=days)).isoformat(),)).fetchone()
                    if not mark or None in (baseline[3],baseline[4],mark[3],mark[4]):continue
                    try:
                        def ratio(col):
                            return float(d(mark[col])/d(baseline[col])-1)
                        rows=self.conn.execute(
                           "SELECT equity FROM marks WHERE ts BETWEEN ? AND ?",
                           (baseline[0],mark[0])).fetchall()
                        min_ret=min(float(d(x[0])/d(baseline[1])-1) for x in rows)
                        result={"decision_id":identity,"horizon_days":days,
                            "strategy_net_return":ratio(1),
                            "cash_usdc_net_return":ratio(3),
                            "btc_net_return":ratio(4),
                            "fees_paid_usd":str(d(mark[2])-d(baseline[2])),
                            "mae_portfolio":min_ret,
                            "generated_by":"PAPER_ENGINE_V12",
                            "attribution":"PORTFOLIO_LEVEL_NOT_CAUSAL_PER_TRADE",
                            "baseline_ts":baseline[0],"evaluated_ts":mark[0]}
                        append(db,"outcome","outcome:"+identity+":"+str(days),now.isoformat(),result)
                    except ValueError as exc:
                        if "EVIDENCE_ID_COLLISION" not in str(exc):raise
                        raise
        finally:db.close()

    def report(self):
        p=self.wallet()
        counts=dict(self.conn.execute("SELECT status,COUNT(*) FROM orders GROUP BY status"))
        events=dict(self.conn.execute("SELECT liquidity,COUNT(*) FROM fills GROUP BY liquidity"))
        marks=self.conn.execute("SELECT ts,equity,usdc_hold_usd,btc_hold_usd FROM marks ORDER BY ts").fetchall()
        out={"kind":"SYNTHETIC_OFFLINE_PAPER_ONLY","initial_cash_usd":self._get("initial_capital_usd"),
             "portfolio":self._wallet_json(p),"engine_peak_usd":self._get("equity_peak_usd"),
             "risk_lock":self._get("risk_lock"),"kill_count":self._get("kill_count"),
             "orders_by_status":counts,"fills_by_liquidity":events,"marks":len(marks),
             "first_mark":marks[0] if marks else None,"last_mark":marks[-1] if marks else None}
        return out

    def close(self):
        self.conn.close()
