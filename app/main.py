"""Punto de entrada del SICAM.

Uso:  uv run python -m app.main
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .core import db, seed
from .ui.shell import Shell
from .ui.theme import qss


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SICAM")
    app.setOrganizationName("Createl Trading SAC")
    app.setStyleSheet(qss())
    # Los gráficos almacenan algunos colores como objetos QColor; sincronizarlos
    # con el tema persistido antes de construir la interfaz.
    from .ui.charts import actualizar_colores_tema
    actualizar_colores_tema()

    conn = db.conectar()
    primera_vez = False
    nc_existentes = conn.execute("SELECT COUNT(*) FROM no_conformidades").fetchone()[0]
    prod_existente = conn.execute("SELECT COUNT(*) FROM produccion").fetchone()[0]
    if nc_existentes == 0 and prod_existente == 0:
        # Carga primero el catálogo canónico en una base nueva.
        seed.siembra(conn)
        primera_vez = True
    else:
        seed.asegurar_maquinas_costura(conn)
        # migraciones ligeras para BDs creadas en fases anteriores
        if conn.execute("SELECT COUNT(*) FROM checklists").fetchone()[0] == 0:
            seed.sembrar_fase2(conn)
        if conn.execute("SELECT COUNT(*) FROM plan_ejecuciones").fetchone()[0] == 0:
            seed.sembrar_fase3(conn)
        if (conn.execute("SELECT COUNT(*) FROM iot_umbrales").fetchone()[0] == 0
                or conn.execute("SELECT COUNT(*) FROM iot_lecturas").fetchone()[0] == 0):
            seed.sembrar_fase4(conn)

    shell = Shell(conn)
    shell.show()
    if primera_vez:
        shell.toast("Primera ejecución: se cargó la semilla sintética (2024 + piloto)", "warn")

    codigo = app.exec()
    conn.close()
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
