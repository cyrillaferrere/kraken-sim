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

API="https://api.kraken.com/0/public/"
EXCLUDED=set(SPEC["UNIVERSE"]["exclusions"])
RENAMES={"XBT":"BTC","XXBT":"BTC","XDG":"DOGE"}

VALUATION_METHOD=("Quotes in USDC: Kraken XXX/USDC ticker when listed online with spread <= 0.3 %; "
    "otherwise XXX/USD divided by Kraken USDC/USD (bid/ask_usdcusd, ask/bid_usdcusd). "
    "Daily bars (signals, ratios) stay on XXX/USD.")

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

def pairs_usd(rows):
    found={}
    for key,row in rows.items():
        if not isinstance(row,dict) or row.get("status","online")!="online":continue
        ws=row.get("wsname","")
        if not isinstance(ws,str) or not ws.endswith("/USD"):continue
        asset=RENAMES.get(ws[:-4],ws[:-4])
        if asset in EXCLUDED or asset.startswith("USD") or "." in asset or not asset.isalnum():
            continue
        if asset in found:raise KrakenMarketError("DUPLICATE_ASSET_ALIAS_"+asset)
        found[asset]=(key,row)
    if not {"BTC","ETH"}.issubset(found):raise KrakenMarketError("MISSING_BTC_ETH")
    return found

def pairs_usdc(rows):
    """Kraken XXX/USDC spot pairs (online), preferred for USDC valuation."""
    found={}
    for key,row in rows.items():
        if not isinstance(row,dict) or row.get("status","online")!="online":continue
        ws=row.get("wsname","")
        if not isinstance(ws,str) or not ws.endswith("/USDC"):continue
        asset=RENAMES.get(ws[:-5],ws[:-5])
        if asset not in found:found[asset]=(key,row)
    return found

MAX_DIRECT_SPREAD=d("0.003")

def usdc_quote(asset,usd_price,usdc_pairs,tickers,usdc):
    """Quote an asset in USDC (account currency of the V1.2 portfolio).
    1) direct Kraken XXX/USDC ticker when the pair exists, is online and its
       spread <= 0.3 %; 2) otherwise XXX/USD converted by USDC/USD,
       conservatively: bid_usdc = bid_usd / ask_usdcusd, ask_usdc = ask_usd / bid_usdcusd."""
    if asset in usdc_pairs:
        try:
            row=ticker_row(tickers,usdc_pairs[asset][0])
            bid,ask=d(row["bid"]),d(row["ask"])
            if (ask-bid)/((ask+bid)/2)<=MAX_DIRECT_SPREAD:
                return {"bid":str(bid),"ask":str(ask),"valuation":"KRAKEN_"+asset+"_USDC_DIRECT"}
        except KrakenMarketError:pass
    return {"bid":str(d(usd_price["bid"])/d(usdc["ask"])),
            "ask":str(d(usd_price["ask"])/d(usdc["bid"])),
            "valuation":"KRAKEN_"+asset+"_USD_DIV_USDCUSD"}

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
    """Top 24h USD spot préréduit; filtres d'univers 30j par moteur ensuite.
    Ce préfiltre est non exhaustif: validation historique non garantie.
    """
    if type(max_pairs) is not int or not 2<=max_pairs<=60:
        raise ValueError("max_pairs must be 2..60")
    rawpairs,_=call("AssetPairs",opener=opener)
    metadata=pairs_usd(rawpairs)
    tickers,quote_received=call("Ticker",opener=opener)
    shortlist=[]
    for asset,(key,info) in metadata.items():
        try:price=ticker_row(tickers,key)
        except KrakenMarketError:continue
        shortlist.append((price["usd_volume"],asset,key,info,price))
    shortlist.sort(key=lambda row:(-row[0],row[1]))
    selected=shortlist[:max_pairs]
    for important in ("BTC","ETH"):
        if important not in {r[1] for r in selected}:
            match=next((r for r in shortlist if r[1]==important),None)
            if match is None:raise KrakenMarketError("MANDATORY_TICKER_ABSENT")
            selected.append(match)
    stable_key=next((k for k,v in rawpairs.items()
                     if isinstance(v,dict) and v.get("wsname")=="USDC/USD"
                     and v.get("status","online")=="online"),None)
    if stable_key is None:raise KrakenMarketError("USDC_USD_PAIR_ABSENT")
    usdcprice=ticker_row(tickers,stable_key)
    usdc={"source":"trusted-public-kraken","bid":usdcprice["bid"],
          "ask":usdcprice["ask"],"as_of":quote_received.isoformat()}
    usdc_pairs=pairs_usdc(rawpairs)
    histories={};quotes={}
    for _,asset,key,pair,price in selected:
        values,received=call("OHLC",{"pair":key,"interval":1440},opener=opener)
        candles=daily_bars(values,key,received)
        if not candles:raise KrakenMarketError("NO_CLOSED_CANDLES_"+asset)
        histories[asset]=candles
        q=usdc_quote(asset,price,usdc_pairs,tickers,usdc)
        quotes[asset]={"bid":q["bid"],"ask":q["ask"],"quote_currency":"USDC",
                       "valuation":q["valuation"],
                       "as_of":quote_received.isoformat(),
                       "min_order_usd":str(pair.get("costmin","25"))}
    observed=clock()
    if observed-quote_received>timedelta(minutes=5):
        raise KrakenMarketError("TICKERS_STALE_AFTER_COLLECTION")
    return {"status":"PAPER","source":"trusted-public-kraken",
            "observed_at":observed.isoformat(),"quotes":quotes,"daily_bars":histories,
            "usdc_usd":usdc,"quote_currency":"USDC",
            "valuation_method":VALUATION_METHOD,"trades":{},"data_origin":"KRAKEN_PUBLIC_API",
            "universe_note":"24h-volume prefilter non exhaustive; 30d median signal still required"}

def overview(snapshot):
    return {"asof":snapshot["observed_at"],"market":"Kraken public",
            "pairs":len(snapshot["daily_bars"]),
            "btc_daily_bars":len(snapshot["daily_bars"].get("BTC",[])),
            "eth_daily_bars":len(snapshot["daily_bars"].get("ETH",[])),
            "usdc_usd_bid":snapshot["usdc_usd"]["bid"],
            "usdc_usd_ask":snapshot["usdc_usd"]["ask"],
            "no_trading_keys":True,"orders_sent":0}
