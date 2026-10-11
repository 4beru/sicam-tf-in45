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



def test_fecha_referencia_respeta_mes_pasado_y_futuro():
    from datetime import date

    from app.core import queries

    hoy = date(2026, 10, 11)
    assert queries.fecha_referencia_mes("2026-08", hoy) == date(2026, 8, 31)
    assert queries.fecha_referencia_mes("2026-10", hoy) == hoy
    assert queries.fecha_referencia_mes("2026-11", hoy) == date(2026, 11, 1)


def test_limites_mes_usa_fin_real_del_calendario():
    from app.core import queries

    assert queries.limites_mes("2026-08") == ("2026-08-01", "2026-08-31")
    assert queries.limites_mes("2026-11") == ("2026-11-01", "2026-11-30")
    assert queries.limites_mes("2024-02") == ("2024-02-01", "2024-02-29")
