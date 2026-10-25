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
from v12_autonomy import SPEC,utc,validate
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
    def __init__(self,root,c0="6605.10"):
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

    def _market_quotes(self,snapshot,now,holdings):
        if snapshot.get("status")!="PAPER" or snapshot.get("source")!="trusted-public-kraken":
            raise ValueError("MARKET_SNAPSHOT_NOT_TRUSTED")
        quotes=snapshot.get("quotes",{})
        required=set(holdings)
        for a in required:
            if a not in quotes:raise ValueError("HELD_ASSET_MISSING_QUOTE")
        out={}
        for asset,q in quotes.items():
            moment=utc(q["as_of"])
            if now-moment>timedelta(minutes=5) or moment>now:
                raise ValueError("QUOTE_NOT_FRESH_FOR_EXECUTION")
            bid,ask=d(q["bid"]),d(q["ask"])
            if bid<=0 or ask<bid or (ask-bid)/((ask+bid)/2)>d("0.003"):
                raise ValueError("QUOTE_INVALID_FOR_EXECUTION")
            out[asset]={"bid":bid,"ask":ask}
        return out

    def _fee(self,liquidity):
        return d(SPEC["COSTS"]["F2"][liquidity])

    def _slip(self,asset,forced=False):
        group="major" if asset in ("BTC","ETH") else "other"
        base=d(SPEC["COSTS"]["slippage"][group])
        return base*d(SPEC["COSTS"]["forced_multiplier"] if forced else 1)

    def _fill(self,portfolio,identity,asset,side,qty,px,liquidity,now):
        fee=self._fee(liquidity)
        if side=="BUY":
            paid=portfolio.buy(asset,qty,px,fee)
        else:
            portfolio.sell(asset,qty,px,fee)
            paid=d(qty)*d(px)*fee
        self.conn.execute("""INSERT INTO fills(decision_id,asset,side,qty,price,fee,liquidity,ts)
                             VALUES(?,?,?,?,?,?,?,?)""",
                          (identity,asset,side,_money(qty),_money(px),_money(paid),
                           liquidity,now.isoformat()))
        return paid

    def _execute_taker(self,portfolio,identity,asset,side,qty,quotes,now,forced=False):
        q=quotes[asset]
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
        equity=p.equity({a:q["bid"] for a,q in quotes.items()})
        from v12_signals import candidate_c,closed_candles
        bars=snapshot.get("daily_bars",{})
        signals={}
        for asset in ("BTC","ETH"):
            arr=closed_candles(bars.get(asset,[]),t)
            if len(arr)>=220:
                sig=candidate_c(arr,SPEC["CANDIDATES"]["C"])
                signals[asset]={"C_entry":bool(sig["entry"]),"C_exit":bool(sig["exit"]),
                                "C_target_weight":round(float(sig["target_weight"]),4)}
        summary={"asof":t.isoformat(),"engine":"V1.2 PAPER OFFLINE FIXTURE",
                 "active_policy_version":self._get("active_policy_version"),
                 "strategy":"V1.2","candidates":["A","B","C","D"],
                 "quotes":{a:{"bid":str(v["bid"]),"ask":str(v["ask"])}
                           for a,v in list(quotes.items())[:20]},
                 "signals":signals,
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
        with self.transaction():
            p=self.wallet()
            try:
                quotes=self._market_quotes(snapshot,moment,p.positions)
                equity=p.equity({a:q["bid"] for a,q in quotes.items()})
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
            if not self._get("risk_lock") and not self._get("paused"):
                events.extend(self._process_pending(p,quotes,snapshot,moment))
            else:
                # Risk-managed holdings stay under independent monitoring
                # even if Grok misses its daily IT.
                events.append({"action":"RISK_LOCK_OR_PAUSE_NO_NEW_ORDERS"})
            equity=p.equity({a:q["bid"] for a,q in quotes.items()})
            self._put("wallet",self._wallet_json(p))
            usdc=None;btc_ref=None
            usdc_quote=snapshot.get("usdc_usd")
            if usdc_quote is not None:
                checked_rate(usdc_quote,moment)
                units=self._get("usdc_initial_units")
                if units is None:
                    units=str(initial_units(self._get("initial_capital_usd"),usdc_quote,moment))
                    self._put("usdc_initial_units",units)
                usdc=str(usd_value(units,usdc_quote,moment))
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
