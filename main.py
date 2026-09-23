"""Lanzador raíz de SICAM.

Este archivo existe para que PyInstaller empaquete el paquete `app` completo.
En desarrollo se puede usar indistintamente:

    uv run python main.py
    uv run python -m app.main

PyInstaller debe compilar este `main.py` (no `app/main.py`), porque los
imports relativos de `app/main.py` solo funcionan cuando el módulo se
importa como parte del paquete `app`.
"""
from app.main import main

if __name__ == "__main__":
    raise SystemExit(main())
