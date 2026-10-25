#!/usr/bin/env python3
"""V1.2 paper-only entrypoint. FAIL CLOSED until Grok Bot's specification."""
import argparse
import sys
from v12_isolation import db_path, IsolationError

def main(argv=None):
    p=argparse.ArgumentParser()
    opts=p.add_mutually_exclusive_group(required=True)
    opts.add_argument("--validate-env",action="store_true")
    opts.add_argument("--cycle",action="store_true")
    args=p.parse_args(argv)
    try: path=db_path()
    except IsolationError as e: p.error(str(e))
    if args.validate_env:
        print("OK V1.2 isolated path (read-only preflight):",path)
        return 0
    print("V1.2 BLOCKED: strategy specification and Cyril approval required",file=sys.stderr)
    return 3

if __name__=="__main__": sys.exit(main())
