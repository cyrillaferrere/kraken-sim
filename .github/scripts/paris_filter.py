#!/usr/bin/env python3
"""Filtre horaire des runs planifiés (heure de Paris), tolérant au retard du cron GitHub.
Usage: paris_filter.py EVENT [NOW_ISO]  -> imprime go=1|go=0 (+ raison sur stderr)."""
import json, os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
TZ = ZoneInfo("Europe/Paris")

def decide(event, now, hours, last_cycle):
    if event != "schedule":
        return True, "déclenchement manuel : pas de filtre"
    h = now.hour
    if h in hours: ok = "créneau %02d" % h
    elif (h - 1) % 24 in hours: ok = "créneau %02d en retard" % ((h - 1) % 24)
    else: return False, "hors créneau (%02dh)" % h
    if last_cycle and now - last_cycle < timedelta(minutes=90):
        return False, "doublon : dernier cycle %s (< 90 min)" % last_cycle.strftime("%d/%m %H:%M")
    return True, ok

def last_cycle_time(path="state/public_state.json", now=None):
    try:
        s = json.load(open(path))["as_of"]  # ex. "25/10 12h24", heure de Paris
        now = now or datetime.now(TZ)
        t = datetime.strptime(f"{now.year} {s}", "%Y %d/%m %Hh%M").replace(tzinfo=TZ)
        if t > now + timedelta(days=1): t = t.replace(year=now.year - 1)
        return t
    except Exception:
        return None

if __name__ == "__main__":
    ev = sys.argv[1]
    now = datetime.fromisoformat(sys.argv[2]).replace(tzinfo=TZ) if len(sys.argv) > 2 else datetime.now(TZ)
    hours = {int(x) for x in os.environ.get("PARIS_HOURS", "").split()}
    go, why = decide(ev, now, hours, last_cycle_time(now=now))
    print(f"Heure Paris: {now:%d/%m %H:%M} -> {'accepté' if go else 'refusé'} ({why})", file=sys.stderr)
    print(f"go={int(go)}")
