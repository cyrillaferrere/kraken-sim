#!/usr/bin/env python3
"""Offline Grok V1.2 proposal intake. Not an API client or an order executor.

The real Grok provider adapter, scheduler, trusted Kraken market collector and
actual paper ledger are NOT wired up.  This function makes the required
decision -> independent risk gate -> durable evidence connection testable.
"""
import hashlib
from datetime import datetime, timezone

from v12_autonomy import utc,validate
from v12_learning import append,canonical,open_journal,verify

def inspect_and_record(proposal,trusted_snapshot,portfolio,evidence_directory,now):
    """Return audited PREVIEW ONLY; never mutates Portfolio or places an order.

    No model call is made. At deployment, only an independently authenticated
    provider adapter can supply 'proposal', and only the trusted collector can
    supply 'trusted_snapshot'. Do not expose the latter as an agent-editable input.
    """
    now=utc(now) if isinstance(now,str) else now.astimezone(timezone.utc)
    if not isinstance(trusted_snapshot,dict):
        raise ValueError("TRUSTED_SNAPSHOT_REQUIRED")
    result=validate(proposal,trusted_snapshot,portfolio,now)
    # Even invalid model outputs and provider timeouts have an audit ID.
    submitted=proposal if isinstance(proposal,dict) else None
    identity=result.get("decision_id")
    if not isinstance(identity,str) or not 1<=len(identity)<=192:
        identity="invalid:"+hashlib.sha256(canonical(submitted).encode("utf8")).hexdigest()[:48]
    evidence=dict(result)
    evidence["decision_id"]=identity
    evidence["model_id"]=submitted.get("model_id") if submitted else None
    evidence["policy_version"]=submitted.get("policy_version") if submitted else None
    evidence["requested_action"]=submitted.get("action") if submitted else None
    evidence["requested_asset"]=submitted.get("asset") if submitted else None
    evidence["proposal_sha256"]=hashlib.sha256(canonical(submitted).encode("utf8")).hexdigest()
    evidence["market_snapshot_sha256"]=hashlib.sha256(canonical(trusted_snapshot).encode("utf8")).hexdigest()
    # Approval is permission to be considered by a separate PAPER execution
    # gate later. This invocation deliberately has no executor!
    conn=open_journal(evidence_directory)
    try:
        record=append(conn,"decision",identity,now.isoformat(),evidence)
        chain=verify(conn)
    finally:
        conn.close()
    return {"decision":result,"evidence":record,"verified_log":chain,
            "paper_order_executed":False,"live_order_executed":False,
            "model_invoked":False}
