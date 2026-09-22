"""Tests de INTERACCIÓN real de UI para el Monitor IoT (Fase 4a).

Ejercitan los flujos del usuario a través de clics sobre la página IotPage:
simular alertas C/D, crear tarjeta TPM, registrar NC, atender, guardar
umbrales, cambiar de máquina y alternar el simulador.

Configuración importante: plataforma Qt offscreen ANTES de importar PySide6,
una BD aislada por test (SICAM_DATA apuntando a tmp_path) y timers detenidos
para que las interacciones sean deterministas.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from app.core import db, iot, seed  # noqa: E402
from app.ui.shell import Shell  # noqa: E402
from app.ui.theme import qss  # noqa: E402


@pytest.fixture(scope="module")
def app():
    """Una única QApplication para todo el módulo."""
    a = QApplication.instance()
    if a is None:
        a = QApplication(sys.argv)
    return a


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("SICAM_DATA", str(tmp_path))
    c = db.conectar()
    seed.siembra(c)
    yield c
    c.close()


@pytest.fixture()
def shell(conn, app):
    app.setStyleSheet(qss())
    s = Shell(conn)
    s.show()
    # determinismo: sin timers de simulación ni reactividad durante el test
    s.paginas["iot"]._timer.stop()
    s._timer_reactividad.stop()
    s.ir_a("iot")
    QApplication.processEvents()
    yield s
    s.close()


# ------------------------------------------------------------------ helpers
def _boton(parent, texto: str) -> QPushButton:
    for b in parent.findChildren(QPushButton):
        if b.text() == texto:
            return b
    raise AssertionError(f"botón no encontrado: {texto!r}")


def _clic(boton: QPushButton) -> None:
    boton.click()
    QApplication.processEvents()


# -------------------------------------------------------------------- tests
def test_simular_alerta_c_crea_alerta_y_tarjeta_tpm(shell, conn):
    page = shell.paginas["iot"]

    _clic(page.btn_c)

    pendientes = iot.alertas(conn, solo_pendientes=True)
    assert len(pendientes) == 1
    assert pendientes[0]["nivel"] == "C"
    assert pendientes[0]["maquina"] == page._maquina_actual
    aid = pendientes[0]["id"]

    _clic(_boton(page, "Crear tarjeta TPM"))

    t = conn.execute(
        "SELECT * FROM tarjetas_tpm WHERE origen = 'IoT' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert t is not None
    assert t["severidad"] == "Crítica"

    a = conn.execute("SELECT * FROM iot_alertas WHERE id = ?", (aid,)).fetchone()
    assert a["atendida"] == 1
    assert a["tarjeta_id"] == t["id"]

    # la campana del shell queda con pendientes visibles
    assert shell.bell.text().strip() != ""


def test_simular_alerta_d_registra_nc(shell, conn):
    page = shell.paginas["iot"]

    _clic(page.btn_d)

    pendientes = iot.alertas(conn, solo_pendientes=True)
    assert len(pendientes) == 1
    assert pendientes[0]["nivel"] == "D"
    aid = pendientes[0]["id"]

    _clic(_boton(page, "Registrar NC"))

    nc = conn.execute(
        "SELECT * FROM no_conformidades ORDER BY id DESC LIMIT 1").fetchone()
    assert nc is not None
    assert nc["maquina"] == page._maquina_actual
    assert nc["causa"] == "Descalibración de máquinas"

    a = conn.execute("SELECT * FROM iot_alertas WHERE id = ?", (aid,)).fetchone()
    assert a["atendida"] == 1


def test_atender_alerta_sin_accion(shell, conn):
    page = shell.paginas["iot"]

    _clic(page.btn_c)
    aid = iot.alertas(conn, solo_pendientes=True)[0]["id"]

    _clic(_boton(page, "Atender"))

    a = conn.execute("SELECT * FROM iot_alertas WHERE id = ?", (aid,)).fetchone()
    assert a["atendida"] == 1
    assert a["tarjeta_id"] is None
    assert conn.execute(
        "SELECT COUNT(*) FROM tarjetas_tpm WHERE origen = 'IoT'").fetchone()[0] == 0


def test_guardar_umbrales_actualiza_clasificacion(shell, conn):
    page = shell.paginas["iot"]

    spin = page._spin_umbrales[("tension", "ok_hi")]
    spin.setValue(60.0)
    _clic(_boton(page, "Guardar umbrales"))

    u = iot.umbrales(conn)["tension"]
    assert u["ok_hi"] == 60.0
    assert iot.clasificar(57.0, u) == "ok"


def test_cambio_de_maquina_repinta_gauges(shell, conn):
    page = shell.paginas["iot"]

    page.combo_maquinas.setCurrentText("RECT-01")
    QApplication.processEvents()
    page.refresh()
    QApplication.processEvents()

    ultima = iot.ultima_lectura(conn, "RECT-01", "tension")
    esperado = f"{ultima['valor']:.1f} cN" if ultima else "—"
    assert page._gauges["tension"]["valor"].text() == esperado


def test_toggle_simulador_controla_inserciones(shell, conn):
    page = shell.paginas["iot"]
    maquina = page._maquina_actual

    def contar() -> int:
        return conn.execute(
            "SELECT COUNT(*) FROM iot_lecturas WHERE maquina = ?",
            (maquina,)).fetchone()[0]

    antes = contar()

    page.btn_sim.setChecked(False)
    page._tick()
    assert contar() == antes

    page.btn_sim.setChecked(True)
    page._tick()
    assert contar() == antes + 4


def test_sin_lecturas_maquina(shell, conn):
    page = shell.paginas["iot"]

    conn.execute("DELETE FROM iot_lecturas WHERE maquina = 'COR-01'")
    conn.commit()

    page.combo_maquinas.setCurrentText("COR-01")
    QApplication.processEvents()
    page.refresh()  # no debe lanzar excepción
    QApplication.processEvents()

    assert page._gauges["tension"]["valor"].text() == "—"
