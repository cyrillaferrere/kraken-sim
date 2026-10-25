#!/usr/bin/env python3
"""Deterministic OFFLINE harness executing the ORIGINAL V1.1 paper engine.

NO public/private network requests. NO writes to production sim.db or state/.
Simulates only fixture timestamps and publicly observed response payloads.
A passing fixture does NOT certify V1.1 historical financial performance:
historical hourly quotes, orderbook depth and post-placement trades must be
captured/verified independently before an official historical baseline exists.
"""
import json
import sqlite3
import tempfile
from contextlib import ExitStack
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

import cycle_v11 as production
import history_export

ROOT=Path(__file__).resolve().parent

def _safe_root(folder):
    root=Path(folder).resolve()
    if root==ROOT or ROOT in root.parents or root==Path("/"):
        raise ValueError("V11_REPLAY_OUTPUT_MUST_BE_OUTSIDE_PRODUCTION_REPO")
    if any((a/"sim.db").exists() for a in (root,*root.parents)):
        raise ValueError("V11_REPLAY_OUTPUT_CANNOT_SHARE_PRODUCTION_DB")
    return root

def _utc(stamp):
    x=datetime.fromisoformat(stamp.replace("Z","+00:00"))
    if x.tzinfo is None or x.utcoffset().total_seconds()!=0:
        raise ValueError("snapshot must have timezone UTC")
    return x.astimezone(timezone.utc)

def check_snapshots(document):
    if not isinstance(document,dict) or not isinstance(document.get("cycles"),list) or not document["cycles"]:
        raise ValueError("V11_REPLAY_FIXTURE_MISSING_CYCLES")
    prev=None;slots=set()
    for snap in document["cycles"]:
        ts=_utc(snap["now_utc"])
        slot=ts.strftime("%Y%m%d%H")
        if prev is not None and ts<=prev:
            raise ValueError("V11_REPLAY_NON_MONOTONIC")
        if slot in slots:
            raise ValueError("V11_REPLAY_DUPLICATE_SLOT")
        slots.add(slot);prev=ts
        api=snap.get("api",{})
        if not isinstance(api,dict) or not all(x in api for x in ("AssetPairs","Ticker","OHLC")):
            raise ValueError("V11_REPLAY_MISSING_PUBLIC_SNAPSHOTS")
    return True

def replay_fixture(document, folder):
    """Return a reproducible ledger summary. Always marked UNVERIFIED.
    Every required endpoint must come from the supplied fixture; no fallback.
    No network access (public or private); runtime database and history under folder.
    """
    check_snapshots(document)
    root=_safe_root(folder)
    root.mkdir(parents=True,exist_ok=True)
    dbfile=root/"fixture_v11.db"
    if dbfile.exists():
        raise ValueError("V11_REPLAY_WOULD_OVERWRITE_EXISTING_FIXTURE")
    history_root=root/"fixture_history"
    observations=[]
    original_export=history_export.export_cycle
    def export_offline(conn,slot,engine,strategy):
        return original_export(conn,slot,engine,strategy,root=str(history_root))
    with ExitStack() as stack:
        stack.enter_context(patch.object(production.V,"DB",str(dbfile)))
        stack.enter_context(patch("history_export.export_cycle",side_effect=export_offline))
        stack.enter_context(patch("urllib.request.urlopen",side_effect=AssertionError("OFFLINE_REPLAY_NETWORK_FORBIDDEN")))
        for snap in document["cycles"]:
            ts=_utc(snap["now_utc"])
            api=snap["api"]
            class FrozenUTC(datetime):
                @classmethod
                def now(cls,tz=None):
                    return ts if tz is not None else ts.replace(tzinfo=None)
            def mock_get(endpoint, **params):
                if endpoint not in api:
                    raise ValueError("V11_REPLAY_ENDPOINT_MISSING: "+endpoint)
                response=api[endpoint]
                if endpoint in ("OHLC","Depth","Trades"):
                    pair=params.get("pair")
                    if not pair or pair not in response:
                        raise ValueError("V11_REPLAY_PAIR_MISSING: "+str((endpoint,pair)))
                    return response[pair]
                if endpoint=="Ticker" and "pair" in params:
                    pair=params["pair"]
                    if pair not in response:
                        raise ValueError("V11_REPLAY_PAIR_MISSING: "+str((endpoint,pair)))
                    return {pair:response[pair]}
                return response
            with patch.object(production,"datetime",FrozenUTC), patch.object(production.V,"get",side_effect=mock_get):
                production.main()
            observations.append({"slot":ts.strftime("%Y%m%d%H"),"utc":ts.isoformat()})
    db=sqlite3.connect(dbfile)
    try:
        cycles=db.execute("SELECT slot,status,mode,strategy_version FROM cycles ORDER BY slot").fetchall()
        orders=db.execute("""SELECT slot,asset,side,round(qty,10),round(price,10),
                          round(fee,10),liquidity,version,strategy_version
                          FROM orders ORDER BY id""").fetchall()
        eq=db.execute("SELECT slot,round(equity,7),round(cash,7) FROM equity ORDER BY slot").fetchall()
        positions=db.execute("SELECT asset,round(qty,10),round(avg_price,10) FROM positions ORDER BY asset").fetchall()
        meta=dict(db.execute("SELECT k,v FROM meta"))
    finally:
        db.close()
    return {"classification":"OFFLINE_FIXTURE_ONLY_NOT_HISTORICAL_REPRODUCTION",
            "engine_file":"cycle_v11.py","strategy":"V1.1",
            "fixture_source":document.get("source","unspecified"),
            "observations":observations,
            "cycles":cycles,"orders":orders,"equity":eq,"positions":positions,
            "capital_initial_usd":float(meta["C0"]),
            "history_root":str(history_root)}

def run_in_temporary_directory(document):
    """Convenient side-effect-free harness, suitable for CI and analysis only."""
    with tempfile.TemporaryDirectory(prefix="kraken-v11-offline-") as tmp:
        result=replay_fixture(document,tmp)
        result.pop("history_root",None)
        return result

def assert_not_official_baseline(result):
    if result.get("classification")=="OFFLINE_FIXTURE_ONLY_NOT_HISTORICAL_REPRODUCTION":
        raise ValueError("OFFLINE_FIXTURE_IS_NOT_VERIFIED_V11_BASELINE")
