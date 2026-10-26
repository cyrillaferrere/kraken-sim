#!/usr/bin/env python3
"""Garde-fous de liquidité PAPER V1.2 (Moteur V1.6.2). Aucun réseau, aucune clé.

- Seuil d'univers : MÉDIANE sur 30 jours du volume quotidien XXX/USDC
  (volume × close des bougies OHLC journalières CLOSES), pas le Ticker 24 h.
- Avant chaque ordre PAPER taker : profondeur cumulée côté exécution dans ±0,5 %
  autour du mid >= 3 × taille de l'ordre (en USDC), sinon INSUFFICIENT_DEPTH.
- Slippage estimé en traversant le carnet (VWAP vs meilleur prix côté exécution).
- Alerte LIQUIDITY_REVIEW si >= 20 tentatives et (refus > 5 % ou slippage médian > 0,15 %).
  Repli DOCUMENTÉ (non automatisé) : retour au seuil de 5 M USDC.
Donnée manquante -> None (null), jamais 0.
"""
import logging
import statistics
from decimal import Decimal,InvalidOperation

from v12_autonomy import SPEC,min_median_volume_usdc

LOG=logging.getLogger("kraken_sim.v12.liquidity")
_L=SPEC.get("LIQUIDITY",{})
_U=SPEC["UNIVERSE"]

ROLLBACK_MIN_MEDIAN=float(_L.get("rollback_min_median_daily_usdc_volume_30d",5000000))
DEPTH_BAND=Decimal(str(_L.get("depth_band_pct",0.005)))
DEPTH_MULTIPLE=Decimal(str(_L.get("depth_multiple",3)))
ALERT_MIN_ATTEMPTS=int(_L.get("alert_min_attempts",20))
ALERT_MAX_REJECT=Decimal(str(_L.get("alert_max_reject_rate",0.05)))
ALERT_MAX_SLIPPAGE=Decimal(str(_L.get("alert_max_median_slippage",0.0015)))
VOLUME_DAYS=int(_U.get("liquidity_days",30))
ROLLBACK_POLICY=("Repli manuel documenté (non automatisé) : si LIQUIDITY_REVIEW est levée, "
    "Cyril décide le retour du seuil à 5 M USDC de volume médian 30 j "
    "(UNIVERSE.min_median_daily_usdc_volume_30d=5000000) via un correctif versionné.")

def _dec(x):
    try:
        v=Decimal(str(x))
    except (InvalidOperation,TypeError,ValueError):
        return None
    return v if v.is_finite() else None

def median_volume_usdc_30d(candles,days=None):
    """Médiane des volumes quotidiens en USDC (volume × close) sur les `days` dernières
    bougies closes. None si moins de `days` bougies ou une donnée manquante/invalide."""
    days=days or VOLUME_DAYS
    if not isinstance(candles,list) or len(candles)<days:
        return None
    vals=[]
    for c in candles[-days:]:
        if not isinstance(c,dict) or c.get("imputed"):return None
        v,px=_dec(c.get("volume")),_dec(c.get("close"))
        if v is None or px is None or v<0 or px<=0:return None
        vals.append(v*px)
    return statistics.median(vals)

def parse_depth(result,key):
    """Réponse publique /0/public/Depth -> {'bids':[(p,q)...] décroissant,'asks':[...] croissant}."""
    row=result.get(key) if isinstance(result,dict) else None
    if row is None and isinstance(result,dict):
        cands=[k for k in result if k!="last"]
        row=result[cands[0]] if len(cands)==1 else None
    if not isinstance(row,dict):return None
    out={}
    for side in ("bids","asks"):
        levels=[]
        for lv in row.get(side) or []:
            try:
                p,q=_dec(lv[0]),_dec(lv[1])
            except (IndexError,TypeError):
                return None
            if p is None or q is None or p<=0 or q<0:return None
            levels.append((p,q))
        out[side]=sorted(levels,key=lambda x:-x[0] if side=="bids" else x[0])
    if not out["bids"] or not out["asks"]:return None
    return out

def book_from_snapshot(row):
    """Carnet stocké dans le snapshot ({'bids':[[p,q]],'asks':...}) -> carnet parsé ou None."""
    return parse_depth({"book":row},"book") if isinstance(row,dict) else None

def _levels(book,side):
    return book["asks"] if side=="BUY" else book["bids"]

def book_summary(book):
    """Instantané résumé : meilleur bid/ask, spread, profondeur USDC à ±0,5 %."""
    if not book:
        return {"best_bid":None,"best_ask":None,"mid":None,"spread_pct":None,
                "depth_bid_usdc_0_5pct":None,"depth_ask_usdc_0_5pct":None}
    bb,ba=book["bids"][0][0],book["asks"][0][0]
    mid=(bb+ba)/2
    lo,hi=mid*(1-DEPTH_BAND),mid*(1+DEPTH_BAND)
    dbid=sum((p*q for p,q in book["bids"] if p>=lo),Decimal(0))
    dask=sum((p*q for p,q in book["asks"] if p<=hi),Decimal(0))
    return {"best_bid":float(bb),"best_ask":float(ba),"mid":float(mid),
            "spread_pct":float((ba-bb)/mid*100),
            "depth_bid_usdc_0_5pct":float(dbid),"depth_ask_usdc_0_5pct":float(dask)}

