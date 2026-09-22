"""Tests de la semilla sintética: coherencia con las Tablas 6/7/21/22 de la tesis."""
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
    assert tasa["2026-07"] > tasa["2026-08"] > tasa["2026-09"]
    assert tasa["2026-09"] < tasa["2026-07"]


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
    assert n == 7  # una actividad por máquina (Fig. 42)
