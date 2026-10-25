#!/usr/bin/env python3
"""Kraken REST public, lecture seule. Aucune API de trading ni clé.
Horodatage du ticker = réception HTTP (Ticker ne fournit pas timestamp serveur).
Les dernières bougies non closes sont exclues de façon stricte.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime,timedelta,timezone
from v12_accounting import d
from v12_autonomy import SPEC
from v12_compliance import (COUNTRY_CODE,MIN_HISTORY_DAILY,QUOTE,base_of,pair_rejection,spread_ok)

API="https://api.kraken.com/0/public/"
EXCLUDED=set(SPEC["UNIVERSE"]["exclusions"])
RENAMES={"XBT":"BTC","XXBT":"BTC","XDG":"DOGE"}

VALUATION_METHOD=("UE/MiCA (Moteur V1.6.1): Kraken XXX/USDC only (AssetPairs country_code=FR, status online, "
    "spread <= 0.3 %%), no USD conversion. Daily bars (signals, ratios) from XXX/USDC OHLC; "
    "pairs with fewer than %d closed daily bars are insufficient_history (bars null, never imputed).")%MIN_HISTORY_DAILY

class KrakenMarketError(RuntimeError): pass

def clock():
    return datetime.now(timezone.utc)

def call(endpoint,params=None,opener=None):
    if endpoint not in ("AssetPairs","Ticker","OHLC"):
        raise KrakenMarketError("NON_PUBLIC_ENDPOINT")
    uri=API+endpoint+"?"+urllib.parse.urlencode(params or {})
    if opener is None:
        def opener(request):
            with urllib.request.urlopen(request,timeout=20) as response:
                if response.status!=200:raise KrakenMarketError("HTTP_"+str(response.status))
                return response.read(5000001)
    try:
        raw=opener(urllib.request.Request(uri,headers={"User-Agent":"KrakenSimPaperV12/1.0"}))
        if len(raw)>5000000:raise KrakenMarketError("OVERSIZE_PUBLIC_RESPONSE")
        response=json.loads(raw)
    except (OSError,ValueError,TypeError) as exc:
        raise KrakenMarketError("PUBLIC_API_UNAVAILABLE") from exc
    if not isinstance(response,dict) or response.get("error") or not isinstance(response.get("result"),dict):
        raise KrakenMarketError("PUBLIC_API_ERROR")
    return response["result"],clock()

def pairs_usdc(rows):
    """Kraken XXX/USDC spot pairs: online, FR-accessible, compliant base (v12_compliance)."""
    found={};rejected={}
    for key,row in rows.items():
        base=base_of(row)
        if base is None:continue
        why=pair_rejection(row) or (("EXCLUDED_BY_SPEC") if base in EXCLUDED else None)
        if why:rejected[base]=why;continue
        if base in found:raise KrakenMarketError("DUPLICATE_ASSET_ALIAS_"+base)
        found[base]=(key,row)
    return found,rejected

def ticker_row(data,key):
    try:
        row=data[key]
        bid,ask,close,volume=map(d,(row["b"][0],row["a"][0],row["c"][0],row["v"][1]))
    except (KeyError,TypeError,IndexError,ValueError,ArithmeticError) as exc:
        raise KrakenMarketError("MISSING_TICKER_DATA_"+key) from exc
    if bid<=0 or ask<bid or close<=0 or volume<0:
        raise KrakenMarketError("INVALID_TICKER_"+key)
    return {"bid":str(bid),"ask":str(ask),"usd_volume":volume*close}

def daily_bars(data,key,asof):
    values=data.get(key)
    if values is None:
        candidates=[x for x in data if x!="last"]
        if len(candidates)!=1:raise KrakenMarketError("OHLC_RESPONSE_AMBIGUOUS")
        values=data[candidates[0]]
    if not isinstance(values,list):raise KrakenMarketError("MALFORMED_OHLC")
    output=[];seen=set()
    for v in values:
        if not isinstance(v,list) or len(v)<8:raise KrakenMarketError("BAD_OHLC_ROW")
        start=int(v[0]);end=start+86400
        if end>int(asof.timestamp()):continue
        if start in seen:raise KrakenMarketError("DUPLICATE_CANDLE")
        seen.add(start)
        op,high,low,close,volume=[d(v[i]) for i in (1,2,3,4,6)]
        if min(op,high,low,close)<=0 or volume<0 or low>min(op,close) or high<max(op,close):
            raise KrakenMarketError("INVALID_CANDLE")
        output.append({"end":datetime.fromtimestamp(end,timezone.utc).isoformat(),
            "open":str(op),"high":str(high),"low":str(low),"close":str(close),
            "volume":str(volume),"trades":int(v[7]),"imputed":False})
    output.sort(key=lambda row:row["end"])
    return output

def collect(max_pairs=40,opener=None):
    """Univers UE : uniquement XXX/USDC (country_code=FR, online, conforme, spread <= 0,3 %).
    Aucune conversion USD. Bougies journalières XXX/USDC ; historique court -> null.
    """
    if type(max_pairs) is not int or not 2<=max_pairs<=60:
        raise ValueError("max_pairs must be 2..60")
    rawpairs,_=call("AssetPairs",{"country_code":COUNTRY_CODE},opener=opener)
    metadata,rejected=pairs_usdc(rawpairs)
    tickers,quote_received=call("Ticker",{"pair":",".join(k for k,_ in metadata.values())} if metadata else None,opener=opener)
    shortlist=[]
    for asset,(key,info) in metadata.items():
        try:price=ticker_row(tickers,key)
        except KrakenMarketError:rejected[asset]="NO_TICKER";continue
        if not spread_ok(price["bid"],price["ask"]):rejected[asset]="SPREAD_ABOVE_0_3_PCT";continue
        shortlist.append((price["usd_volume"],asset,key,info,price))
    shortlist.sort(key=lambda row:(-row[0],row[1]))
    selected=shortlist[:max_pairs]
    for important in ("BTC","ETH"):
        if important not in {r[1] for r in selected}:
            match=next((r for r in shortlist if r[1]==important),None)
            if match is None:raise KrakenMarketError("MANDATORY_USDC_PAIR_ABSENT_"+important)
            selected.append(match)
    histories={};quotes={};insufficient={};history={}
    for _,asset,key,pair,price in selected:
        values,received=call("OHLC",{"pair":key,"interval":1440},opener=opener)
        candles=daily_bars(values,key,received)
        n=len(candles)
        if n<MIN_HISTORY_DAILY:
            insufficient[asset]=n
            history[asset]={"pair":asset+"/"+QUOTE,"closed_bars":n,"status":"insufficient_history",
                            "sma200":None,"donchian55":None,"bars":None}
        else:
            histories[asset]=candles
            history[asset]={"pair":asset+"/"+QUOTE,"closed_bars":n,"status":"ok"}
        quotes[asset]={"bid":price["bid"],"ask":price["ask"],"quote_currency":QUOTE,
                       "valuation":"KRAKEN_"+asset+"_USDC_DIRECT","pair":asset+"/"+QUOTE,
                       "as_of":quote_received.isoformat(),
                       "min_order_usd":str(pair.get("costmin","25"))}
    btc_n=history["BTC"]["closed_bars"]
    observed=clock()
    if observed-quote_received>timedelta(minutes=5):
        raise KrakenMarketError("TICKERS_STALE_AFTER_COLLECTION")
    eligible=sorted(quotes)
    return {"status":"PAPER","source":"trusted-public-kraken",
            "observed_at":observed.isoformat(),"quotes":quotes,"daily_bars":histories,
            "usdc_usd":None,"quote_currency":QUOTE,
            "valuation_method":VALUATION_METHOD,"trades":{},"data_origin":"KRAKEN_PUBLIC_API",
            "compliance":{"regime":"UE/MiCA","country_code":COUNTRY_CODE,"quote":QUOTE,
                "spot_long_only":True,"eligible":eligible,"eligible_pairs":[a+"/"+QUOTE for a in eligible],
                "insufficient_history":sorted(insufficient),"history":history,
                "rejected":dict(sorted(rejected.items())),
                "btc_regime_source":"BTC/USDC",
                "btc_regime_history":{"closed_bars":btc_n,"sufficient":btc_n>=MIN_HISTORY_DAILY}},
            "universe_note":"XXX/USDC only (country_code=FR); 30d median signal still required"}

def overview(snapshot):
    return {"asof":snapshot["observed_at"],"market":"Kraken public",
            "pairs":len(snapshot["daily_bars"]),
            "btc_daily_bars":len(snapshot["daily_bars"].get("BTC",[])),
            "eth_daily_bars":len(snapshot["daily_bars"].get("ETH",[])),
            "eligible_usdc_pairs":len(snapshot.get("compliance",{}).get("eligible",[])),
            "no_trading_keys":True,"orders_sent":0}
