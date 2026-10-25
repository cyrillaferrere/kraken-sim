# Batterie de tests V1.2 (phase infrastructure)

Depuis la racine : 
- python3 -m unittest discover -s tests -p 'test_v12_*.py' -v
- python3 -m unittest discover -s tests -p 'test_v11_nonregression.py' -v

Couverts : isolation et chemin explicite, refus de cycle en attente de SPEC, clé de cycle unique, schéma minimal et sérialisation atomique, look-ahead sur dates, gel statique du code V1.1 et de sim.yml.

NON ENCORE COUVERTS : comptabilité en positions, frais, maker/taker, ordres partiels, stress tests, stops et gap, replay V1.1 déterministe, backtests et walk-forward. Un guard vert ne valide PAS encore la stratégie.
