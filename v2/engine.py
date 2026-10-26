#!/usr/bin/env python3
"""Kraken Sim V2 — garde-fou PAPER avant fourniture de chiffres par GrokBot.

Ce fichier ne simule aucun ordre et ne fabrique aucun capital, prix, allocation,
seuil ou rendement. Le moteur de strategie V2 reste a integrer apres validation
explicite des donnees et regles transmises par GrokBot.
"""
import json
from pathlib import Path

STATE = Path(__file__).with_name("state.json")

def run():
    state = json.loads(STATE.read_text(encoding="utf-8"))
    if state.get("data_source") != "grokbot_verified" or state.get("initial") is None:
        print("HOLD — V2 en attente des chiffres et de leur provenance GrokBot. Aucun ordre.")
        return
    print("HOLD — Donnees recues mais moteur V2 non valide. Aucun ordre.")

if __name__ == "__main__":
    run()
