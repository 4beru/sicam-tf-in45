"""Tests de la lógica de checklists → tarjetas TPM (regla de oro de la fase 2)."""
from __future__ import annotations

import pytest

from app.core import checklists, db, seed


@pytest.fixture()
def conn(tmp_path):
    c = db.conectar(tmp_path / "chk.db")
    seed.siembra(c)
    yield c
    c.close()


def _items(conn, maquina, con_fallas):
    items = []
    for i, item in enumerate(checklists.items_de_maquina(conn, maquina)):
        if item in con_fallas:
            sev, com = con_fallas[item]
            items.append({"item": item, "estado": "falla", "severidad": sev, "comentario": com})
        else:
            items.append({"item": item, "estado": "ok"})
    return items


def test_plantillas_por_tipo(conn):
    assert len(checklists.items_de_maquina(conn, "RECT-05")) == 8   # recta
    assert len(checklists.items_de_maquina(conn, "COR-01")) == 6    # cortadora
    assert "Estado de cuchilla" in " ".join(checklists.items_de_maquina(conn, "OVE-01"))


def test_falla_genera_tarjeta_con_severidad(conn):
    res = checklists.registrar_checklist(
        conn, "RECT-05", "Tarde", "Rojas M.",
        _items(conn, "RECT-05", {"Tensión del hilo (prueba en retazo)": ("Moderada", "fruncida")}))
    assert len(res["tarjetas"]) == 1
    t = checklists.detalle_tarjeta(conn, res["tarjetas"][0])
    assert t["tipo"] == "Mantenimiento"
    assert t["severidad"] == "Moderada"
    assert "Tensión del hilo" in t["descripcion"]
    assert "fruncida" in t["descripcion"]          # el comentario viaja en la descripción
    assert t["origen"] == "Checklist"
    assert t["estado"] == "abierta"


def test_varias_fallas_generan_varias_tarjetas(conn):
    res = checklists.registrar_checklist(
        conn, "OVE-01", "Mañana", "Quispe J.",
        _items(conn, "OVE-01", {
            "Estado de cuchilla (corte limpio)": ("Crítica", "cortes irregulares"),
            "Pedal y guardas de seguridad": ("Leve", "guarda floja"),
        }))
    assert len(res["tarjetas"]) == 2
    sevs = {checklists.detalle_tarjeta(conn, t)["severidad"] for t in res["tarjetas"]}
    assert sevs == {"Crítica", "Leve"}


def test_falla_sin_severidad_rechazada(conn):
    with pytest.raises(ValueError):
        checklists.registrar_checklist(conn, "RECT-01", "Tarde", "—",
                                       [{"item": "x", "estado": "falla"}])


def test_ciclo_de_vida_de_tarjeta(conn):
    tid = checklists.crear_tarjeta_manual(
        conn, "Seguridad", "Crítica", "COR-01", "Protector retirado")
    assert checklists.detalle_tarjeta(conn, tid)["estado"] == "abierta"
    checklists.cambiar_estado_tarjeta(conn, tid, "atencion", "Téc. Soto")
    t = checklists.detalle_tarjeta(conn, tid)
    assert (t["estado"], t["responsable"]) == ("atencion", "Téc. Soto")
    checklists.cambiar_estado_tarjeta(conn, tid, "cerrada", "Téc. Soto")
    assert checklists.detalle_tarjeta(conn, tid)["cerrada_en"] is not None


def test_cumplimiento_y_recientes(conn):
    c = checklists.cumplimiento_hoy(conn)
    assert c["total"] == 7                    # estaciones sembradas
    assert 0 < c["hechas"] <= c["total"]      # la semilla llenó algunas hoy
    rec = checklists.checklists_recientes(conn, 5)
    assert rec and all("tarjeta" in r for r in rec)


def test_foto_se_guarda_en_disco(conn, tmp_path):
    res = checklists.registrar_checklist(
        conn, "RECT-01", "Tarde", "Torres L.",
        [{"item": "Orden del puesto de trabajo", "estado": "falla",
          "severidad": "Leve", "comentario": "retazos",
          "foto_bytes": b"\xff\xd8fake", "foto_ext": ".jpg"}],
        fotos_dir=tmp_path / "fotos")
    fotos = list((tmp_path / "fotos").glob("*.jpg"))
    assert len(fotos) == 1
    fila = conn.execute(
        "SELECT foto FROM checklist_items WHERE checklist_id = ?",
        (res["checklist_id"],)).fetchone()
    assert fila["foto"].endswith(".jpg")
