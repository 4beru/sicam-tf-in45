from __future__ import annotations

import pytest

from app.core import db, integridad, seed


@pytest.fixture()
def conn(tmp_path):
    conexion = db.conectar(tmp_path / "integridad.db")
    seed.siembra(conexion, reset=True)
    yield conexion
    conexion.close()


def test_semilla_restaurada_pasa_auditoria(conn):
    resultado = integridad.auditar_y_reparar(conn)
    assert resultado["integridad_sqlite"] == "ok"
    assert resultado["reparaciones"] == []
    assert resultado["problemas"] == []


def test_auditoria_elimina_items_sin_checklist_padre(conn):
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO checklist_items (checklist_id, item, estado) "
        "VALUES (999999, 'ítem huérfano', 'ok')"
    )
    conn.commit()
    conn.execute("PRAGMA foreign_keys=ON")

    resultado = integridad.auditar_y_reparar(conn)
    assert any("ítems de checklist sin registro padre" in x for x in resultado["reparaciones"])
    assert conn.execute(
        "SELECT COUNT(*) FROM checklist_items WHERE checklist_id=999999"
    ).fetchone()[0] == 0
