#!/usr/bin/env python3
"""Offline preparation for official Kraken 1440-minute OHLCVT ZIP archives.

No downloads, no API keys, no production DB access.  Collects evidence and
creates MANIFEST.draft.json only: never self-certifies a complete universe.

Usage:
 python3 prepare_kraken_history_v12.py scan --archives ARCHIVES.json --out inventory.json
 python3 prepare_kraken_history_v12.py build --archives ARCHIVES.json \
      --mapping PAIR_REVIEW.json --output /separate/local/v12-history

ARCHIVES.json example: {"archives":[{"file":"/data/Kraken_OHLCVT_Full.zip",
 "sha256":"<actual 64hex SHA256 verified against official source>",
 "source_url":"https://assets.kraken.com/marketing/institutions/...",
 "retrieved_utc":"2026-10-25T12:00:00Z"}]}
PAIR_REVIEW.json example: {"pairs":{"XXBTZUSD":{"asset":"BTC","listed_at":null,
 "status":"unknown","delisted_at":null,"evidence_url":null},
 "USDTUSD":{"exclude":true,"reason":"stablecoin"}}}.
Unknown pairs MUST be reviewed. First trading day does NOT prove listing date.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from v12_data import sha256_file

PAIR=re.compile(r"^(?P<pair>[A-Za-z0-9.]+)_1440\.csv$",re.IGNORECASE)
SHA=re.compile(r"^[0-9a-f]{64}$")
def _utc(text):
    parsed=datetime.fromisoformat(text.replace("Z","+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("retrieved_utc must include timezone")
    return parsed.astimezone(timezone.utc)

def _archives(document):
    entries=document.get("archives")
    if not isinstance(entries,list) or not entries:
        raise ValueError("ARCHIVES: at least one full official archive is required")
    inspected=[]
    for item in entries:
        path=Path(item["file"]).expanduser().resolve()
        expected=str(item.get("sha256","")).lower()
        if not SHA.fullmatch(expected):
            raise ValueError("ARCHIVE_UNVERIFIED_SHA256: "+path.name)
        url=urlsplit(item.get("source_url",""))
        if (url.scheme!="https" or url.netloc!="assets.kraken.com" or
            not url.path.startswith("/marketing/institutions/") or
            url.query or url.fragment):
            raise ValueError("ARCHIVE_UNTRUSTED_ORIGIN: "+path.name)
        _utc(item["retrieved_utc"])
        if not path.is_file() or sha256_file(path)!=expected:
            raise ValueError("ARCHIVE_HASH_MISMATCH: "+path.name)
        if not zipfile.is_zipfile(path):
            raise ValueError("ARCHIVE_NOT_ZIP: "+path.name)
        inspected.append(dict(item,file=str(path)))
    return inspected

def _daily_members(z):
    members={}
    for member in z.infolist():
        if member.is_dir():
            continue
        # ZIP may contain a directory, but traversal is never extracted.
        base=Path(member.filename).name
        match=PAIR.fullmatch(base)
        if not match:
            continue
        pair=match.group("pair").upper()
        if not pair.endswith(("USD","ZUSD")):
            continue
        if pair in members:
            raise ValueError("DUPLICATE_DAILY_PAIR_IN_ARCHIVE: "+pair)
        members[pair]=member
    return members

def inventory(archives):
    out={}
    for item in archives:
        with zipfile.ZipFile(item["file"]) as z:
            # Do not decompress multi-gigabyte complete archives during an inventory scan.
            # SHA-256 authenticates the whole ZIP; ZIP CRC is checked while each selected CSV is read.
            pairs=_daily_members(z)
            for pair,member in pairs.items():
                out.setdefault(pair,[]).append({"archive":Path(item["file"]).name,
                                                  "member":member.filename,
                                                  "compressed_bytes":member.compress_size,
                                                  "csv_bytes":member.file_size})
    return dict(source="Kraken official archive review - not a certified universe",
                status="INVENTORY_UNVERIFIED",pair_count=len(out),
                pairs=dict(sorted(out.items())))

def _rows(z,member):
    with z.open(member) as binary:
        with io.TextIOWrapper(binary,encoding="utf-8-sig",newline="") as text:
            for n,row in enumerate(csv.reader(text),1):
                if not row:
                    continue
                if len(row)!=7:
                    raise ValueError("BAD_OHLCVT_ROW: %s:%s"%(member.filename,n))
                # Do NOT rewrite precision or round floats: preserve official data text.
                try:
                    ts=int(row[0])
                    nums=[float(v) for v in row[1:6]]
                    trades=int(row[6])
                except (ValueError,OverflowError) as exc:
                    raise ValueError("BAD_OHLCVT_VALUE: %s:%s"%(member.filename,n)) from exc
                if (ts%86400 or not all(math.isfinite(x) for x in nums) or
                    min(nums[:4])<=0 or nums[4]<0 or
                    nums[1]<max(nums[0],nums[3]) or
                    nums[2]>min(nums[0],nums[3]) or trades<0):
                    raise ValueError("BAD_OHLCVT_PRICE_OR_TIME: %s:%s"%(member.filename,n))
                yield ts,",".join(row)+"\n"

def prepare(archives,review,output):
    index=inventory(archives)
    if not isinstance(review.get("pairs"),dict):
        raise ValueError("PAIR_REVIEW_MISSING")
    discovered=set(index["pairs"])
    mapped=set(review["pairs"])
    if discovered!=mapped:
        raise ValueError("UNREVIEWED_PAIRS: %s ; extraneous: %s"%
                         (sorted(discovered-mapped),sorted(mapped-discovered)))
    output=Path(output).expanduser().resolve()
    if output.is_relative_to(Path(__file__).resolve().parent):
        raise ValueError("OUTPUT_INSIDE_CODE_REPOSITORY_FORBIDDEN")
    output.mkdir(parents=True,exist_ok=True)
    manifest=[]
    used=set()
    for pair in sorted(index["pairs"]):
        entry=review["pairs"][pair]
        if entry.get("exclude"):
            if not entry.get("reason"):
                raise ValueError("EXCLUSION_WITHOUT_REASON: "+pair)
            continue
        asset=str(entry.get("asset","")).upper()
        if not re.fullmatch(r"[A-Z0-9]{2,12}",asset) or asset in used:
            raise ValueError("UNREVIEWED_OR_COLLIDING_ASSET: "+pair)
        used.add(asset)
        # No assumptions about first listing or delisting from the last candle.
        if entry.get("status") not in ("active","delisted","unknown"):
            raise ValueError("ASSET_LIFECYCLE_UNREVIEWED: "+pair)
        all_rows={}
        for item in archives:
            with zipfile.ZipFile(item["file"]) as z:
                member=_daily_members(z).get(pair)
                if member is None:continue
                for ts,row in _rows(z,member):
                    existing=all_rows.setdefault(ts,row)
                    if existing!=row:
                        raise ValueError("CONFLICTING_OVERLAP: %s %s"%(pair,ts))
        if not all_rows:
            raise ValueError("EMPTY_PAIR: "+pair)
        filename=asset+"USD_1440.csv"
        with (output/filename).open("w",encoding="utf8",newline="") as target:
            for ts in sorted(all_rows):
                target.write(all_rows[ts])
        sources=[{"url":a["source_url"],"sha256":a["sha256"]}
                 for a in archives if any(x["archive"]==Path(a["file"]).name for x in index["pairs"][pair])]
        manifest.append({"asset":asset,"file":filename,
                         "sha256":sha256_file(output/filename),
                         "source_url":sources[0]["url"],
                         "source_archives":sources,
                         "retrieved_utc":max(a["retrieved_utc"] for a in archives),
                         "listed_at":entry.get("listed_at"),
                         "status":entry["status"],
                         "delisted_at":entry.get("delisted_at"),
                         "lifecycle_evidence_url":entry.get("evidence_url"),
                         "min_order_usd":entry.get("min_order_usd"),
                         "first_observed_utc":datetime.fromtimestamp(min(all_rows),timezone.utc).isoformat(),
                         "last_observed_utc":datetime.fromtimestamp(max(all_rows),timezone.utc).isoformat()})
    candidate={"_status":"DRAFT_NEVER_AUTO_CERTIFIED",
               "coverage":{"all_historical_usd_spot_pairs_verified":False,
                           "enumeration_source_url":None,"enumeration_utc":None,
                           "historical_pair_ids":[]},
               "excluded_pairs":{p:x for p,x in review["pairs"].items() if x.get("exclude")},
               "files":manifest}
    (output/"MANIFEST.draft.json").write_text(json.dumps(candidate,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    (output/"INVENTORY.json").write_text(json.dumps(index,indent=2)+"\n",encoding="utf8")
    return {"status":"DRAFT_ONLY","assets":len(manifest),"pairs_reviewed":len(index["pairs"]),
            "manifest":str(output/"MANIFEST.draft.json"),
            "note":"Listing/lifecycle and historical-universe completeness require human evidence review."}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("scan","build"))
    p.add_argument("--archives",required=True)
    p.add_argument("--out",help="inventory JSON destination (scan)")
    p.add_argument("--mapping",help="PAIR_REVIEW.json (build)")
    p.add_argument("--output",help="dedicated external extraction directory (build)")
    a=p.parse_args(argv)
    archives=_archives(json.loads(Path(a.archives).read_text(encoding="utf8")))
    if a.mode=="scan":
        if not a.out:p.error("scan requires --out")
        dest=Path(a.out).resolve()
        if dest.is_relative_to(Path(__file__).resolve().parent):
            p.error("inventory output must be outside repository")
        dest.write_text(json.dumps(inventory(archives),indent=2)+"\n")
        print("Unverified inventory:",dest)
        return
    if not a.mapping or not a.output:
        p.error("build requires --mapping and --output")
    result=prepare(archives,json.loads(Path(a.mapping).read_text()),a.output)
    print(json.dumps(result,indent=2))
if __name__=="__main__":
    main()
