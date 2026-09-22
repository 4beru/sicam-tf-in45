"""Tests del motor del plan TPM (Fig. 42) y de los reportes PDF."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.core import db, plan_tpm, queries, reportes, seed


@pytest.fixture()
def conn(tmp_path):
    c = db.conectar(tmp_path / "plan.db")
    seed.siembra(c)
    yield c
    c.close()


def test_frecuencias_fig42(conn):
    frecs = {(f["maquina"], f["actividad"]): f["frecuencia_dias"]
             for f in conn.execute("SELECT * FROM frecuencias")}
    assert frecs[("RECT-05", "Lubricación y revisión de puntada")] == 7
    assert frecs[("OVE-01", "Revisión de cuchilla")] == 15
    assert frecs[("REC-02", "Calibración de tensión")] == 15
    assert frecs[("COR-01", "Revisión de sensor/encoder")] == 30


def test_motor_genera_tareas_y_estados(conn):
    tareas = plan_tpm.tareas_del_mes(conn)
    assert tareas, "el mes debe tener tareas programadas"
    estados = {t["estado"] for t in tareas}
    assert estados & {"over", "soon", "sched"}
    for t in tareas:
        assert 1 <= t["semana"] <= 4
        d = date.fromisoformat(t["fecha"])
        assert t["semana"] == plan_tpm.semana_de(d)


def test_registrar_ejecucion_elimina_vencida_y_sube_cumplimiento(conn):
    antes = plan_tpm.resumen(conn)
    assert antes["vencidas"] > 0

    # ejecutar hoy una actividad vencida (la primera que aparezca)
    vencida = next(t for t in plan_tpm.tareas_del_mes(conn) if t["estado"] == "over")
    plan_tpm.registrar_ejecucion(conn, vencida["maquina"], vencida["actividad"],
                                 responsable="Téc. Mendoza")

    despues = plan_tpm.resumen(conn)
    assert despues["vencidas"] == antes["vencidas"] - 1
    assert despues["ejecutadas"] == antes["ejecutadas"] + 1
    assert despues["cumplimiento"] > antes["cumplimiento"]
    # la próxima ocurrencia queda a frecuencia días de hoy (si cae dentro del mes)
    esperada = date.today() + timedelta(days=vencida["frecuencia"])
    proxima = plan_tpm.proxima_tarea(conn, vencida["maquina"])
    if proxima is not None:
        assert date.fromisoformat(proxima["fecha"]) == esperada
    else:
        # la próxima cae el mes siguiente: no hay pendientes de esa máquina este mes
        assert (esperada.year, esperada.month) != (date.today().year, date.today().month)


def test_resumen_coherente(conn):
    r = plan_tpm.resumen(conn)
    assert date.today().strftime("%Y") in r["mes"]
    assert r["ejecutadas"] >= 1          # la semilla registró ejecuciones pasadas
    assert 0 <= r["cumplimiento"] <= 100


def test_pdfs_se_generan(conn, tmp_path):
    p1 = reportes.pdf_plan(conn, tmp_path / "plan.pdf")
    p2 = reportes.pdf_indicadores(conn, tmp_path / "indicadores.pdf")
    p3 = reportes.pdf_pareto(conn, tmp_path / "pareto.pdf")
    for p in (p1, p2, p3):
        assert p.exists() and p.stat().st_size > 1500
        assert p.read_bytes()[:5] == b"%PDF-"


def test_firma_datos_cambia_al_registrar(conn):
    f1 = queries.firma_datos(conn)
    plan_tpm.registrar_ejecucion(conn, "RECT-01", "Lubricación y revisión de puntada")
    assert queries.firma_datos(conn) != f1
