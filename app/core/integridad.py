"""Auditoría de la base SQLite y reparaciones que no requieren inferir datos."""
from __future__ import annotations

import sqlite3
from datetime import date

from . import db, queries, seed


def _fecha_iso_valida(valor: str | None) -> bool:
    if not valor:
        return False
    try:
        return date.fromisoformat(valor).isoformat() == valor
    except (TypeError, ValueError):
        return False


def auditar_y_reparar(conn: sqlite3.Connection) -> dict[str, list[str] | str]:
    """Repara solo referencias huérfanas evidentes; notifica otras anomalías."""
    reparaciones: list[str] = []
    problemas: list[str] = []

    with conn:
        items_huerfanos = conn.execute(
            "SELECT COUNT(*) FROM checklist_items ci "
            "LEFT JOIN checklists c ON c.id = ci.checklist_id WHERE c.id IS NULL"
        ).fetchone()[0]
        if items_huerfanos:
            conn.execute(
                "DELETE FROM checklist_items WHERE checklist_id NOT IN "
                "(SELECT id FROM checklists)"
            )
            reparaciones.append(
                f"Eliminados {items_huerfanos} ítems de checklist sin registro padre."
            )

        tarjetas_huerfanas = conn.execute(
            "SELECT COUNT(*) FROM tarjetas_tpm t "
            "LEFT JOIN checklists c ON c.id = t.checklist_id "
            "WHERE t.origen = 'Checklist' AND t.checklist_id IS NOT NULL AND c.id IS NULL"
        ).fetchone()[0]
        if tarjetas_huerfanas:
            conn.execute(
                "DELETE FROM tarjetas_tpm WHERE origen = 'Checklist' "
                "AND checklist_id IS NOT NULL AND checklist_id NOT IN "
                "(SELECT id FROM checklists)"
            )
            reparaciones.append(
                f"Eliminadas {tarjetas_huerfanas} tarjetas automáticas sin checklist origen."
            )

    try:
        integridad_sqlite = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    except sqlite3.DatabaseError as exc:
        integridad_sqlite = f"error: {exc}"
    if integridad_sqlite != "ok":
        problemas.append(f"Integridad física SQLite no confirmada: {integridad_sqlite}")

    try:
        violaciones_fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violaciones_fk:
            problemas.append(f"Quedan {len(violaciones_fk)} violaciones de claves foráneas.")
    except sqlite3.DatabaseError as exc:
        problemas.append(f"No se pudieron comprobar claves foráneas: {exc}")

    prod_invalidos = 0
    for fila in conn.execute("SELECT fecha, inspeccionadas, nc_detectadas FROM produccion"):
        if (not _fecha_iso_valida(fila["fecha"])
                or fila["inspeccionadas"] <= 0
                or fila["nc_detectadas"] < 0
                or fila["nc_detectadas"] > fila["inspeccionadas"]):
            prod_invalidos += 1
    if prod_invalidos:
        problemas.append(
            f"{prod_invalidos} filas de producción tienen fechas o cantidades inconsistentes."
        )

    nc_invalidas = 0
    maquinas_no_encontradas = 0
    for fila in conn.execute(
        "SELECT fecha, turno, proceso, causa, cantidad, maquina FROM no_conformidades"
    ):
        if (not _fecha_iso_valida(fila["fecha"])
                or fila["turno"] not in db.TURNOS
                or fila["proceso"] not in db.PROCESOS
                or fila["causa"] not in db.CAUSAS
                or fila["cantidad"] <= 0):
            nc_invalidas += 1
        maquina = fila["maquina"]
        if maquina and maquina != "—" and not conn.execute(
            "SELECT 1 FROM maquinas WHERE codigo = ?", (maquina,)
        ).fetchone():
            maquinas_no_encontradas += 1
    if nc_invalidas:
        problemas.append(
            f"{nc_invalidas} no conformidades contienen fecha, catálogo o cantidad inválidos."
        )
    if maquinas_no_encontradas:
        problemas.append(
            f"{maquinas_no_encontradas} no conformidades apuntan a máquinas inexistentes."
        )

    for tabla in ("checklists", "tarjetas_tpm", "frecuencias"):
        n = conn.execute(
            f"SELECT COUNT(*) FROM {tabla} t "
            "WHERE NOT EXISTS (SELECT 1 FROM maquinas m WHERE m.codigo = t.maquina)"
        ).fetchone()[0]
        if n:
            problemas.append(f"{n} filas de {tabla} apuntan a máquinas inexistentes.")

    # No sobrescribir cambios legítimos: las diferencias del catálogo se notifican.
    maquinas_desviadas = 0
    for codigo, tipo, marca, area, criticidad, compra, calibracion in seed.MAQUINAS:
        fila = conn.execute(
            "SELECT tipo, marca_modelo, area, criticidad, fecha_compra, ultima_calibracion "
            "FROM maquinas WHERE codigo = ?", (codigo,)
        ).fetchone()
        if fila and tuple(fila) != (tipo, marca, area, criticidad, compra, calibracion):
            maquinas_desviadas += 1
    if maquinas_desviadas:
        problemas.append(
            f"{maquinas_desviadas} máquinas de muestra difieren del catálogo canónico; "
            "revísalas o usa «Restablecer datos piloto»."
        )

    faltan_produccion = []
    faltan_nc = []
    for mes in ("2026-08", "2026-09", "2026-10", "2026-11"):
        desde, hasta = queries.limites_mes(mes)
        produccion = conn.execute(
            "SELECT COUNT(*) FROM produccion WHERE fecha BETWEEN ? AND ?", (desde, hasta)
        ).fetchone()[0]
        no_conformidades = conn.execute(
            "SELECT COUNT(*) FROM no_conformidades WHERE fecha BETWEEN ? AND ?", (desde, hasta)
        ).fetchone()[0]
        etiqueta = queries.etiqueta_mes(mes)
        if not produccion:
            faltan_produccion.append(etiqueta)
        if not no_conformidades:
            faltan_nc.append(etiqueta)
    if faltan_produccion:
        problemas.append(
            "Falta producción piloto para: " + ", ".join(faltan_produccion)
            + ". Usa «Restablecer datos piloto» para regenerar la demostración."
        )
    if faltan_nc:
        problemas.append(
            "Faltan registros de no conformidad piloto para: " + ", ".join(faltan_nc)
            + ". Usa «Restablecer datos piloto» para regenerar la demostración."
        )

    # La semilla sintética genera producción y NC por día/proceso a partir de
    # la misma tasa. Se comparan solo filas marcadas como semilla, no datos
    # manuales/importados que pueden tener un flujo de registro distinto.
    desajustes_semilla = conn.execute(
        "WITH p AS ("
        " SELECT fecha, proceso, SUM(nc_detectadas) AS total"
        " FROM produccion WHERE origen_dato = 'semilla' GROUP BY fecha, proceso"
        "), n AS ("
        " SELECT fecha, proceso, SUM(cantidad) AS total"
        " FROM no_conformidades WHERE origen_dato = 'semilla' GROUP BY fecha, proceso"
        "), claves AS ("
        " SELECT fecha, proceso FROM p UNION SELECT fecha, proceso FROM n"
        ")"
        " SELECT COUNT(*) FROM claves"
        " LEFT JOIN p USING (fecha, proceso)"
        " LEFT JOIN n USING (fecha, proceso)"
        " WHERE COALESCE(p.total, 0) != COALESCE(n.total, 0)"
    ).fetchone()[0]
    if desajustes_semilla:
        problemas.append(
            f"Producción y no conformidades de la semilla no coinciden en "
            f"{desajustes_semilla} combinaciones fecha/proceso."
        )

    return {
        "integridad_sqlite": integridad_sqlite,
        "reparaciones": reparaciones,
        "problemas": problemas,
    }
