"""Regresión del flujo completo de restablecimiento de datos piloto."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.core import db, integridad, seed
from app.ui.datos_page import DatosPage


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("SICAM_DATA", str(tmp_path / "sicam-data"))
    conexion = db.conectar(tmp_path / "sicam.db")
    seed.siembra(conexion, reset=True)
    yield conexion
    conexion.close()


def test_restaurar_piloto_recupera_mes_catalogo_y_evidencias(
    conn, app, monkeypatch
):
    carpeta_fotos = db.ruta_data() / "fotos"
    carpeta_fotos.mkdir(parents=True)
    foto = carpeta_fotos / "evidencia.jpg"
    foto.write_bytes(b"evidencia de prueba")
    item = conn.execute(
        "SELECT id FROM checklist_items ORDER BY id LIMIT 1"
    ).fetchone()
    assert item is not None

    # Simular el estado anterior: catálogo desviado y meses finales ausentes.
    with conn:
        conn.execute(
            "UPDATE maquinas SET marca_modelo = 'CATALOGO ANTIGUO'"
        )
        conn.execute(
            "UPDATE checklist_items SET foto = ? WHERE id = ?",
            (str(foto), item["id"]),
        )
        conn.execute(
            "DELETE FROM produccion WHERE fecha BETWEEN '2026-10-01' AND '2026-11-30'"
        )
        conn.execute(
            "DELETE FROM no_conformidades WHERE fecha BETWEEN '2026-10-01' AND '2026-11-30'"
        )

    mensajes = []
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        QMessageBox, "critical",
        lambda *args, **kwargs: mensajes.append(("critical", args)),
    )
    monkeypatch.setattr(
        QMessageBox, "warning",
        lambda *args, **kwargs: mensajes.append(("warning", args)),
    )

    class ShellStub:
        _firma = None

        def __init__(self):
            self.toasts = []
            self.refrescos = []

        def toast(self, mensaje):
            self.toasts.append(mensaje)

        def refresh_all(self, **kwargs):
            self.refrescos.append(kwargs)

    shell = ShellStub()
    page = DatosPage(conn, shell)
    page._resembrar()

    resultado = integridad.auditar_y_reparar(conn)
    assert resultado["integridad_sqlite"] == "ok"
    assert resultado["problemas"] == []
    assert not any(tipo == "critical" for tipo, _ in mensajes)
    assert not any(tipo == "warning" for tipo, _ in mensajes)
    assert shell.toasts == ["Datos piloto restaurados y auditados"]
    assert shell.refrescos == [{"excepto": "datos"}]
    assert not foto.exists()

    for mes, fin in (("2026-08", "2026-08-31"), ("2026-09", "2026-09-30"),
                     ("2026-10", "2026-10-31"), ("2026-11", "2026-11-30")):
        assert conn.execute(
            "SELECT COUNT(*) FROM produccion WHERE fecha BETWEEN ? AND ?",
            (f"{mes}-01", fin),
        ).fetchone()[0] > 0
        assert conn.execute(
            "SELECT COUNT(*) FROM no_conformidades WHERE fecha BETWEEN ? AND ?",
            (f"{mes}-01", fin),
        ).fetchone()[0] > 0

    assert conn.execute(
        "SELECT COUNT(*) FROM maquinas WHERE marca_modelo = 'CATALOGO ANTIGUO'"
    ).fetchone()[0] == 0
