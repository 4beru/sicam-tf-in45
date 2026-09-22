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
