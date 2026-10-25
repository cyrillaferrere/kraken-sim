#!/usr/bin/env python3
"""V1.2 offline entrypoint. Synthetic --dry-run, HOLD-only --init-check; --cycle BLOCKED.

The 30-day fixture does not call Grok Bot, Kraken or any real trading endpoint.
"""
import argparse
import json
import sys
from v12_isolation import db_path, IsolationError

def main(argv=None):
    p=argparse.ArgumentParser(description="Kraken V1.2 : préflight et test fictif uniquement")
    opts=p.add_mutually_exclusive_group(required=True)
    opts.add_argument("--validate-env",action="store_true")
    opts.add_argument("--cycle",action="store_true",
                      help="INTERDIT : aucune simulation autonome activée")
    opts.add_argument("--dry-run",action="store_true",
                      help="30 jours synthétiques hors ligne, sans appel Grok")
    opts.add_argument("--init-check",action="store_true",
                      help="init état si absent + check marché public + HOLD seul, 0 ordre")
    p.add_argument("--state-dir",help="dossier d'état V1.2 (absolu); défaut V12_STATE_DIR")
    p.add_argument("--out",help="dossier externe de sortie; obligatoire avec --dry-run")
    args=p.parse_args(argv)
    if args.dry_run:
        if not args.out: p.error("--dry-run requiert --out (chemin absolu hors dépôt)")
        from v12_synthetic_30d import run_30day_fixture
        try:
            report=run_30day_fixture(args.out)
        except (IsolationError,ValueError) as exc:
            p.error(str(exc))
        print(json.dumps(report,indent=2,ensure_ascii=False))
        return 0
    if args.init_check:
        from v12_init_check import run,InitCheckRefused
        import os
        try:
            report=run(args.state_dir or os.environ.get("V12_STATE_DIR"))
        except (IsolationError,InitCheckRefused,AssertionError) as exc:
            print("V1.2 INIT-CHECK REFUSED:",exc,file=sys.stderr);return 4
        print(json.dumps(report,indent=2,ensure_ascii=False))
        return 0 if report["orders"]==0 else 4
    try: path=db_path()
    except IsolationError as exc: p.error(str(exc))
    if args.validate_env:
        print("OK V1.2 isolated path (read-only preflight):",path)
        return 0
    print("V1.2 BLOCKED: Cyril approval required; --cycle never runs autonomous trading",file=sys.stderr)
    return 3

if __name__=="__main__":
    sys.exit(main())
