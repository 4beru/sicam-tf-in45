"""Lógica de checklists móviles y tarjetas TPM (Etapa 6 de la tesis).

Regla de oro: cada ítem marcado como FALLA en un checklist genera
automáticamente una Tarjeta TPM con severidad leve / moderada / crítica
(acción: operario / mantenimiento / intervención inmediata).
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from . import db

SEVERIDADES = ["Leve", "Moderada", "Crítica"]
TIPOS_TARJETA = ["Mantenimiento", "Seguridad", "Operación"]

ACCION_SEGUN_SEVERIDAD = {
    "Leve": "Corrección por operario",
    "Moderada": "Revisión por mantenimiento",
    "Crítica": "Intervención inmediata",
}

# Plantillas por tipo de máquina (Figuras 38, 39 y 41 de la tesis)
PLANTILLAS: dict[str, list[str]] = {
    "Recta": [
        "Limpieza superficial y retiro de pelusas",
        "Estado y fijación de la aguja",
        "Tensión del hilo (prueba en retazo)",
        "Hilo y canilla suficientes",
        "Orden del puesto de trabajo",
        "Puntada uniforme en prueba",
        "Fugas de aceite en bandeja",
        "Pedal y parada de emergencia",
    ],
    "Overlock": [
        "Limpieza y retiro de pelusas",
        "Estado de cuchilla (corte limpio)",
        "Tensión de hilos (prueba en retazo)",
        "Estado de agujas y looper",
        "Orden del puesto de trabajo",
        "Cadena de costura uniforme",
        "Fugas de aceite",
        "Pedal y guardas de seguridad",
    ],
    "Recubridora": [
        "Limpieza y retiro de pelusas",
        "Calibración de tensión (prueba)",
        "Estado de agujas",
        "Hilos y canillas suficientes",
        "Orden del puesto de trabajo",
        "Costura plana sin pliegues",
        "Fugas de aceite",
        "Pedal y guardas de seguridad",
    ],
    "Cortadora": [
        "Limpieza de mesa y área de corte",
        "Cuchilla y filo en buen estado",
        "Sensor/encoder sin señal de falla",
        "Alineación de guías y topes",
        "Sistema de extracción de pelusa",
        "Botón de emergencia accesible",
    ],
    "Plancha / prensa": [
        "Limpieza de placa y superficie",
        "Presión y temperatura según estándar",
        "Estado de mangueras y cables",
        "Orden del puesto de trabajo",
        "Protector térmico en su sitio",
    ],
    "Etiquetado": [
        "Orden y limpieza de la estación",
        "Guías y topes de etiqueta alineados",
        "Etiquetas correctas por lote (talla/modelo)",
        "Herramientas en su lugar",
        "Controles visuales legibles",
    ],
}


def sembrar_plantillas(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute("DELETE FROM plantilla_checklist")
        conn.executemany(
            "INSERT OR IGNORE INTO plantilla_checklist (tipo, orden, item) VALUES (?,?,?)",
            [(tipo, i + 1, item)
             for tipo, items in PLANTILLAS.items() for i, item in enumerate(items)])


def items_de_maquina(conn: sqlite3.Connection, maquina: str) -> list[str]:
    """Items de la plantilla según el tipo de la máquina (con fallback)."""
    fila = conn.execute(
        "SELECT tipo FROM maquinas WHERE codigo = ?", (maquina,)).fetchone()
    tipo = fila["tipo"] if fila else None
    if tipo in PLANTILLAS:
        return PLANTILLAS[tipo]
    return PLANTILLAS["Etiquetado"]  # plantilla genérica de estación


def registrar_checklist(
    conn: sqlite3.Connection, maquina: str, turno: str, operario: str,
    items: list[dict], origen: str = "celular", fecha: str | None = None,
    fotos_dir: Path | None = None,
) -> dict:
    """Guarda un checklist y genera las tarjetas TPM de los ítems con falla.

    items: [{item, estado: 'ok'|'falla', severidad?, comentario?, foto_bytes?, foto_ext?}]
    Retorna {"checklist_id", "tarjetas": [id, ...]}.
    """
    if turno not in db.TURNOS:
        raise ValueError(f"turno no válido: {turno}")
    for it in items:
        if it.get("estado") not in ("ok", "falla"):
            raise ValueError(f"estado no válido en ítem: {it.get('estado')!r}")
        if it["estado"] == "falla":
            sev = it.get("severidad")
            if sev not in SEVERIDADES:
                raise ValueError("los ítems con falla requieren severidad "
                                 "(Leve / Moderada / Crítica)")

    fotos_dir = Path(fotos_dir) if fotos_dir else db.ruta_data() / "fotos"
    fotos_dir.mkdir(parents=True, exist_ok=True)
    fecha = fecha or date.today().isoformat()

    with conn:
        cur = conn.execute(
            "INSERT INTO checklists (maquina, operario, turno, fecha, origen) "
            "VALUES (?,?,?,?,?)",
            (maquina, operario or "—", turno, fecha, origen))
        checklist_id = cur.lastrowid

        tarjetas: list[int] = []
        for it in items:
            foto_ruta = ""
            if it.get("foto_bytes"):
                ext = (it.get("foto_ext") or "jpg").lower().lstrip(".") or "jpg"
                if ext not in ("jpg", "jpeg", "png", "webp", "heic"):
                    ext = "jpg"
                foto_ruta = str(fotos_dir / f"{maquina}_{fecha}_{checklist_id}_{len(tarjetas)}.{ext}")
                Path(foto_ruta).write_bytes(it["foto_bytes"])
            conn.execute(
                "INSERT INTO checklist_items (checklist_id, item, estado, severidad, "
                "comentario, foto) VALUES (?,?,?,?,?,?)",
                (checklist_id, it["item"], it["estado"],
                 it.get("severidad", ""), it.get("comentario", ""), foto_ruta))
            if it["estado"] == "falla":
                descripcion = it["item"]
                if it.get("comentario"):
                    descripcion += f" — {it['comentario']}"
                t = conn.execute(
                    "INSERT INTO tarjetas_tpm (tipo, severidad, maquina, descripcion, "
                    "origen, checklist_id) VALUES (?,?,?,?,?,?)",
                    ("Mantenimiento", it["severidad"], maquina, descripcion,
                     "Checklist", checklist_id)).lastrowid
                tarjetas.append(t)

    return {"checklist_id": checklist_id, "tarjetas": tarjetas}


def cambiar_estado_tarjeta(conn: sqlite3.Connection, tarjeta_id: int,
                           estado: str, responsable: str = "—") -> None:
    if estado not in ("abierta", "atencion", "cerrada"):
        raise ValueError(f"estado no válido: {estado}")
    with conn:
        if estado == "cerrada":
            conn.execute(
                "UPDATE tarjetas_tpm SET estado = ?, responsable = ?, "
                "cerrada_en = datetime('now','localtime') WHERE id = ?",
                (estado, responsable, tarjeta_id))
        else:
            conn.execute(
                "UPDATE tarjetas_tpm SET estado = ?, responsable = ? WHERE id = ?",
                (estado, responsable, tarjeta_id))


def crear_tarjeta_manual(conn: sqlite3.Connection, tipo: str, severidad: str,
                         maquina: str, descripcion: str) -> int:
    if tipo not in TIPOS_TARJETA:
        raise ValueError(f"tipo no válido: {tipo}")
    if severidad not in SEVERIDADES:
        raise ValueError(f"severidad no válida: {severidad}")
    with conn:
        return conn.execute(
            "INSERT INTO tarjetas_tpm (tipo, severidad, maquina, descripcion, origen) "
            "VALUES (?,?,?,?,'Manual')",
            (tipo, severidad, maquina, descripcion)).lastrowid


def codigo_tarjeta(tarjeta_id: int) -> str:
    """Id legible para mostrar (TPM-0042)."""
    return f"TPM-{tarjeta_id:04d}"


# ------------------------------------------------------------------ consultas
def cumplimiento_hoy(conn: sqlite3.Connection) -> dict:
    """Estaciones que completaron checklist hoy vs total de estaciones."""
    hoy = date.today().isoformat()
    total = conn.execute("SELECT COUNT(*) FROM maquinas").fetchone()[0]
    hechas = conn.execute(
        "SELECT COUNT(DISTINCT maquina) FROM checklists WHERE fecha = ?", (hoy,)).fetchone()[0]
    return {
        "hoy": hoy, "hechas": hechas, "total": total,
        "pct": round(hechas / total * 100, 0) if total else 0.0,
    }


def checklists_recientes(conn: sqlite3.Connection, limite: int = 20) -> list[dict]:
    filas = conn.execute(
        "SELECT c.id, c.maquina, c.operario, c.turno, c.fecha, c.creada_en, "
        "SUM(ci.estado = 'falla') AS fallas, COUNT(ci.id) AS items "
        "FROM checklists c JOIN checklist_items ci ON ci.checklist_id = c.id "
        "GROUP BY c.id ORDER BY c.id DESC LIMIT ?", (limite,)).fetchall()
    out = []
    for r in filas:
        tarjeta = None
        if r["fallas"]:
            t = conn.execute(
                "SELECT id FROM tarjetas_tpm WHERE checklist_id = ? LIMIT 1",
                (r["id"],)).fetchone()
            tarjeta = codigo_tarjeta(t["id"]) if t else None
        out.append(dict(r) | {"tarjeta": tarjeta})
    return out


def tarjetas_por_estado(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {"abierta": [], "atencion": [], "cerrada": []}
    for r in conn.execute(
            "SELECT * FROM tarjetas_tpm ORDER BY CASE estado "
            "WHEN 'abierta' THEN 0 WHEN 'atencion' THEN 1 ELSE 2 END, id DESC"):
        out[r["estado"]].append(dict(r))
    return out


def detalle_tarjeta(conn: sqlite3.Connection, tarjeta_id: int) -> dict | None:
    r = conn.execute("SELECT * FROM tarjetas_tpm WHERE id = ?", (tarjeta_id,)).fetchone()
    return dict(r) if r else None
