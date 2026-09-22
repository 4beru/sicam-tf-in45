"""Consultas de analítica para el dashboard y los módulos (sin Qt)."""
from __future__ import annotations

import sqlite3

INICIO_PILOTO = "2026-07-01"

MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                "Jul", "Ago", "Set", "Oct", "Nov", "Dic"]


def etiqueta_mes(mes_iso: str) -> str:
    """'2024-01' -> 'Ene 24'"""
    anio, mes = mes_iso.split("-")
    return f"{MESES_CORTOS[int(mes) - 1]} {anio[2:]}"


def pareto(conn: sqlite3.Connection, desde: str | None = None,
           hasta: str | None = None) -> list[tuple[str, int, float]]:
    """[(causa, prendas, pct)] ordenado desc con pct sobre el total del periodo."""
    sql = "SELECT causa, SUM(cantidad) AS n FROM no_conformidades WHERE 1=1"
    params: list = []
    if desde:
        sql += " AND fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND fecha <= ?"
        params.append(hasta)
    sql += " GROUP BY causa ORDER BY n DESC"
    filas = conn.execute(sql, params).fetchall()
    total = sum(r["n"] for r in filas) or 1
    return [(r["causa"], r["n"], round(r["n"] / total * 100, 1)) for r in filas]


def tasa_mensual(conn: sqlite3.Connection) -> list[dict]:
    """Una fila por mes con tasa NC; marca el periodo piloto."""
    filas = conn.execute(
        "SELECT strftime('%Y-%m', fecha) AS mes, SUM(nc_detectadas) AS nc, "
        "SUM(inspeccionadas) AS insp FROM produccion GROUP BY mes ORDER BY mes"
    ).fetchall()
    out = []
    for r in filas:
        insp = r["insp"] or 1
        out.append({
            "mes": r["mes"],
            "etiqueta": etiqueta_mes(r["mes"]),
            "tasa": round((r["nc"] or 0) / insp * 100, 2),
            "nc": r["nc"] or 0,
            "insp": insp,
            "piloto": r["mes"] >= "2026-07",
        })
    return out


def ultimo_mes(conn: sqlite3.Connection) -> str | None:
    r = conn.execute("SELECT strftime('%Y-%m', MAX(fecha)) AS m FROM produccion").fetchone()
    return r["m"]


def _mes_anterior(mes: str) -> str:
    anio, m = int(mes[:4]), int(mes[5:7])
    m -= 1
    if m == 0:
        anio, m = anio - 1, 12
    return f"{anio}-{m:02d}"


def resumen_mes(conn: sqlite3.Connection, mes: str | None = None) -> dict:
    """KPIs del mes indicado (por defecto el último con producción)."""
    mes = mes or ultimo_mes(conn)
    if not mes:
        return {"mes": None}
    inicio, fin = f"{mes}-01", f"{mes}-31"

    def q(desde, hasta):
        return conn.execute(
            "SELECT COALESCE(SUM(nc_detectadas),0) AS nc, COALESCE(SUM(inspeccionadas),0) AS insp "
            "FROM produccion WHERE fecha BETWEEN ? AND ?", (desde, hasta)).fetchone()

    act, prev = q(inicio, fin), q(f"{_mes_anterior(mes)}-01", f"{_mes_anterior(mes)}-31")
    por_proceso = conn.execute(
        "SELECT proceso, SUM(cantidad) AS n FROM no_conformidades "
        "WHERE fecha BETWEEN ? AND ? GROUP BY proceso ORDER BY n DESC", (inicio, fin)).fetchall()
    par = pareto(conn, desde=inicio, hasta=fin)
    tasa = round(act["nc"] / act["insp"] * 100, 2) if act["insp"] else 0.0
    tasa_prev = round(prev["nc"] / prev["insp"] * 100, 2) if prev["insp"] else None
    return {
        "mes": mes,
        "nc": act["nc"],
        "insp": act["insp"],
        "tasa": tasa,
        "tasa_prev": tasa_prev,
        "por_proceso": [(r["proceso"], r["n"]) for r in por_proceso],
        "causa_top": par[0] if par else None,
    }


