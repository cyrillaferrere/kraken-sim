#!/usr/bin/env python3
"""Append-only, hash-chained decision/outcome record for Grok V1.2 PAPER.

Records observations and proposals, NOT a self-training foundation model.
No automatic parameter change, no activation of any trading cycle.
Only an external path authorized by v12_isolation can be used.
"""
import hashlib
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

from v12_isolation import state_dir
from v12_autonomy import utc

KINDS=frozenset(("decision","outcome","policy_proposal","policy_assessment"))
ZERO="0"*64

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)

def open_journal(directory=None):
    root=state_dir(directory)
    root.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(root/"grok_paper_evidence_v12.db",timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("""CREATE TABLE IF NOT EXISTS evidence(
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind IN ('decision','outcome','policy_proposal','policy_assessment')),
        occurred_at TEXT NOT NULL,
        payload TEXT NOT NULL,
        previous_hash TEXT NOT NULL,
        record_hash TEXT NOT NULL)""")
    conn.commit()
    return conn

def _hash(previous,kind,event_id,occurred_at,payload):
    return hashlib.sha256(canonical([previous,kind,event_id,occurred_at,payload]).encode("utf8")).hexdigest()

def _validate(kind,event_id,stamp,payload):
    if kind not in KINDS or not isinstance(event_id,str) or not 1<=len(event_id)<=192:
        raise ValueError("INVALID_EVENT_KIND_OR_ID")
    at=utc(stamp)
    if not isinstance(payload,dict):
        raise ValueError("INVALID_EVENT_PAYLOAD")
    if kind=="decision":
        if (payload.get("decision_id")!=event_id or payload.get("status")!="PREFLIGHT_ONLY_NOT_EXECUTED"
            or not isinstance(payload.get("accepted"),bool) or not isinstance(payload.get("reason"),str)):
            raise ValueError("INVALID_PREFLIGHT_EVENT")
    if kind=="outcome":
        if payload.get("horizon_days") not in (1,7,30):
            raise ValueError("INVALID_EVALUATION_HORIZON")
        if not isinstance(payload.get("decision_id"),str):
            raise ValueError("OUTCOME_WITHOUT_DECISION_ID")
        if not all(isinstance(payload.get(x),(int,float)) and not isinstance(payload.get(x),bool)
                   for x in ("strategy_net_return","cash_usdc_net_return","btc_net_return")):
            raise ValueError("OUTCOME_WITHOUT_COMPARABLE_RETURNS")
    if kind=="policy_proposal":
        if (payload.get("status")!="SHADOW_ONLY" or
            payload.get("candidate") not in ("A","B","C","D") or
            payload.get("live_permission") is not False or
            not payload.get("hypothesis")):
            raise ValueError("POLICY_PROPOSAL_NOT_SHADOW_ONLY")
    if kind=="policy_assessment" and payload.get("decision") not in ("REJECT","NEEDS_REVIEW"):
        raise ValueError("AUTOMATIC_POLICY_PROMOTION_FORBIDDEN")
    return at

def append(conn,kind,event_id,stamp,payload):
    """Idempotent exact retry; reject altered event IDs; hash every record."""
    at=_validate(kind,event_id,stamp,payload)
    payload_text=canonical(payload)
    when=at.isoformat()
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        existing=conn.execute(
            "SELECT kind,occurred_at,payload,record_hash FROM evidence WHERE event_id=?",
            (event_id,)).fetchone()
        if existing:
            if existing[:3]!=(kind,when,payload_text):
                raise ValueError("EVIDENCE_ID_COLLISION")
            return {"event_id":event_id,"record_hash":existing[3],"duplicate":True}
        if kind=="outcome":
            # No hindsight attribution unless original decision was committed.
            prior=conn.execute("SELECT occurred_at FROM evidence WHERE event_id=? AND kind='decision'",
                               (payload["decision_id"],)).fetchone()
            if prior is None:
                raise ValueError("OUTCOME_WITHOUT_COMMITTED_DECISION")
            if at<utc(prior[0])+timedelta(days=payload["horizon_days"]):
                raise ValueError("OUTCOME_BEFORE_EVALUATION_HORIZON")
        prev_row=conn.execute("SELECT occurred_at,record_hash FROM evidence ORDER BY seq DESC LIMIT 1").fetchone()
        prev=prev_row[1] if prev_row else ZERO
        # Stable hash chain chronological by event recording time, not market candle.
        if prev_row and utc(prev_row[0])>at:
            raise ValueError("NON_MONOTONIC_EVENT_TIME")
        signature=_hash(prev,kind,event_id,when,payload_text)
        conn.execute("""INSERT INTO evidence(event_id,kind,occurred_at,payload,previous_hash,record_hash)
                        VALUES(?,?,?,?,?,?)""",(event_id,kind,when,payload_text,prev,signature))
    return {"event_id":event_id,"record_hash":signature,"duplicate":False}

def verify(conn):
    previous=ZERO
    rows=conn.execute("""SELECT event_id,kind,occurred_at,payload,previous_hash,record_hash
                          FROM evidence ORDER BY seq""").fetchall()
    last=None
    for event_id,kind,stamp,payload_text,prior,digest in rows:
        if (prior!=previous or digest!=_hash(prior,kind,event_id,stamp,payload_text)
            or (last is not None and utc(stamp)<last)):
            raise ValueError("EVIDENCE_CHAIN_BROKEN")
        previous=digest
        last=utc(stamp)
    return {"records":len(rows),"last_hash":previous,"verified":True,
            "note":"Local hash chain detects edits unless all later hashes are recalculated; external anchoring needed for tamper resistance."}

def summarize(conn):
    """Counting is evidence, not a profitability or promotion claim."""
    rows=conn.execute("SELECT kind,payload FROM evidence ORDER BY seq").fetchall()
    stats={"decisions":0,"approved":0,"rejected":0,"hold":0,
           "outcomes":0,"policy_proposals":0,"needs_review":0,"auto_promotions":0}
    for kind,raw in rows:
        x=json.loads(raw)
        if kind=="decision":
            stats["decisions"]+=1
            stats["approved" if x["accepted"] else "rejected"]+=1
            if x.get("reason")=="HOLD_LOGGED_NO_ORDER":stats["hold"]+=1
        if kind=="outcome":stats["outcomes"]+=1
        if kind=="policy_proposal":stats["policy_proposals"]+=1
        if kind=="policy_assessment" and x.get("decision")=="NEEDS_REVIEW":
            stats["needs_review"]+=1
    return stats
