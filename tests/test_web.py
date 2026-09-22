"""Tests del servidor LAN (rutas Flask vía test_client, sin abrir puertos)."""
from __future__ import annotations

import io

import pytest

from app.core import checklists, db, seed
from app.web.servidor import crear_app


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("SICAM_DATA", str(tmp_path))
    c = db.conectar()
    seed.siembra(c)
    yield c
    c.close()


@pytest.fixture()
def client(conn):
    app = crear_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_index_lista_estaciones(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"RECT-05" in r.data


def test_formulario_de_estacion(client):
    r = client.get("/RECT-05")
    assert r.status_code == 200
    assert "Tensión del hilo".encode() in r.data          # item de plantilla recta
    assert b"FALLA" in r.data
    assert b"Tarjeta TPM" in r.data                        # nota de generación automática


def test_formulario_estacion_inexistente(client):
    assert client.get("/NO-EXISTE-99").status_code == 404


def test_guardar_checklist_con_falla_y_foto(client, conn):
    foto = (io.BytesIO(b"\xff\xd8foto-de-evidencia"), "evidencia.jpg")
    r = client.post("/RECT-05/guardar", data={
        "turno": "Tarde", "operario": "Rojas M.",
        "item_0": "Tensión del hilo (prueba en retazo)",
        "estado_0": "falla", "sev_0": "Moderada", "com_0": "costura fruncida",
        "foto_0": foto,
        "item_1": "Orden del puesto de trabajo", "estado_1": "ok",
    }, content_type="multipart/form-data")
    assert r.status_code == 200
    assert b"guardado" in r.data.lower()

    chk = conn.execute("SELECT * FROM checklists ORDER BY id DESC LIMIT 1").fetchone()
    assert (chk["maquina"], chk["operario"], chk["turno"]) == ("RECT-05", "Rojas M.", "Tarde")
    item = conn.execute(
        "SELECT * FROM checklist_items WHERE checklist_id = ? AND estado = 'falla'",
        (chk["id"],)).fetchone()
    assert item["severidad"] == "Moderada"
    assert item["foto"] and "RECT-05" in item["foto"]
    tarj = conn.execute(
        "SELECT * FROM tarjetas_tpm WHERE checklist_id = ?", (chk["id"],)).fetchone()
    assert tarj and tarj["severidad"] == "Moderada"


def test_falla_sin_foto_rechazada(client, conn):
    antes = conn.execute("SELECT COUNT(*) FROM checklists").fetchone()[0]
    r = client.post("/RECT-01/guardar", data={
        "turno": "Mañana", "operario": "Torres L.",
        "item_0": "Orden del puesto de trabajo",
        "estado_0": "falla", "sev_0": "Leve", "com_0": "",
    }, content_type="multipart/form-data")
    assert r.status_code == 400
    despues = conn.execute("SELECT COUNT(*) FROM checklists").fetchone()[0]
    assert antes == despues            # nada se guardó


def test_health(client):
    assert client.get("/health").data == b"ok"


# ---------------------------------------------------------------- IoT (fase 4a)

def test_iot_lectura_continua(client, conn):
    r = client.post("/iot/lectura", json={
        "maquina": "RECT-05", "variable": "vibracion", "valor": 5.9})
    assert r.status_code == 200
    j = r.get_json()
    assert j["nivel"] == "C"
    assert j["alerta"] is not None

    fila = conn.execute(
        "SELECT * FROM iot_lecturas ORDER BY id DESC LIMIT 1").fetchone()
    assert fila["origen"] == "esp32"
    assert (fila["maquina"], fila["variable"]) == ("RECT-05", "vibracion")


def test_iot_evento_defecto_nivel_d(client, conn):
    r = client.post("/iot/lectura", json={
        "maquina": "ETQ-03", "variable": "etiqueta", "nivel": "D", "valor": 1})
    assert r.status_code == 200
    j = r.get_json()
    assert j["nivel"] == "D"
    assert j["alerta"]["nivel"] == "D"

    alerta = conn.execute(
        "SELECT * FROM iot_alertas ORDER BY id DESC LIMIT 1").fetchone()
    assert alerta is not None
    assert alerta["nivel"] == "D"


def test_iot_maquina_desconocida(client):
    r = client.post("/iot/lectura", json={
        "maquina": "NO-EXISTE", "variable": "vibracion", "valor": 5.9})
    assert r.status_code == 400


def test_iot_variable_invalida(client):
    r = client.post("/iot/lectura", json={
        "maquina": "RECT-05", "variable": "ruido", "valor": 5.9})
    assert r.status_code == 400


def test_iot_sin_json(client):
    r = client.post("/iot/lectura", data="esto-no-es-json",
                    content_type="application/json")
    assert r.status_code == 400


def test_iot_estado(client):
    r = client.get("/iot/estado")
    assert r.status_code == 200
    assert "maquinas" in r.get_json()


def test_servidor_lan_puerto_ocupado_lanza_oserror():
    """Un segundo servidor en el mismo puerto debe lanzar OSError (no salir
    del proceso como hace werkzeug con sys.exit)."""
    import socket

    from app.web.servidor import ServidorLAN

    sonda = socket.socket()
    sonda.bind(("127.0.0.1", 0))
    puerto = sonda.getsockname()[1]
    sonda.close()

    srv1 = ServidorLAN(puerto)
    srv1.iniciar()
    try:
        srv2 = ServidorLAN(puerto)
        with pytest.raises(OSError):
            srv2.iniciar()
    finally:
        srv1.detener()
