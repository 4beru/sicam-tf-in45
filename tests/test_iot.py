"""Tests del módulo CORE del monitor IoT (umbrales, clasificación, alertas)."""
from __future__ import annotations

import random

import pytest

from app.core import db, iot, seed


@pytest.fixture()
def conn(tmp_path):
    c = db.conectar(tmp_path / "iot.db")
    seed.siembra(c)
    yield c
    c.close()


# ---------------------------------------------------------------- clasificar
def test_clasificar_tension_en_limites(conn):
    u = iot.umbrales(conn)["tension"]
    assert iot.clasificar(45.0, u) == "ok"    # ok_lo
    assert iot.clasificar(55.0, u) == "ok"    # ok_hi
    assert iot.clasificar(40.0, u) == "A"     # a_lo
    assert iot.clasificar(60.0, u) == "A"     # a_hi
    assert iot.clasificar(39.0, u) == "C"     # bajo a_lo
    assert iot.clasificar(61.0, u) == "C"     # sobre a_hi


def test_clasificar_vibracion_a_lo_negativo(conn):
    u = iot.umbrales(conn)["vibracion"]
    assert u["a_lo"] == -1.0
    assert iot.clasificar(0.0, u) == "ok"     # valor bajo normal sigue ok
    assert iot.clasificar(4.5, u) == "ok"
    assert iot.clasificar(5.2, u) == "A"
    assert iot.clasificar(-1.0, u) == "A"
    assert iot.clasificar(6.0, u) == "C"


# ----------------------------------------------------------- registrar_lectura
def test_registrar_lectura_nivel_y_transicion_a_c(conn):
    r1 = iot.registrar_lectura(conn, "RECT-05", "tension", 50.0)
    assert r1["nivel"] == "ok"
    assert r1["alerta"] is None

    r2 = iot.registrar_lectura(conn, "RECT-05", "tension", 39.0)
    assert r2["nivel"] == "C"
    assert r2["alerta"] is not None
    assert r2["alerta"]["nivel"] == "C"
    assert r2["alerta"]["maquina"] == "RECT-05"
    assert r2["alerta"]["variable"] == "tension"

    # segunda lectura C consecutiva no duplica alerta
    r3 = iot.registrar_lectura(conn, "RECT-05", "tension", 38.0)
    assert r3["nivel"] == "C"
    assert r3["alerta"] is None

    # transición A -> C sí crea otra alerta
    r4 = iot.registrar_lectura(conn, "RECT-05", "tension", 41.0)
    assert r4["nivel"] == "A"
    assert r4["alerta"] is not None
    assert iot.alertas_pendientes(conn) == 2


def test_registrar_lectura_valida_maquina_y_variable(conn):
    with pytest.raises(ValueError):
        iot.registrar_lectura(conn, "NO-EXISTE", "tension", 50.0)
    with pytest.raises(ValueError):
        iot.registrar_lectura(conn, "RECT-05", "presion", 50.0)
    with pytest.raises(ValueError):
        iot.registrar_lectura(conn, "RECT-05", "tension", "no-numérico")


# ------------------------------------------------------ tarjetas desde alerta
def test_crear_tarjeta_desde_alerta_critica(conn):
    aid = iot.registrar_alerta(conn, "RECT-05", "tension", "C", "mensaje", 39.0)
    tid = iot.crear_tarjeta_desde_alerta(conn, aid)
    t = conn.execute("SELECT * FROM tarjetas_tpm WHERE id = ?", (tid,)).fetchone()
    assert t["tipo"] == "Mantenimiento"
    assert t["severidad"] == "Crítica"
    assert t["origen"] == "IoT"
    a = conn.execute("SELECT * FROM iot_alertas WHERE id = ?", (aid,)).fetchone()
    assert a["atendida"] == 1
    assert a["tarjeta_id"] == tid


def test_crear_tarjeta_desde_alerta_moderada(conn):
    aid = iot.registrar_alerta(conn, "RECT-05", "tension", "A", "mensaje", 41.0)
    tid = iot.crear_tarjeta_desde_alerta(conn, aid)
    t = conn.execute("SELECT * FROM tarjetas_tpm WHERE id = ?", (tid,)).fetchone()
    assert t["severidad"] == "Moderada"


def test_crear_tarjeta_rechaza_nivel_d(conn):
    aid = iot.registrar_alerta(conn, "ETQ-03", "velocidad", "D", "etiqueta invertida", 0.0)
    with pytest.raises(ValueError):
        iot.crear_tarjeta_desde_alerta(conn, aid)


# ------------------------------------------------------- NC desde alerta D
def test_registrar_nc_desde_alerta_d(conn):
    aid = iot.registrar_alerta(conn, "COR-01", "velocidad", "D", "etiqueta invertida", 0.0)
    nc_id = iot.registrar_nc_desde_alerta(conn, aid)
    nc = conn.execute("SELECT * FROM no_conformidades WHERE id = ?", (nc_id,)).fetchone()
    assert nc["maquina"] == "COR-01"
    assert nc["proceso"] == "Corte"           # área de la máquina
    assert nc["causa"] == "Descalibración de máquinas"
    a = conn.execute("SELECT * FROM iot_alertas WHERE id = ?", (aid,)).fetchone()
    assert a["atendida"] == 1


def test_registrar_nc_rechaza_nivel_no_d(conn):
    aid = iot.registrar_alerta(conn, "RECT-05", "tension", "A", "mensaje", 41.0)
    with pytest.raises(ValueError):
        iot.registrar_nc_desde_alerta(conn, aid)


# ---------------------------------------------------------- actualizar umbral
def test_actualizar_umbral_cambia_clasificacion(conn):
    iot.actualizar_umbral(conn, "tension", ok_hi=60.0)
    u = iot.umbrales(conn)["tension"]
    assert u["ok_hi"] == 60.0
    assert iot.clasificar(57.0, u) == "ok"    # antes habría sido "A"


def test_actualizar_umbral_campo_invalido(conn):
    with pytest.raises(ValueError):
        iot.actualizar_umbral(conn, "tension", foo=1.0)
    with pytest.raises(ValueError):
        iot.actualizar_umbral(conn, "presion", ok_hi=60.0)


# -------------------------------------------------------------- simulación
def test_simular_paso_cuatro_filas_en_rango(conn):
    antes = conn.execute(
        "SELECT COUNT(*) FROM iot_lecturas WHERE maquina = 'RECT-05'").fetchone()[0]
    alertas = iot.simular_paso(conn, "RECT-05", rng=random.Random(1))
    despues = conn.execute(
        "SELECT COUNT(*) FROM iot_lecturas WHERE maquina = 'RECT-05'").fetchone()[0]
    assert despues - antes == 4
    u = iot.umbrales(conn)
    for variable in iot.VARIABLES:
        ult = iot.ultima_lectura(conn, "RECT-05", variable)
        assert u[variable]["min_escala"] <= ult["valor"] <= u[variable]["max_escala"]


def test_generar_historial_siembra_60_por_variable(conn):
    conn.execute("DELETE FROM iot_lecturas")
    conn.commit()
    iot.generar_historial(conn, "RECT-05", n=60)
    n = conn.execute(
        "SELECT COUNT(*) FROM iot_lecturas WHERE maquina = 'RECT-05'").fetchone()[0]
    assert n == 60 * 4