def check_order(book,side,qty):
    """Contrôle pré-ordre. side BUY consomme les asks, SELL les bids.
    Retourne accepted, reason, order_usdc, depth_usdc, slippage_pct (null si inconnu)."""
    q=_dec(qty)
    if side not in ("BUY","SELL") or q is None or q<=0:
        return {"accepted":False,"reason":"INVALID_ORDER","order_usdc":None,"depth_usdc":None,"slippage_pct":None}
    if not book:
        return {"accepted":False,"reason":"DEPTH_UNAVAILABLE","order_usdc":None,"depth_usdc":None,"slippage_pct":None}
    bb,ba=book["bids"][0][0],book["asks"][0][0]
    mid=(bb+ba)/2
    levels=_levels(book,side)
    if side=="BUY":
        depth=sum((p*x for p,x in levels if p<=mid*(1+DEPTH_BAND)),Decimal(0))
    else:
        depth=sum((p*x for p,x in levels if p>=mid*(1-DEPTH_BAND)),Decimal(0))
    order=q*mid
    # Slippage : VWAP obtenu en traversant le carnet vs meilleur prix côté exécution.
    left=q;cost=Decimal(0)
    for p,x in levels:
        take=min(left,x);cost+=take*p;left-=take
        if left<=0:break
    slip=None
    if left<=0:
        vwap=cost/q;best=levels[0][0]
        slip=float(abs(vwap-best)/best*100)
    ok=depth>=DEPTH_MULTIPLE*order
    return {"accepted":bool(ok),"reason":None if ok else "INSUFFICIENT_DEPTH",
            "order_usdc":float(order),"depth_usdc":float(depth),"slippage_pct":slip}

def empty_metrics():
    return {"attempts":0,"accepted":0,"rejections":{},"slippages_pct":[]}

def record(metrics,result):
    m=dict(metrics or empty_metrics())
    m["rejections"]=dict(m.get("rejections") or {})
    m["slippages_pct"]=list(m.get("slippages_pct") or [])[-500:]
    m["attempts"]=int(m.get("attempts",0))+1
    if result["accepted"]:
        m["accepted"]=int(m.get("accepted",0))+1
        if result.get("slippage_pct") is not None:m["slippages_pct"].append(result["slippage_pct"])
    else:
        r=result.get("reason") or "UNKNOWN"
        m["rejections"][r]=int(m["rejections"].get(r,0))+1
    return m

def evaluate_alert(metrics):
    """LIQUIDITY_REVIEW si >= 20 tentatives et (refus > 5 % ou slippage médian > 0,15 %)."""
    m=metrics or empty_metrics()
    n=int(m.get("attempts",0))
    rejected=sum(int(v) for v in (m.get("rejections") or {}).values())
    rate=(Decimal(rejected)/n) if n else None
    sl=m.get("slippages_pct") or []
    med=statistics.median(sl) if sl else None
    reasons=[]
    if n>=ALERT_MIN_ATTEMPTS:
        if rate is not None and rate>ALERT_MAX_REJECT:reasons.append("REJECTION_RATE_ABOVE_5_PCT")
        if med is not None and Decimal(str(med))/100>ALERT_MAX_SLIPPAGE:reasons.append("MEDIAN_SLIPPAGE_ABOVE_0_15_PCT")
    alert={"code":"LIQUIDITY_REVIEW","reasons":reasons,"attempts":n,
           "rejection_rate_pct":float(rate*100) if rate is not None else None,
           "median_slippage_pct":med,"fallback":ROLLBACK_POLICY} if reasons else None
    if alert:
        LOG.warning("LIQUIDITY_REVIEW: %s",alert)
    return alert

def monitor(metrics,books_summary,as_of,eligible_count=None,volumes=None):
    """Bloc liquidity_monitor (forme attendue par le dashboard PR #22, champs + détails)."""
    m=metrics or empty_metrics()
    n=int(m.get("attempts",0))
    rejected=sum(int(v) for v in (m.get("rejections") or {}).values())
    liq_rej=int((m.get("rejections") or {}).get("INSUFFICIENT_DEPTH",0))+int((m.get("rejections") or {}).get("DEPTH_UNAVAILABLE",0))
    sl=m.get("slippages_pct") or []
    spreads=[b["spread_pct"] for b in (books_summary or {}).values() if b.get("spread_pct") is not None]
    alert=evaluate_alert(m)
    return {"as_of":as_of,
        "min_median_daily_volume_usdc":min_median_volume_usdc(),
        "volume_basis":"median_30d_daily_ohlc_close_x_volume_usdc",
        "eligible_pairs_count":eligible_count,
        "order_attempts":n,
        "rejected_orders":rejected if n else None,
        "rejected_liquidity_orders":liq_rej if n else None,
        "rejected_liquidity_pct":(liq_rej/n*100) if n else None,
        "orderbook_checks":len(books_summary) if books_summary is not None else None,
        "median_spread_pct":statistics.median(spreads) if spreads else None,
        "estimated_slippage_pct":statistics.median(sl) if sl else None,
        "rejection_reasons":dict(m.get("rejections") or {}) if n else None,
        "depth_rule":{"band_pct":float(DEPTH_BAND*100),"multiple":float(DEPTH_MULTIPLE),
                      "reject_reason":"INSUFFICIENT_DEPTH"},
        "books":books_summary,"median_volumes_usdc_30d":volumes,
        "alert":alert,
        "rollback_policy":ROLLBACK_POLICY}
