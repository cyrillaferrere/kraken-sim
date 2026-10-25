#!/usr/bin/env python3
"""Kraken OFFICIAL full OHLCVT archive downloader — explicit opt-in, resumable.

This CLI NEVER contacts Kraken's private/trading endpoints and NEVER runs a
simulation. Writes ONLY to a user-selected external directory. Checks all
five SHA-256 checksums *as published by Kraken*, plus the assembled ZIP SHA.
All large network transfer requires --download, otherwise prints the plan.

Source as of 2026-10-25:
https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data
https://assets.kraken.com/marketing/institutions/OHLCVT_Full_PARTS_SHA256SUMS.txt

Note: independent checksum for optional 2026Q3 ZIP has not been established.
Hashing a downloaded 2026Q3 ZIP is an integrity fingerprint, not an
independent attestation. This tool NEVER certifies historical listings.
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE_URL="https://assets.kraken.com/marketing/institutions/"
FULL_PARTS=(
    ("Kraken_OHLCVT_Full.zip.part00","12ce809a0cc12c421f9bb871434f71eca8b3c258cb194efae258318a683b9491"),
    ("Kraken_OHLCVT_Full.zip.part01","7086e1915e79b5157fae05978ca9603da7d7a53d03ee"),
    ("Kraken_OHLCVT_Full.zip.part02","880fcf84e177e50ca946f3f5cb6d57c721a4950853ca1bf6bdde526896013cc1"),
    ("Kraken_OHLCVT_Full.zip.part03","3fa1fdfbb94c5a3cc861068a11b5c309502a8ac8da0f4c6f091c5a2968451157"),
    ("Kraken_OHLCVT_Full.zip.part04","db2c8b80c92a2e09b3f71f464b0b55574bd56c645d2560169dbbe4887b9c00eb"),
)
FULL_NAME="Kraken_OHLCVT_Full.zip"
FULL_SHA256="bc273e9027470b07d790a7fa4df9bb43f0dfc527c20c6ecae48402e123e7b1c7"
Q3_NAME="Kraken_OHLCVT_2026Q3.zip"
CHUNK=4*1024*1024

def sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(CHUNK),b""):
            h.update(block)
    return h.hexdigest()

def destination(raw):
    dst=Path(raw).expanduser().resolve()
    if dst==Path("/") or dst==HERE or HERE in dst.parents:
        raise ValueError("OUTSIDE_REPOSITORY_REQUIRED")
    for parent in (dst,*dst.parents):
        if (parent/"sim.db").exists():
            raise ValueError("PRODUCTION_LEDGER_NEAR_DOWNLOAD_TARGET")
    if dst.exists() and not dst.is_dir():
        raise ValueError("OUTPUT_MUST_BE_DIRECTORY")
    return dst

def _response_start(response, offset):
    status=getattr(response,"status",None)
    if status is None and hasattr(response,"getcode"):
        status=response.getcode()
    if offset==0:
        if status not in (200,None):
            raise ValueError("HTTP_UNEXPECTED_STATUS: "+str(status))
        return 0,"wb"
    if status==206:
        got=response.headers.get("Content-Range","")
        found=re.match(r"^bytes (\d+)-\d+/\d+$",got)
        if not found or int(found.group(1))!=offset:
            raise ValueError("HTTP_INVALID_CONTENT_RANGE: "+got)
        return offset,"ab"
    if status==200:
        # Server ignores Range; start afresh. NEVER append a full file.
        return 0,"wb"
    raise ValueError("HTTP_RANGE_NOT_SUPPORTED: "+str(status))

def get_part(dst,filename,expected,timeout=60):
    final=dst/filename
    if final.exists():
        if sha256(final)!=expected:
            raise ValueError("EXISTING_PART_HASH_MISMATCH: "+filename)
        return final,"cached"
    partial=dst/(filename+".partial")
    offset=partial.stat().st_size if partial.exists() else 0
    req=urllib.request.Request(BASE_URL+filename,headers={
        "User-Agent":"Kraken-Sim-V12-public-dataset/1.0",
        **({"Range":"bytes=%d-"%offset} if offset else {}),
    })
    with urllib.request.urlopen(req,timeout=timeout) as response:
        _,mode=_response_start(response,offset)
        with open(partial,mode) as out:
            while True:
                block=response.read(CHUNK)
                if not block:
                    break
                out.write(block)
    if sha256(partial)!=expected:
        # Retain partial for diagnostics; no verified .part is made available.
        raise ValueError("PART_HASH_MISMATCH_OR_INCOMPLETE: "+filename)
    os.replace(partial,final)
    return final,"downloaded"

def assemble(dst):
    dest=dst/FULL_NAME
    if dest.exists():
        if sha256(dest)!=FULL_SHA256:
            raise ValueError("EXISTING_COMPLETE_ARCHIVE_HASH_MISMATCH")
        return dest,"cached"
    fd,tmp=tempfile.mkstemp(dir=dst,prefix=".kraken-full-",suffix=".zip")
    os.close(fd)
    try:
        with open(tmp,"wb") as output:
            for name,expected in FULL_PARTS:
                part=dst/name
                if not part.exists() or sha256(part)!=expected:
                    raise ValueError("UNVERIFIED_PART: "+name)
                with open(part,"rb") as src:
                    shutil.copyfileobj(src,output,length=CHUNK)
            output.flush()
            os.fsync(output.fileno())
        if sha256(tmp)!=FULL_SHA256:
            raise ValueError("ASSEMBLED_ARCHIVE_HASH_MISMATCH")
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return dest,"assembled"

def build_config(dst,archive,q3=None):
    now=datetime.now(timezone.utc).isoformat()
    item={"file":str(archive),"sha256":FULL_SHA256,
          "source_url":BASE_URL+FULL_PARTS[0][0],
          "retrieved_utc":now,
          "checksum_provenance":"Kraken SHA256 complete ZIP on official support article",
          "parts_checksum_source":BASE_URL+"OHLCVT_Full_PARTS_SHA256SUMS.txt"}
    config={"status":"DOWNLOADED_NOT_HISTORICALLY_CERTIFIED","archives":[item]}
    if q3:
        file=Path(q3).expanduser().resolve()
        if not file.is_file() or file.name!=Q3_NAME:
            raise ValueError("Q3_INPUT_MUST_BE_OFFICIAL_NAMED_ZIP")
        config["archives"].append({
            "file":str(file),"sha256":sha256(file),
            "source_url":BASE_URL+Q3_NAME,"retrieved_utc":now,
            "checksum_provenance":"Local fingerprint only; no independent published checksum supplied",
            "checksum_independently_attested":False})
    config["warning"]="Hash verification alone DOES NOT certify pair coverage, delistings or data provenance."
    out=dst/"ARCHIVES.json"
    if out.exists():
        raise ValueError("ARCHIVES_CONFIG_EXISTS: refusing to overwrite a review")
    tmp=dst/".ARCHIVES.json.tmp"
    try:
        tmp.write_text(json.dumps(config,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        os.replace(tmp,out)
    finally:
        tmp.unlink(missing_ok=True)
    return out

def run(out,download=False,q3=None,min_free_gib=25):
    dst=destination(out)
    plan={"mode":"DOWNLOAD_OPT_IN" if download else "DRY_RUN",
          "destination":str(dst),"parts":len(FULL_PARTS),
          "urls":[BASE_URL+name for name,_ in FULL_PARTS],
          "verification":"SHA-256 each part + assembled ZIP, official checksums",
          "official_full_zip_sha256":FULL_SHA256,
          "minimum_free_gib_required_when_downloading":min_free_gib}
    if not download:
        return plan
    dst.mkdir(parents=True,exist_ok=True)
    free=shutil.disk_usage(dst).free
    if free<min_free_gib*1024**3:
        raise ValueError("INSUFFICIENT_DISK_SPACE: at least %s GiB free required"%min_free_gib)
    statuses={}
    for name,digest in FULL_PARTS:
        _,status=get_part(dst,name,digest)
        statuses[name]=status
    archive,status=assemble(dst)
    plan["assembled_zip_status"]=status
    plan["part_statuses"]=statuses
    plan["manifest"]=str(build_config(dst,archive,q3))
    plan["mode"]="VERIFIED_DOWNLOAD_NOT_HISTORY_CERTIFICATION"
    return plan

def main(argv=None):
    p=argparse.ArgumentParser(description="Download public Kraken OHLCVT archives, manual only")
    p.add_argument("--out",required=True,help="absolute/external data volume, not repository")
    p.add_argument("--download",action="store_true",help="opt into downloading the large official ZIP parts")
    p.add_argument("--q3-file",help="optional already-downloaded Q3 ZIP, separate checksum provenance")
    p.add_argument("--min-free-gib",type=int,default=25,help="safety headroom, default 25 GiB")
    args=p.parse_args(argv)
    if args.min_free_gib<1: p.error("--min-free-gib must be >= 1")
    print(json.dumps(run(args.out,args.download,args.q3_file,args.min_free_gib),indent=2,ensure_ascii=False))
if __name__=="__main__":
    main()