def ranking_operarios(conn: sqlite3.Connection, proceso: str = "Corte",
                      desde: str = INICIO_PILOTO, limite: int = 5) -> list[tuple[str, int]]:
    filas = conn.execute(
        "SELECT operario, SUM(cantidad) AS n FROM no_conformidades "
        "WHERE proceso = ? AND fecha >= ? AND operario != '—' "
        "GROUP BY operario ORDER BY n DESC LIMIT ?", (proceso, desde, limite)).fetchall()
    return [(r["operario"], r["n"]) for r in filas]


def ranking_maquinas(conn: sqlite3.Connection, desde: str = INICIO_PILOTO,
                     limite: int = 5) -> list[tuple[str, int]]:
    filas = conn.execute(
        "SELECT maquina, SUM(cantidad) AS n FROM no_conformidades "
        "WHERE maquina != '—' AND fecha >= ? "
        "GROUP BY maquina ORDER BY n DESC LIMIT ?", (desde, limite)).fetchall()
    return [(r["maquina"], r["n"]) for r in filas]


def no_conformidades(conn: sqlite3.Connection, *, proceso: str = "", turno: str = "",
                     causa: str = "", desde: str = "", hasta: str = "",
                     limite: int = 200) -> list[sqlite3.Row]:
    sql = "SELECT * FROM no_conformidades WHERE 1=1"
    params: list = []
    if proceso:
        sql += " AND proceso = ?"
        params.append(proceso)
    if turno:
        sql += " AND turno = ?"
        params.append(turno)
    if causa:
        sql += " AND causa = ?"
        params.append(causa)
    if desde:
        sql += " AND fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND fecha <= ?"
        params.append(hasta)
    sql += " ORDER BY fecha DESC, id DESC LIMIT ?"
    params.append(limite)
    return conn.execute(sql, params).fetchall()


def produccion_reciente(conn: sqlite3.Connection, limite: int = 30) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM produccion ORDER BY fecha DESC, proceso LIMIT ?",
        (limite,)).fetchall()


def tasa_diaria(conn: sqlite3.Connection, dias: int = 14) -> list[tuple[str, float]]:
    filas = conn.execute(
        "SELECT fecha, SUM(nc_detectadas) AS nc, SUM(inspeccionadas) AS insp "
        "FROM produccion GROUP BY fecha ORDER BY fecha DESC LIMIT ?", (dias,)).fetchall()
    return [(r["fecha"][5:], round(r["nc"] / (r["insp"] or 1) * 100, 2)) for r in reversed(filas)]


def metas(conn: sqlite3.Connection) -> dict[str, tuple[float, float]]:
    return {r["indicador"]: (r["as_is"], r["to_be"])
            for r in conn.execute("SELECT * FROM metas")}


def firma_datos(conn: sqlite3.Connection) -> tuple:
    """Huella del contenido mutable: si cambia, algo nuevo entró al sistema
    (desde un celular, un diálogo o una importación) y las vistas deben refrescarse."""
    filas = conn.execute("""
        SELECT 'nc',  COUNT(*), COALESCE(MAX(id),0) FROM no_conformidades
        UNION ALL SELECT 'prod', COUNT(*), COALESCE(MAX(id),0) FROM produccion
        UNION ALL SELECT 'chk',  COUNT(*), COALESCE(MAX(id),0) FROM checklists
        UNION ALL SELECT 'tarj', COUNT(*), COALESCE(MAX(id),0) FROM tarjetas_tpm
        UNION ALL SELECT 'exe',  COUNT(*), COALESCE(MAX(id),0) FROM plan_ejecuciones
        UNION ALL SELECT 'iota', COUNT(*), COALESCE(MAX(id),0) FROM iot_alertas
    """).fetchall()
    abiertas = conn.execute(
        "SELECT COUNT(*) FROM tarjetas_tpm WHERE estado != 'cerrada'").fetchone()[0]
    alertas_iot = conn.execute(
        "SELECT COUNT(*) FROM iot_alertas WHERE atendida = 0").fetchone()[0]
    # Nota: iot_lecturas queda fuera de la firma a propósito: el simulador escribe
    # cada 2 s y la página Monitor IoT se repinta sola; incluir las lecturas aquí
    # forzaría un refresh global constante (y churn de widgets) en todas las páginas.
    return tuple(tuple(f) for f in filas) + (abiertas, alertas_iot)
