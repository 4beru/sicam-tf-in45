"""Página Máquinas: ficha maestra con historial, calibración y plan asociado."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..core import plan_tpm
from . import icons
from .charts import SparkBarras
from .theme import COLORS
from .widgets import Card


def _chip_crit(criticidad: str) -> QLabel:
    c = QLabel(criticidad)
    css = {"Alta": ("#FEE2E2", "#B91C1C"), "Media": ("#FEF3C7", "#B45309"),
           "Baja": ("#DCFCE7", "#15803D")}.get(criticidad, ("#F1F5F9", "#475569"))
    c.setStyleSheet(f"background:{css[0]};color:{css[1]};font-size:10px;"
                    f"font-weight:800;padding:2px 8px;border-radius:6px")
    return c


def _estado_calibracion(ultima: str) -> tuple[str, str]:
    """(texto, color) — vencida si pasaron más de 90 días."""
    if not ultima:
        return "Sin registro", "#B45309"
    try:
        dias = (date.today() - date.fromisoformat(ultima)).days
    except ValueError:
        return ultima, "#64748B"
    if dias > 90:
        return f"⚠ Vencida ({dias} días)", "#B91C1C"
    return f"✔ Al día ({dias} días)", "#15803D"


class MaquinasPage(QWidget):
    def __init__(self, conn: sqlite3.Connection, shell):
        super().__init__()
        self.conn = conn
        self.shell = shell
        self.sel: str | None = None

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        layout = QHBoxLayout()
        layout.setSpacing(14)

        self.lista_box = QVBoxLayout()
        self.lista_scroll = QScrollArea()
        self.lista_scroll.setWidgetResizable(True)
        self.lista_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.lista_scroll.setStyleSheet("QScrollArea{background:transparent;}")
        self.lista_scroll.setMinimumWidth(300)
        self.lista_widget = QWidget()
        self.lista_widget.setLayout(self.lista_box)
        self.lista_scroll.setWidget(self.lista_widget)
        layout.addWidget(self.lista_scroll, 2)

        self.detalle = Card()
        layout.addWidget(self.detalle, 3)
        v.addLayout(layout)
        self.setLayout(v)

    def _seleccionar(self, codigo: str):
        self.sel = codigo
        self.refresh()

    # ------------------------------------------------ refresco
    def refresh(self):
        maquinas = self.conn.execute("SELECT * FROM maquinas ORDER BY codigo").fetchall()
        if self.sel is None and maquinas:
            self.sel = maquinas[0]["codigo"]

        # ---- lista
        while self.lista_box.count():
            item = self.lista_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for m in maquinas:
            tarjeta = _tarjeta_maquina(m, self.sel == m["codigo"])
            tarjeta.mousePressEvent = (lambda e, c=m["codigo"]: self._seleccionar(c))
            self.lista_box.addWidget(tarjeta)
        self.lista_box.addStretch(1)

        # ---- detalle
        while self.detalle.vbox.count():
            item = self.detalle.vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
        m = next((x for x in maquinas if x["codigo"] == self.sel), None)
        if m is None:
            self.detalle.vbox.addWidget(QLabel("Sin máquinas registradas."))
            return
        self._pintar_detalle(m)

    def _pintar_detalle(self, m):
        codigo, tipo, marca = m["codigo"], m["tipo"], m["marca_modelo"]

        cabeza = QHBoxLayout()
        titulo = QLabel(f"<span style='font-size:17px;font-weight:800'>{codigo}</span>"
                        f"&nbsp;&nbsp;<span style='color:#64748B'>{tipo} · {marca}</span>")
        titulo.setTextFormat(Qt.TextFormat.RichText)
        cabeza.addWidget(titulo)
        cabeza.addStretch(1)
        cabeza.addWidget(_chip_crit(m["criticidad"]))
        self.detalle.vbox.addLayout(cabeza)

        estado_txt, color = _estado_calibracion(m["ultima_calibracion"])
        estado = QLabel(f"Calibración: <b style='color:{color}'>{estado_txt}</b>")
        estado.setTextFormat(Qt.TextFormat.RichText)
        self.detalle.vbox.addWidget(estado)

        # fichas rápidas
        desde = date.today().replace(year=date.today().year - 1).isoformat()
        tarj_abiertas = self.conn.execute(
            "SELECT COUNT(*) FROM tarjetas_tpm WHERE maquina = ? AND estado != 'cerrada'",
            (codigo,)).fetchone()[0]
        fallas_12m = self.conn.execute(
            "SELECT COUNT(*) FROM tarjetas_tpm WHERE maquina = ?", (codigo,)).fetchone()[0]
        proxima = plan_tpm.proxima_tarea(self.conn, codigo)

        grid = QHBoxLayout()
        grid.setSpacing(10)
        for etiqueta, valor in [
            ("Área", m["area"]),
            ("Fecha de compra", m["fecha_compra"] or "—"),
            ("Últ. calibración", m["ultima_calibracion"] or "—"),
            ("Tarjetas abiertas", str(tarj_abiertas)),
            ("Tarjetas 12 m", str(fallas_12m)),
            ("Próx. mantenimiento",
             f"{proxima['actividad'][:22]}… · {proxima['fecha'][8:]}/{proxima['fecha'][5:7]}"
             if proxima else "—"),
        ]:
            ficha = QWidget()
            ficha.setProperty("cls", "ficha")
            fv = QVBoxLayout(ficha)
            fv.setContentsMargins(10, 8, 10, 8)
            e = QLabel(etiqueta.upper())
            e.setProperty("cls", "ficha_lbl")
            val = QLabel(f"<b>{valor}</b>")
            val.setTextFormat(Qt.TextFormat.RichText)
            val.setWordWrap(True)
            fv.addWidget(e)
            fv.addWidget(val)
            grid.addWidget(ficha, 1)
        self.detalle.vbox.addLayout(grid)

        # historial de fallas por mes (12 m)
        filas = self.conn.execute(
            "SELECT strftime('%Y-%m', creada_en) AS mes, COUNT(*) AS n "
            "FROM tarjetas_tpm WHERE maquina = ? AND creada_en >= ? "
            "GROUP BY mes ORDER BY mes", (codigo, desde)).fetchall()
        por_mes = {f["mes"]: f["n"] for f in filas}
        datos = []
        d = date.today().replace(day=1)
        for _ in range(12):
            datos.append(por_mes.get(d.strftime("%Y-%m"), 0))
            d = (d.replace(day=28) - timedelta(days=32)).replace(day=1)
        datos.reverse()
        self.spark = SparkBarras()
        self.spark.set_datos(datos, "Tarjetas TPM por mes · histórico")
        self.detalle.vbox.addWidget(self.spark)

        # acciones
        acciones = QHBoxLayout()
        b1 = QPushButton("  Nueva tarjeta para esta máquina")
        b1.setProperty("cls", "primary")
        b1.setIcon(icons.icono("plus", "#FFFFFF", 15))
        b1.clicked.connect(lambda: self._nueva_tarjeta(codigo))
        b2 = QPushButton("  Ver en plan TPM")
        b2.setProperty("cls", "ghost")
        b2.setIcon(icons.icono("calendar", COLORS["teal"], 15))
        b2.clicked.connect(lambda: self.shell.ir_a("plan"))
        acciones.addWidget(b1)
        acciones.addWidget(b2)
        acciones.addStretch(1)
        self.detalle.vbox.addLayout(acciones)
        self.detalle.vbox.addStretch(1)

    def _nueva_tarjeta(self, codigo: str):
        from .tarjetas_page import NuevaTarjetaDialog
        dlg = NuevaTarjetaDialog(self.conn, self)
        dlg.maquina.setCurrentText(codigo)
        if dlg.exec():
            self.shell.toast(f"Tarjeta TPM creada para {codigo}")
            self.shell.refresh_all(excepto="maq")


def _tarjeta_maquina(m, seleccionada: bool) -> QFrame:
    """Tarjeta compacta de la lista de máquinas."""
    t = QFrame()
    t.setProperty("cls", "maq-sel" if seleccionada else "maq-card")
    t.setCursor(Qt.CursorShape.PointingHandCursor)
    v = QVBoxLayout(t)
    v.setContentsMargins(12, 10, 12, 10)
    v.setSpacing(3)
    r1 = QHBoxLayout()
    id_lbl = QLabel(f"<b>{m['codigo']}</b>")
    id_lbl.setTextFormat(Qt.TextFormat.RichText)
    r1.addWidget(id_lbl)
    r1.addStretch(1)
    r1.addWidget(_chip_crit(m["criticidad"]))
    v.addLayout(r1)
    r2 = QLabel(f"{m['tipo']} · {m['marca_modelo']} · {m['area']}")
    r2.setProperty("cls", "hint")
    v.addWidget(r2)
    return t
