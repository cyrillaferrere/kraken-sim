"""Validate GPT-6 daily reports without allowing fabricated market numbers."""
import argparse
import re
from pathlib import Path

SECTIONS = ("## 1. Marché global", "## 2. Actifs éligibles", "## 3. Actualités et macro",
            "## 4. Risques", "## 5. Idées d'allocation", "## 6. Sources")


def validate_report(text, *, template=False):
    if not isinstance(text, str) or any(section not in text for section in SECTIONS):
        raise ValueError("Missing required report section")
    if "Horodatage" not in text or "Sources" not in text:
        raise ValueError("Missing provenance")
    if not template:
        if "GABARIT" in text:
            raise ValueError("Report is still a template")
        if not re.search(r"https://[^\s|)]+", text):
            raise ValueError("No source URL")
        if not re.search(r"20\d\d-\d\d-\d\dT\d\d:\d\d", text):
            raise ValueError("No UTC timestamp")
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("path", type=Path)
    p.add_argument("--template", action="store_true")
    args = p.parse_args()
    validate_report(args.path.read_text(encoding="utf-8"), template=args.template)
    print("Report structure OK")


if __name__ == "__main__":
    main()
