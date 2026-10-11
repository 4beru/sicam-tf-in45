"""Tests de la semilla sintética: cobertura, coherencia e idempotencia."""
from __future__ import annotations

import pytest

from app.core import db, queries, seed


@pytest.fixture()
def conn(tmp_path):
    c = db.conectar(tmp_path / "seed.db")
    seed.siembra(c)
    yield c
    c.close()


def test_volumenes_coherentes_con_la_tesis(conn):
    total_nc = conn.execute("SELECT SUM(cantidad) FROM no_conformidades WHERE fecha LIKE '2024%'").fetchone()[0]
    # tesis: 48 021 prendas NC en 2024 (tolerancia por redondeos del generador)
    assert 44_000 < total_nc < 52_000


def test_tasa_2024_cerca_del_as_is(conn):
    meses = [m for m in queries.tasa_mensual(conn) if m["mes"].startswith("2024")]
    promedio = sum(m["nc"] for m in meses) / sum(m["insp"] for m in meses) * 100
    assert 10.3 < promedio < 11.0  # As-Is 10.68


def test_piloto_desciende_hacia_la_meta(conn):
    tasa = {m["mes"]: m["tasa"] for m in queries.tasa_mensual(conn) if m["piloto"]}
    meses = [f"2026-{mes:02d}" for mes in range(7, 12)]
    assert all(mes in tasa for mes in meses)
    assert all(tasa[a] > tasa[b] for a, b in zip(meses, meses[1:]))
    assert tasa["2026-09"] < tasa["2026-07"]


def test_semilla_no_duplica_datos_si_se_ejecuta_otra_vez(conn):
    tablas = (
        "produccion", "no_conformidades", "checklists", "tarjetas_tpm",
        "plan_ejecuciones", "iot_lecturas", "iot_alertas",
    )
    antes = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tablas}
    seed.siembra(conn)
    despues = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tablas}
    assert despues == antes


def test_piloto_completo_y_cantidades_validas(conn):
    assert conn.execute(
        "SELECT COUNT(*) FROM produccion WHERE fecha BETWEEN '2026-08-01' AND '2026-11-30'"
    ).fetchone()[0] > 0
    invalidas = conn.execute(
        "SELECT COUNT(*) FROM produccion "
        "WHERE inspeccionadas <= 0 OR nc_detectadas < 0 OR nc_detectadas > inspeccionadas"
    ).fetchone()[0]
    assert invalidas == 0


def test_pareto_respeta_el_orden_de_la_tabla_7(conn):
    par = queries.pareto(conn)
    causas = [c for c, _, _ in par]
    # las cuatro primeras causas de la Tabla 7 deben liderar (en algún orden cercano)
    assert set(causas[:4]) == {
        "Operaciones no estandarizadas",
        "Errores humanos",
        "Incumplimiento del mantenimiento preventivo",
        "Descalibración de máquinas",
    }
    acum = sum(p for _, _, p in par[:4])
    assert 78 <= acum <= 85  # ~81% de participación


def test_metas_y_frecuencias_presentes(conn):
    m = queries.metas(conn)
    assert m["Tasa de prendas no conformes"] == (10.68, 4.95)
    n = conn.execute("SELECT COUNT(*) FROM frecuencias").fetchone()[0]
    maquinas = conn.execute("SELECT COUNT(*) FROM maquinas").fetchone()[0]
    assert n == maquinas == 30
