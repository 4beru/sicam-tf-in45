"""Motor del plan de mantenimiento preventivo TPM (Figura 42 de la tesis).

Reglas: cada (máquina, actividad) tiene una frecuencia en días; la próxima
fecha vence en `última ejecución + frecuencia`. Las tareas del mes se derivan
solas — nada se calcula a mano ni en Excel.
"""
from __future__ import annotations

import calendar
import sqlite3
from datetime import date, timedelta

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "setiembre", "octubre", "noviembre", "diciembre"]

RESPONSABLES = ["Téc. Mendoza", "Téc. Soto", "Mantenimiento"]


def _hoy() -> date:
    return date.today()


def semana_de(d: date) -> int:
    """Semana 1–4 dentro del mes (para el grid S1–S4)."""
    return min(4, (d.day - 1) // 7 + 1)


def _fin_de_mes(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def ultima_ejecucion(conn: sqlite3.Connection, maquina: str, actividad: str) -> date | None:
    r = conn.execute(
        "SELECT MAX(fecha) FROM plan_ejecuciones WHERE maquina = ? AND actividad = ?",
        (maquina, actividad)).fetchone()
    return date.fromisoformat(r[0]) if r and r[0] else None


def registrar_ejecucion(conn: sqlite3.Connection, maquina: str, actividad: str,
                        fecha: str | None = None, responsable: str = "Mantenimiento",
                        observacion: str = "") -> int:
    fecha = fecha or _hoy().isoformat()
    with conn:
        return conn.execute(
            "INSERT INTO plan_ejecuciones (maquina, actividad, fecha, responsable, observacion) "
            "VALUES (?,?,?,?,?)",
            (maquina, actividad, fecha, responsable, observacion)).lastrowid


def _base_inicial(maquina: str, actividad: str, frecuencia: int, inicio_mes: date) -> date:
    """Sin ejecuciones previas: primera tarea del mes en un offset determinista."""
    semilla = sum(ord(c) for c in maquina + actividad)
    return inicio_mes + timedelta(days=semilla % max(1, frecuencia))


def tareas_del_mes(conn: sqlite3.Connection, hoy: date | None = None) -> list[dict]:
    """Ocurrencias pendientes del mes actual por cada frecuencia.

    Cada tarea: {maquina, actividad, frecuencia, fecha, semana, estado}
    estado: 'over' (vencida) · 'soon' (vence en ≤ 7 días) · 'sched' (programada).
    Las actividades ejecutadas a tiempo desaparecen de pendientes (su próxima
    ocurrencia queda a frecuencia días de la ejecución).
    """
    hoy = hoy or _hoy()
    y, m = hoy.year, hoy.month
    inicio = date(y, m, 1)
    fin = _fin_de_mes(y, m)

    tareas: list[dict] = []
    for f in conn.execute("SELECT * FROM frecuencias ORDER BY maquina"):
        freq = f["frecuencia_dias"]
        ultima = ultima_ejecucion(conn, f["maquina"], f["actividad"])
        if ultima is None:
            proxima = _base_inicial(f["maquina"], f["actividad"], freq, inicio)
        else:
            proxima = ultima + timedelta(days=freq)
        while proxima <= fin:
            dias = (proxima - hoy).days
            estado = "over" if dias < 0 else ("soon" if dias <= 7 else "sched")
            tareas.append({
                "maquina": f["maquina"], "actividad": f["actividad"],
                "frecuencia": freq, "frecuencia_txt": _texto_freq(freq),
                "fecha": proxima.isoformat(), "semana": semana_de(proxima),
                "estado": estado, "responsable": f["responsable"],
            })
            proxima += timedelta(days=freq)
    return tareas


def _texto_freq(dias: int) -> str:
    return {7: "Semanal", 15: "Quincenal", 30: "Mensual"}.get(dias, f"Cada {dias} días")


def ejecuciones_del_mes(conn: sqlite3.Connection, hoy: date | None = None) -> list[dict]:
    hoy = hoy or _hoy()
    prefijo = f"{hoy.year}-{hoy.month:02d}"
    return [dict(r) for r in conn.execute(
        "SELECT * FROM plan_ejecuciones WHERE fecha LIKE ? ORDER BY fecha DESC, id DESC",
        (prefijo + "%",))]


def resumen(conn: sqlite3.Connection, hoy: date | None = None) -> dict:
    hoy = hoy or _hoy()
    tareas = tareas_del_mes(conn, hoy)
    ejec = ejecuciones_del_mes(conn, hoy)
    vencidas = sum(1 for t in tareas if t["estado"] == "over")
    proximas = sum(1 for t in tareas if t["estado"] == "soon")
    programadas = sum(1 for t in tareas if t["estado"] == "sched")
    denom = len(ejec) + vencidas
    return {
        "mes": f"{MESES[hoy.month - 1].capitalize()} {hoy.year}",
        "vencidas": vencidas, "proximas": proximas, "programadas": programadas,
        "ejecutadas": len(ejec),
        "cumplimiento": round(len(ejec) / denom * 100, 0) if denom else 100.0,
    }


def nombre_mes(mes: int) -> str:
    return MESES[mes - 1].capitalize()


def proxima_tarea(conn: sqlite3.Connection, maquina: str) -> dict | None:
    """Próxima ocurrencia pendiente de una máquina (para su ficha)."""
    tareas = [t for t in tareas_del_mes(conn) if t["maquina"] == maquina]
    if not tareas:
        return None
    return min(tareas, key=lambda t: t["fecha"])
