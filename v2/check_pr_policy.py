#!/usr/bin/env python3
"""PR guard for Kraken Sim V2. Requires GitHub event JSON and git history."""
import json
import os
import subprocess
import sys
from pathlib import Path


def changed(base, head):
    return subprocess.check_output(["git", "diff", "--name-only", base, head], text=True).splitlines()


def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("V2 PR guard only applies on pull_request events")
        return
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pr = event.get("pull_request")
    if not pr:
        return
    files = set(changed(pr["base"]["sha"], pr["head"]["sha"]))
    forbidden = {"sim.yml", "sim_v12.yml", "strategy/params.json",
                 "VERSION_ENGINE", "VERSION_ENGINE_V12"}
    forbidden_prefixes = ("strategy/v1_2/",)
    if files & forbidden or any(f.startswith(forbidden_prefixes) for f in files):
        sys.exit("V2 PR cannot modify V1/V1.2")
    if "v2/guardrails.json" in files:
        labels = {x["name"] for x in pr.get("labels", [])}
        if not pr["title"].startswith("[GUARDRAILS]") or "cyril-approved" not in labels:
            sys.exit("Guardrail change requires [GUARDRAILS] PR and cyril-approved label")
    if any(f.startswith("v2/") for f in files):
        if "CHANGELOG.md" not in files or "v2/README.md" not in files:
            sys.exit("V2 PR requires CHANGELOG.md and v2/README.md updates")
    print("V2 PR guard passed")


if __name__ == "__main__":
    main()
