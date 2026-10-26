#!/usr/bin/env python3
"""Garde-fou de conformité UE/MiCA de la V1.2 (Moteur V1.6.1). Voir docs/CONFORMITE_UE_V1_2.md.

Indépendant de Grok et de l'apprentissage : constantes versionnées ici, appliquées
par le collecteur (univers) ET par la gateway (rejet de toute décision non conforme).
Particulier résidant en France, spot long uniquement, quote XXX/USDC uniquement.
"""
from decimal import Decimal

COUNTRY_CODE="FR"                 # AssetPairs?country_code=FR (filtre Kraken des paires accessibles)
QUOTE="USDC"                      # seule devise de cotation autorisée (Circle, EMT conforme MiCA)
MAX_SPREAD=Decimal("0.003")       # spread <= 0,3 %
# Stablecoins / monnaies : jamais tradés comme actif de base (USDT et non conformes MiCA inclus).
EXCLUDED_BASES=frozenset({"USDT","USDC","DAI","PYUSD","FDUSD","USDE","TUSD","USDG","USDQ","USDR",
    "USDS","RLUSD","EURC","EUROP","EURR","EURT","EURQ","EUR","GBP","USD","WBTC","TBTC","WETH",
    "PAXG","XAUT"})
# Actifs restreints FR : le filtre primaire est country_code=FR (Kraken). Repli statique
# (déjà utilisé en V1.1) appliqué EN PLUS, au cas où le filtre ne les retirerait pas.
# Liste Kraken « EEA clients cannot deposit or trade » (support.kraken.com, lue le 25/10/2026).
FR_RESTRICTED=frozenset("""AKE ALEO APXUSD AUDX AUGUR AUSD BASED BNKR BRL1 CASH CHECK COPM DAI DCR ESX EVAA FF
 FIDD FOLKS FRNT MXNB NOCK OPN OUSD PACT PONS PWT PYUSD QCAD RLUSD RNBW SN44 SN51 SN62 SN64 SN75 SN8
 SOFID SOMI ST STABLE STBL TAKE TCS TEA TGBP TREMP U2U UAI UMXM UNITAS USAT USD1 USDD USDE USDGO USDPT
 USDS USDT USTABLES VELVET VOOI WAR WEMIX WFB XAUT XMR""".split())
ALLOWED_ACTIONS=frozenset({"HOLD","BUY","SELL","CANCEL"})
FORBIDDEN_KEYS=frozenset({"leverage","margin","reduce_only","short","side_short","futures","contract"})
MIN_HISTORY_DAILY=220             # SMA200 régime BTC + EMA lente+20 (C) : en dessous -> insufficient_history
RENAMES={"XBT":"BTC","XXBT":"BTC","XDG":"DOGE"}

class ComplianceError(ValueError):pass

def base_of(row):
    ws=row.get("wsname","") if isinstance(row,dict) else ""
    if not isinstance(ws,str) or not ws.endswith("/"+QUOTE):return None
    b=ws[:-len(QUOTE)-1]
    return RENAMES.get(b,b)

def pair_rejection(row):
    """Raison de non-conformité d'une ligne AssetPairs (None si conforme hors spread)."""
    base=base_of(row)
    if base is None:return "QUOTE_NOT_USDC"
    if row.get("status")!="online":return "PAIR_NOT_ONLINE"
    if base in EXCLUDED_BASES or base.startswith("USD") or base.startswith("EUR"):return "STABLECOIN_OR_FIAT_EXCLUDED"
    if base in FR_RESTRICTED:return "FR_RESTRICTED_ASSET"
    if "." in base or not base.isalnum():return "NON_SPOT_ASSET"
    return None

def spread_ok(bid,ask):
    bid,ask=Decimal(str(bid)),Decimal(str(ask))
    return bid>0 and ask>=bid and (ask-bid)/((ask+bid)/2)<=MAX_SPREAD

def check_decision(decision,snapshot,positions):
    """Rejette toute décision non conforme. Appelé par la gateway avant le risque."""
    if not isinstance(decision,dict):raise ComplianceError("COMPLIANCE_INVALID_DECISION")
    if FORBIDDEN_KEYS & set(decision):raise ComplianceError("COMPLIANCE_LEVERAGE_MARGIN_SHORT_FORBIDDEN")
    action=decision.get("action");asset=str(decision.get("asset",""))
    if action not in ALLOWED_ACTIONS:raise ComplianceError("COMPLIANCE_ACTION_FORBIDDEN")
    if "/" in asset:
        if not asset.endswith("/"+QUOTE):raise ComplianceError("COMPLIANCE_QUOTE_NOT_USDC")
        asset=asset.split("/")[0]
    asset=RENAMES.get(asset,asset)
    comp=(snapshot or {}).get("compliance") or {}
    if comp.get("quote")!=QUOTE:raise ComplianceError("COMPLIANCE_SNAPSHOT_NOT_USDC")
    if asset in EXCLUDED_BASES or asset.startswith("USD"):raise ComplianceError("COMPLIANCE_STABLECOIN_FORBIDDEN")
    if asset in FR_RESTRICTED:raise ComplianceError("COMPLIANCE_FR_RESTRICTED")
    if action=="BUY":
        if asset not in comp.get("eligible",[]):raise ComplianceError("COMPLIANCE_PAIR_NOT_ELIGIBLE")
        if asset in comp.get("insufficient_history",[]):raise ComplianceError("COMPLIANCE_INSUFFICIENT_HISTORY")
    if action=="SELL":
        held=positions.get(asset) if isinstance(positions,dict) else None
        qty=Decimal(str(decision.get("quantity","0")))
        have=Decimal(str((held or {}).get("qty",0))) if isinstance(held,dict) else Decimal(str(getattr(held,"qty",0) or 0))
        if qty>have:raise ComplianceError("COMPLIANCE_SHORT_SELLING_FORBIDDEN")
    return True
